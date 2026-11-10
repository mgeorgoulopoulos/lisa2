"""Simultaneous scale-space RGB objective with exact bounded color fitting."""
import numpy as np
from numba import njit
from .pyramid import pool,pooled_weights
from .objective import ColorObjective
from .raster import projected,cross,bounds,inside
from .geometry import BASES


class MultiscaleObjective:
    factors=(1,4,16)
    coefficients=(.25,.35,.40)

    def __init__(self,target,black_penalty=.15):
        original=ColorObjective(target,black_penalty)
        self.target=original.target
        self.mask=original.mask
        self.targets=[pool(self.target,f) for f in self.factors]
        self.weights=[pooled_weights(original.weights,f)*c for f,c in zip(self.factors,self.coefficients)]
        self.baseline=self.terms(np.zeros_like(target))['total']

    def prepare(self,image):
        return [np.ascontiguousarray(t-pool(image,f)) for t,f in zip(self.targets,self.factors)]

    def terms(self,image):
        errors=[float(np.sum(w[:,:,:,None]*(t-pool(image,f))**2)) for t,w,f in zip(self.targets,self.weights,self.factors)]
        return dict(scale1=errors[0],scale4=errors[1],scale16=errors[2],total=sum(errors))

    def candidate(self,v,residuals):
        return optimal_color_pyramid(v,residuals[0],residuals[1],residuals[2],*self.weights)


@njit(cache=True)
def optimal_color_pyramid(v,r1,r4,r16,w1,w4,w16):
    views,h,w,_=r1.shape
    sums=np.zeros(3);denominator=0.
    for k in range(views):
        p=projected(v,BASES[k],w,h)
        if abs(cross(p[0],p[1],p[2,0],p[2,1]))<1e-8: continue
        x0,x1,y0,y1=bounds(p,w,h)
        if x1<x0 or y1<y0: continue
        counts4=np.zeros((y1//4-y0//4+1,x1//4-x0//4+1))
        counts16=np.zeros((y1//16-y0//16+1,x1//16-x0//16+1))
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                if inside(p,x+.5,y+.5):
                    denominator+=w1[k,y,x]
                    for c in range(3): sums[c]+=w1[k,y,x]*r1[k,y,x,c]
                    counts4[y//4-y0//4,x//4-x0//4]+=1
                    counts16[y//16-y0//16,x//16-x0//16]+=1
        for y in range(counts4.shape[0]):
            for x in range(counts4.shape[1]):
                coverage=counts4[y,x]/16.
                yy=y+y0//4;xx=x+x0//4
                denominator+=w4[k,yy,xx]*coverage**2
                for c in range(3): sums[c]+=w4[k,yy,xx]*coverage*r4[k,yy,xx,c]
        for y in range(counts16.shape[0]):
            for x in range(counts16.shape[1]):
                coverage=counts16[y,x]/256.
                yy=y+y0//16;xx=x+x0//16
                denominator+=w16[k,yy,xx]*coverage**2
                for c in range(3): sums[c]+=w16[k,yy,xx]*coverage*r16[k,yy,xx,c]
    color=np.zeros(3);gain=0.
    if denominator>0:
        for c in range(3):
            color[c]=max(0.,min(.4,sums[c]/denominator))
            gain+=2*color[c]*sums[c]-denominator*color[c]**2
    return color,gain
