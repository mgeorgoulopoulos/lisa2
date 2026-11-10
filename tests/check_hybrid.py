import numpy as np
from scipy.optimize import lsq_linear
from lisa2.hybrid_gouraud import bounded_rgb,local_fit,add
from lisa2.raster import render
from lisa2.geometry import BASES
from lisa2.objective import ColorObjective
rng=np.random.default_rng(92)
for trial in range(35):
 A=rng.normal(size=(30,3));b=rng.normal(size=(30,3))
 if trial==0: A[:]=0
 if trial==1: A[:,2]=A[:,1]
 G=A.T@A;H=A.T@b;c,g=bounded_rgb(G,H)
 reference=np.column_stack([lsq_linear(A,b[:,k],bounds=(0,.4),tol=1e-12).x for k in range(3)])
 assert np.allclose(np.sum((A@c-b)**2),np.sum((A@reference-b)**2),atol=1e-8)
 assert np.allclose(g,np.sum(b*b)-np.sum((A@c-b)**2),atol=1e-8)
v=rng.normal(0,.25,(6,3,3));colors=rng.uniform(0,.4,(6,3,3));image=render(v,colors,64,48)
objective=ColorObjective(rng.uniform(0,.5,image.shape));current=image.copy();add(current,v[2],colors[2],-1)
assert np.allclose(current,render(np.delete(v,2,0),np.delete(colors,2,0),64,48),atol=1e-12)
candidate=v[2]+rng.normal(0,.04,(3,3));residual=np.ascontiguousarray(objective.target-current)
c,gain=local_fit(candidate,residual,objective.weights);before=objective.terms(current)['total'];add(current,candidate,c)
assert np.allclose(before-objective.terms(current)['total'],gain,atol=1e-11)
assert np.allclose(current,render(np.concatenate([np.delete(v,2,0),candidate[None]]),np.concatenate([np.delete(colors,2,0),c[None]]),64,48),atol=1e-12)
print('PASS: local bounded solver matches SciPy including singular cases; incremental replacement and profiled gain match full physical renders.')
