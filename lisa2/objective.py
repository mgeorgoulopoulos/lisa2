"""Separate, normalized interior-color, edge and black-background losses."""
from collections import deque

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt, gaussian_filter, label


CONTOUR_DEFAULTS = dict(preserve_contours=True, contour_max_radius=20,
                        contour_internal_radius=6, preserve_thin_features=True,
                        balance_regions=False, region_count=2, region_share=20,
                        exterior_weight=4., shell_strength=.25, thin_strength=1.25)

WEIGHT_LIMITS = dict(exterior_weight=(1.25,8.), shell_strength=(0.,2.),
                     thin_strength=(0.,3.))


def contour_options(settings):
    options = {}
    if settings['preserve_contours']:
        options.update(preserve_contours=True, contour_max_radius=settings['contour_max_radius'],
                       contour_internal_radius=settings['contour_internal_radius'])
        for key in ('exterior_weight','shell_strength'):
            if settings[key]!=CONTOUR_DEFAULTS[key]:
                options[key]=settings[key]
    if settings['preserve_thin_features']:
        options['preserve_thin_features'] = True
        if settings['thin_strength']!=CONTOUR_DEFAULTS['thin_strength']:
            options['thin_strength']=settings['thin_strength']
    if settings['balance_regions']:
        options.update(balance_regions=True, region_count=settings['region_count'],
                       region_share=settings['region_share'])
    return options


def thin_feature_weights(mask, strength=1.25):
    """Boost foreground that survives only small disk openings."""
    if not mask.any():
        return np.ones(mask.shape)
    scale = mask.shape[1] / 320
    depth = distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]
    thickness = np.zeros(mask.shape)
    radii = sorted({max(1, round(scale * r)) for r in (2, 4, 6, 8, 12, 16)})
    for radius in radii:
        core = depth > radius
        if not core.any():
            break
        opened = distance_transform_edt(~core) <= radius
        thickness[opened] = radius / scale
    boost = np.clip((14 - thickness) / 12, 0, 1) * mask
    sigma = 1.2 * scale
    smooth = gaussian_filter(boost, sigma)
    coverage = gaussian_filter(mask.astype(float), sigma)
    return 1 + strength * mask * smooth / np.maximum(coverage, 1e-9)


def balance_region_weights(weights, mask, count, share):
    """Redistribute a percentage of foreground weight to the largest regions."""
    scale = mask.shape[1] / 320
    depth = distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]
    regions, cores = label(depth > max(1, round(scale)))
    if cores < 2:
        return
    queue = deque(zip(*np.nonzero(regions)))
    height, width = mask.shape
    while queue:
        y, x = queue.popleft()
        for row, col in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
            if 0 <= row < height and 0 <= col < width and mask[row,col] and regions[row,col] == 0:
                regions[row,col] = regions[y,x]
                queue.append((row,col))
    sizes = np.bincount(regions.ravel(), minlength=cores+1)
    minimum = max(1, round(12 * scale**2))
    selected = sorted((i for i in range(1,cores+1) if sizes[i]>=minimum),
                      key=lambda i: (-sizes[i],i))[:count]
    if len(selected) < 2:
        return
    fraction = share / 100
    budget = fraction * weights.sum() / len(selected)
    weights *= 1 - fraction
    for region in selected:
        weights[regions == region] += budget / sizes[region]


class ColorObjective:
    """Only interior RGB error and a small squared light-spill penalty."""
    def __init__(self,target,black_penalty=.15,*,preserve_contours=False,
                 contour_max_radius=20,contour_internal_radius=6,preserve_thin_features=False,
                 balance_regions=False,region_count=2,region_share=20,
                 exterior_weight=4.,shell_strength=.25,thin_strength=1.25):
        self.target=target.copy()
        self.mask=target.max(axis=3)>.025
        self.target[~self.mask]=0.
        self.weights=np.zeros(target.shape[:3])
        self.foreground_weights=np.zeros_like(self.weights)
        self.background_weights=np.zeros_like(self.weights)
        for k,mask in enumerate(self.mask):
            count=max(int(mask.sum()),1)
            if preserve_contours:
                scale=target.shape[2]/640
                outer=contour_max_radius*scale
                inner=contour_internal_radius*scale
                distance=distance_transform_edt(~mask) if mask.any() else np.full(mask.shape,outer)
                exterior=1+(exterior_weight-1)*np.minimum(distance/outer,1)
                depth=distance_transform_edt(mask)
                shell=np.where(depth<=inner,np.clip((inner+1-depth)/inner,0,1),0)
                self.foreground_weights[k]=mask*(1+shell_strength*shell)/count
                self.background_weights[k]=(~mask)*exterior/count
            else:
                self.foreground_weights[k]=mask/count
                self.background_weights[k]=black_penalty*(~mask)/count
            if preserve_thin_features:
                self.foreground_weights[k] *= thin_feature_weights(mask,thin_strength)
            if balance_regions:
                balance_region_weights(self.foreground_weights[k],mask,region_count,region_share)
        self.weights=self.foreground_weights+self.background_weights
        self.baseline=self.terms(np.zeros_like(target))['total']

    def terms(self,image):
        residual=self.target-image
        foreground=float(np.sum(self.foreground_weights[:,:,:,None]*residual**2))
        background=float(np.sum(self.background_weights[:,:,:,None]*image**2))
        return dict(interior_color=foreground,black_spill=background,total=foreground+background)


