"""Hard-raster finite-difference joint position/RGB local refinement.

The first RGB fit is supplied by the caller. A bounded linearized joint step
is only a proposal; exact profiled hard-raster gains decide acceptance.
"""
import numpy as np
from numba import njit
from scipy.optimize import lsq_linear
from .geometry import BASES, constrain, project
from .gouraud import footprint
from .raster import projected, cross, inside


@njit(cache=True)
def sampled_basis(vertices, views, rows, width, height):
    result=np.zeros((len(rows),3))
    for k in range(4):
        p=projected(vertices,BASES[k],width,height)
        area=cross(p[0],p[1],p[2,0],p[2,1])
        if abs(area)<1e-8: continue
        for n in range(len(rows)):
            if views[n]!=k: continue
            x=rows[n]%width+.5;y=rows[n]//width+.5
            if inside(p,x,y):
                a=cross(p[1],p[2],x,y)/area
                b=cross(p[2],p[0],x,y)/area
                result[n,0]=a;result[n,1]=b;result[n,2]=1-a-b
    return result


def refine(vertices, colors, gain, residual, weights, radius=2., difference=1., steps=1):
    # Import here avoids a cycle with the hybrid driver.
    from .hybrid_gouraud import local_fit
    v=vertices.copy();c=colors.copy();best=float(gain)
    height,width=weights.shape[1:]
    accepted=0;trials=0;linearizations=0;geometry_probes=0
    for iteration in range(steps):
        # Convert world-space perturbations to a maximum displacement in any
        # training view. Bounds on the joint proposal are checked again below.
        pixel_scales=np.empty(9)
        for axis in range(9):
            delta=np.zeros((3,3));delta.flat[axis]=1e-5
            pixel_scales[axis]=max(np.linalg.norm(project(v+delta,b,width,height)-project(v,b,width,height),axis=1).max()/1e-5 for b in BASES)
        unit=1/np.maximum(pixel_scales,1e-8)
        probes=[]
        for axis in range(9):
            delta=np.zeros((3,3));delta.flat[axis]=unit[axis]*difference
            probes.extend([constrain(v+delta),constrain(v-delta)])
        geometry_probes+=18
        # Union includes pixels newly covered by finite differences, so moving
        # edges contribute to the local model as well as interior color changes.
        views=[];rows=[]
        for k,b in enumerate(BASES):
            union=np.unique(np.concatenate([footprint(p,b,width,height)[0] for p in [v,*probes]]))
            views.extend([k]*len(union));rows.extend(union)
        views=np.asarray(views,dtype=np.int64);rows=np.asarray(rows,dtype=np.int64)
        if not len(rows): break
        a=sampled_basis(v,views,rows,width,height)
        root=np.sqrt(weights.reshape(4,-1)[views,rows])
        target=residual.reshape(4,-1,3)[views,rows]
        image=a@c
        jac=np.zeros((len(rows)*3,18))
        for axis in range(9):
            plus=sampled_basis(probes[2*axis],views,rows,width,height)@c
            minus=sampled_basis(probes[2*axis+1],views,rows,width,height)@c
            jac[:,axis]=((plus-minus)*root[:,None]/(2*difference)).ravel()
        for vertex in range(3):
            for channel in range(3):
                jac[channel::3,9+vertex*3+channel]=a[:,vertex]*root
        rhs=((target-image)*root[:,None]).ravel()
        # Variables 0:9 are pixel-scaled xyz increments, 9:18 are RGB increments.
        lower=np.r_[np.full(9,-radius),-c.ravel()]
        upper=np.r_[np.full(9,radius),.4-c.ravel()]
        result=lsq_linear(jac,rhs,bounds=(lower,upper),method='bvls',tol=1e-5,max_iter=30)
        linearizations+=1
        if not np.all(np.isfinite(result.x)): break
        direction=(result.x[:9]*unit).reshape(3,3)
        proposal=constrain(v+direction)
        displacement=max(np.linalg.norm(project(proposal,b,width,height)-project(v,b,width,height),axis=1).max() for b in BASES)
        if displacement>radius: direction*=radius/displacement
        improved=False
        for fraction in (1.,.5,.25):
            candidate=constrain(v+fraction*direction)
            # Refit RGB exactly at the proposed geometry, dominating the joint
            # linear color prediction while preserving the two-pass structure.
            new_c,new_gain=local_fit(candidate,residual,weights);trials+=1
            if new_gain>best+1e-14:
                v=candidate;c=new_c;best=float(new_gain);accepted+=1;improved=True
                break
        if not improved: break
    return v,c,best,dict(accepted=accepted,trials=trials,linearizations=linearizations,geometry_probes=geometry_probes)
