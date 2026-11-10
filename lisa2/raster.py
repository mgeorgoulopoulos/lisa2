"""Two-sided flat additive rasterization, without depth, textures or view tricks."""
import numpy as np
from numba import njit
from .geometry import BASES, RADIUS, TAN_HALF, ASPECT


@njit(cache=True)
def projected(v, b, w, h):
    p=np.empty((3,2))
    for i in range(3):
        x=np.dot(v[i],b[0]); y=np.dot(v[i],b[1]); z=RADIUS-np.dot(v[i],b[2])
        p[i,0]=(1+x/z/TAN_HALF/ASPECT)*w/2
        p[i,1]=(1-y/z/TAN_HALF)*h/2
    return p


@njit(cache=True)
def cross(a,b,x,y):
    return (b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])


@njit(cache=True)
def bounds(p,w,h):
    return max(0,int(np.floor(p[:,0].min()))),min(w-1,int(np.ceil(p[:,0].max()))),max(0,int(np.floor(p[:,1].min()))),min(h-1,int(np.ceil(p[:,1].max())))


@njit(cache=True)
def inside(p,x,y):
    a=cross(p[0],p[1],x,y);b=cross(p[1],p[2],x,y);c=cross(p[2],p[0],x,y)
    return (a>=0 and b>=0 and c>=0) or (a<=0 and b<=0 and c<=0)


@njit(cache=True)
def optimal_color(v, residual, weights, bases=BASES):
    views,h,w,_=residual.shape
    sums=np.zeros(3);count=0.
    for k in range(views):
        p=projected(v,bases[k],w,h)
        if abs(cross(p[0],p[1],p[2,0],p[2,1]))<1e-8: continue
        x0,x1,y0,y1=bounds(p,w,h)
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                if inside(p,x+.5,y+.5):
                    weight=weights[k,y,x]
                    count+=weight
                    for c in range(3): sums[c]+=weight*residual[k,y,x,c]
    color=np.zeros(3)
    improvement=0.
    if count>0:
        for c in range(3):
            color[c]=max(0.,min(.4,sums[c]/count))
            improvement+=2*color[c]*sums[c]-count*color[c]*color[c]
    return color, improvement


@njit(cache=True)
def add_triangle(images,v,color,scale=1.,bases=BASES):
    views,h,w,_=images.shape
    for k in range(views):
        p=projected(v,bases[k],w,h)
        if abs(cross(p[0],p[1],p[2,0],p[2,1]))<1e-8: continue
        x0,x1,y0,y1=bounds(p,w,h)
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                if inside(p,x+.5,y+.5):
                    for c in range(3): images[k,y,x,c]+=scale*color[c]


@njit(cache=True)
def optimal_color_structure(v,effective,weights,ex,ey,image,mask,sw,visibility,reference,bases=BASES):
    views,h,w,_=effective.shape
    sums=np.zeros(3);denominator=0.
    for k in range(views):
        p=projected(v,bases[k],w,h)
        if abs(cross(p[0],p[1],p[2,0],p[2,1]))<1e-8: continue
        x0,x1,y0,y1=bounds(p,w,h)
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                if inside(p,x+.5,y+.5):
                    denominator+=weights[k,y,x]
                    for c in range(3): sums[c]+=effective[k,y,x,c]
                    # D(mask)^2 is nonzero only across a triangle boundary.
                    if x>0 and not inside(p,x-.5,y+.5): denominator+=ex[k,y,x-1]
                    if x+1<w and not inside(p,x+1.5,y+.5): denominator+=ex[k,y,x]
                    if y>0 and not inside(p,x+.5,y-.5): denominator+=ey[k,y-1,x]
                    if y+1<h and not inside(p,x+.5,y+1.5): denominator+=ey[k,y,x]
    color=np.zeros(3)
    if denominator>0:
        for c in range(3):
            color[c]=max(0.,min(.4,sums[c]/denominator))
    candidates=np.empty((8,3))
    factors=np.array([0.,.25,.5,1.,1.5,2.])
    gains=np.zeros(8)
    hue=color.copy()
    if hue.max()<1e-12: hue=reference.copy()
    if hue.max()<1e-12: hue=np.ones(3)
    hue=hue/max(hue.max(),1e-12)*visibility
    for j in range(8):
        for c in range(3):
            candidates[j,c]=hue[c] if j==7 else (reference[c] if j==6 else min(.4,color[c]*factors[j]))
            gains[j]+=2*candidates[j,c]*sums[c]-denominator*candidates[j,c]**2
    # Evaluate the actual nonlinear silhouette loss, not merely its gradient.
    for k in range(views):
        p=projected(v,bases[k],w,h)
        if abs(cross(p[0],p[1],p[2,0],p[2,1]))<1e-8: continue
        x0,x1,y0,y1=bounds(p,w,h)
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                if inside(p,x+.5,y+.5):
                    before=min(1.,max(0.,image[k,y,x].max()/visibility))
                    wanted=1. if mask[k,y,x] else 0.
                    for j in range(8):
                        bright=max(image[k,y,x,0]+candidates[j,0],image[k,y,x,1]+candidates[j,1],image[k,y,x,2]+candidates[j,2])
                        after=min(1.,max(0.,bright/visibility))
                        gains[j]+=sw[k,y,x]*((before-wanted)**2-(after-wanted)**2)
    best=int(np.argmax(gains))
    return candidates[best],gains[best]


def render(vertices,colors,width=320,height=240,bases=BASES):
    colors=np.asarray(colors)
    if colors.ndim==3:
        from .gouraud import render_gouraud
        return render_gouraud(np.asarray(vertices),colors,width,height,bases)
    images=np.zeros((len(bases),height,width,3),dtype=np.float64)
    for v,c in zip(vertices,colors): add_triangle(images,v,c,1.,bases)
    return images