class StructureObjective:
    def __init__(self, target, color=1., edge=1.5, background=6., linear=.08, silhouette=3., edge_norm="area"):
        self.target=target.copy()
        self.mask=target.max(axis=3)>.025
        self.target[~self.mask]=0.
        self.weights=np.zeros(target.shape[:3])
        self.bg=np.zeros_like(self.weights)
        self.ex=np.zeros_like(self.weights)
        self.ey=np.zeros_like(self.weights)
        self.sw=np.zeros_like(self.weights)
        self.visibility=.12
        views,h,w,_=target.shape
        # Per-view normalization makes each camera and each region matter.
        for k in range(views):
            mask=self.mask[k]
            fg_count=max(int(mask.sum()),1)
            bg_count=max(int((~mask).sum()),1)
            self.weights[k]=color*mask/fg_count+background*(~mask)/bg_count
            self.bg[k]=background*linear*(~mask)/bg_count
            band=binary_dilation(mask,iterations=2)^binary_erosion(mask,iterations=2)
            self.sw[k]=silhouette*(mask/fg_count+4*(~mask)/bg_count+3*band/max(int(band.sum()),1))
            strength=1.+8.*band
            self.ex[k,:,:-1]=(strength[:,:-1]+strength[:,1:])/2
            self.ey[k,:-1,:]=(strength[:-1,:]+strength[1:,:])/2
            norm=self.ex[k].sum()+self.ey[k].sum()
            if edge_norm=='energy':
                dx=np.diff(self.target[k],axis=1);dy=np.diff(self.target[k],axis=0)
                norm=float(np.sum(self.ex[k,:,:-1,None]*dx**2)+np.sum(self.ey[k,:-1,:,None]*dy**2))
                norm=max(norm,1e-12)
            self.ex[k]*=edge/norm
            self.ey[k]*=edge/norm
        self.baseline=self.terms(np.zeros_like(target))['total']

    def terms(self,image):
        residual=self.target-image
        color=float(np.sum(self.weights[:,:,:,None]*residual**2))
        linear=float(np.sum(self.bg[:,:,:,None]*image))
        dx=np.diff(residual,axis=2);dy=np.diff(residual,axis=1)
        edges=float(np.sum(self.ex[:,:,:-1,None]*dx**2)+np.sum(self.ey[:,:-1,:,None]*dy**2))
        coverage=np.clip(image.max(axis=3)/self.visibility,0,1)
        shape=float(np.sum(self.sw*(coverage-self.mask)**2))
        return dict(weighted_rgb=color,edge=edges,background_linear=linear,silhouette=shape,total=color+edges+linear+shape)

    def effective_residual(self,residual):
        # Adjoint of forward differences; exact quadratic gradient, not a proxy.
        result=self.weights[:,:,:,None]*residual-.5*self.bg[:,:,:,None]
        dx=np.diff(residual,axis=2)*self.ex[:,:,:-1,None]
        dy=np.diff(residual,axis=1)*self.ey[:,:-1,:,None]
        result[:,:,:-1]-=dx;result[:,:,1:]+=dx
        result[:,:-1,:]-=dy;result[:,1:,:]+=dy
        return np.ascontiguousarray(result)


def quality_metrics(target,image):
    """Comparable diagnostics, independent of optimizer loss weights."""
    from scipy.ndimage import binary_dilation, binary_erosion
    result=[]
    for t,im in zip(target,image):
        mask=t.max(axis=2)>.025
        visible=im.max(axis=2)>.025
        border=mask^binary_erosion(mask)
        actual=visible^binary_erosion(visible)
        matched_actual=actual&binary_dilation(border,iterations=2)
        matched_target=border&binary_dilation(actual,iterations=2)
        precision=matched_actual.sum()/max(actual.sum(),1)
        recall=matched_target.sum()/max(border.sum(),1)
        result.append(dict(silhouette_iou=float((visible&mask).sum()/max((visible|mask).sum(),1)),
            contour_f1=float(2*precision*recall/max(precision+recall,1e-12)),
            foreground_mse=float(np.mean((t[mask]-im[mask])**2)),
            background_mean=float(np.mean(im[~mask])),
            background_spill_fraction=float(np.mean(visible[~mask]))))
    return result
