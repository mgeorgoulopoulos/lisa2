"""Verify the pilot's ranking is exactly the existing physical removal cost."""
import numpy as np
from lisa2.geometry import BASES
from lisa2.gouraud import render_gouraud
from lisa2.hybrid_gouraud import add,local_fit
from lisa2.objective import ColorObjective
from lisa2.replacement_trial import marginal_utilities,residual_centers,new_triangle

rng=np.random.default_rng(98)
vertices=rng.normal(0,.2,(6,3,3));colors=rng.uniform(0,.4,(6,3,3))
image=render_gouraud(vertices,colors,64,48,BASES)
target=render_gouraud(vertices+rng.normal(0,.02,vertices.shape),colors,64,48,BASES)
obj=ColorObjective(target);utilities=marginal_utilities(vertices,colors,image,obj)
initial=obj.terms(image)['total']
for i in range(len(vertices)):
    without=image.copy();add(without,vertices[i],colors[i],-1.)
    assert np.isclose(utilities[i],obj.terms(without)['total']-initial,atol=1e-12)
residual=np.ascontiguousarray(obj.target-image)
centers,p=residual_centers(residual,obj.weights,rng,count=256)
assert np.max(np.linalg.norm(centers,axis=1))<=1 and np.min(p)>=0 and np.isclose(p.sum(),1)
for _ in range(20):
    v=new_triangle(centers,p,rng);c,g=local_fit(v,residual,obj.weights)
    assert np.max(np.linalg.norm(v,axis=1))<=1+1e-12 and c.min()>=0 and c.max()<=.4
print('PASS: exact physical marginal ranking, residual proposals, unit sphere and shared bounded RGB.')
