"""Check physical acceptance, sampled raster and per-step projected bounds."""
import numpy as np
from lisa2.geometry import BASES,project,constrain
from lisa2.gouraud import render_gouraud
from lisa2.hybrid_gouraud import local_fit,add
from lisa2.local_refine import refine,sampled_basis
from lisa2.objective import ColorObjective

rng=np.random.default_rng(413)
for trial in range(6):
    target_v=constrain(rng.normal(0,.3,(3,3)))
    target_c=rng.uniform(.02,.35,(3,3))
    target=render_gouraud(target_v[None],target_c[None],80,60,BASES)
    obj=ColorObjective(target)
    v=constrain(target_v+rng.normal(0,.025,(3,3)))
    c,g=local_fit(v,obj.target,obj.weights)
    views=np.repeat(np.arange(4),80*60);rows=np.tile(np.arange(80*60),4)
    sampled=(sampled_basis(v,views,rows,80,60)@c).reshape(4,60,80,3)
    assert np.allclose(sampled,render_gouraud(v[None],c[None],80,60,BASES),atol=1e-12)
    nv,nc,ng,stats=refine(v,c,g,obj.target,obj.weights,2.,1.,1)
    assert ng>=g and np.max(nc)<=.4 and np.min(nc)>=0
    assert np.max(np.linalg.norm(nv,axis=1))<=1+1e-12
    assert max(np.linalg.norm(project(nv,b,80,60)-project(v,b,80,60),axis=1).max() for b in BASES)<=2.00001
    physical=obj.terms(render_gouraud(nv[None],nc[None],80,60,BASES))['total']
    assert np.isclose(obj.baseline-physical,ng,atol=1e-11)
    assert physical<=obj.terms(sampled)['total']+1e-12
print('PASS: sampled raster matches full raster; accepted exact gains, RGB/sphere bounds and projected trust radii verified.')
