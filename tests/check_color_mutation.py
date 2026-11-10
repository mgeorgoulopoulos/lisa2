import numpy as np
from lisa2.objective import ColorObjective
from lisa2.mutation import outside_any_silhouette,adaptive_mutation
from lisa2.raster import optimal_color,render
from lisa2.geometry import constrain

rng=np.random.default_rng(33)
target=np.zeros((4,36,48,3));target[:,8:28,12:36]=[.6,.3,.2]
obj=ColorObjective(target,.15)
assert set(obj.terms(target))=={'interior_color','black_spill','total'}
assert obj.terms(target)['total']==0
assert 1-obj.terms(np.zeros_like(target))['total']/obj.baseline==0
fg=target.copy();fg[0,12,20]+=.2
bg=target.copy();bg[0,1,1]+=.2
assert np.isclose(obj.terms(bg)['total']/obj.terms(fg)['total'],.15)
for _ in range(8):
    base=rng.uniform(0,.1,target.shape);v=constrain(rng.normal(size=(3,3))*.5)
    color,gain=optimal_color(v,obj.target-base,obj.weights)
    delta=obj.terms(base)['total']-obj.terms(base+render([v],[color],48,36))['total']
    assert np.isclose(delta,gain,atol=1e-9)
masks=np.ones((4,36,48),dtype=bool)
assert not outside_any_silhouette(np.zeros((3,3)),masks).any()
masks[2,18,24]=False
assert outside_any_silhouette(np.zeros((3,3)),masks).all(), 'One failing view must be sufficient'
changed=np.zeros(3);squared=np.zeros(3)
parent=np.zeros(9)
for _ in range(5000):
    individual=rng.normal(size=9).tolist()
    adaptive_mutation(individual,parent,np.array([False,True,False]),rng)
    values=np.array(individual).reshape(3,3)
    changed+=np.any(values!=0,axis=1);squared+=(values**2).sum(axis=1)
rates=changed/5000
assert .20<rates[0]<.30 and .85<rates[1]<.95
assert squared[1]>10*squared[0]
print('PASS: exactly two loss terms, black scores zero, small 0.15 spill penalty, exact RGB fit, any-view mutation trigger and higher measured mutation rates.')

# Extra correct black padding cannot increase fitness or dilute an existing spill.
padded_target=np.pad(target,((0,0),(8,8),(10,10),(0,0)))
padded_image=np.pad(bg,((0,0),(8,8),(10,10),(0,0)))
padded=ColorObjective(padded_target,.15)
assert np.isclose(padded.terms(padded_image)['total'],obj.terms(bg)['total'])
assert np.isclose(padded.baseline,obj.baseline)
print('PASS: adding black padding does not earn score or dilute light-spill errors.')
