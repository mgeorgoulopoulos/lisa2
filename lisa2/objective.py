"""Separate, normalized interior-color, edge and black-background losses."""
import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion


class ColorObjective:
    """Only interior RGB error and a small squared light-spill penalty."""
    def __init__(self,target,black_penalty=.15):
        self.target=target.copy()
        self.mask=target.max(axis=3)>.025
        self.target[~self.mask]=0.
        self.weights=np.zeros(target.shape[:3])
        self.foreground_weights=np.zeros_like(self.weights)
        self.background_weights=np.zeros_like(self.weights)
        for k,mask in enumerate(self.mask):
            count=max(int(mask.sum()),1)
            self.foreground_weights[k]=mask/count
            self.background_weights[k]=black_penalty*(~mask)/count
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
