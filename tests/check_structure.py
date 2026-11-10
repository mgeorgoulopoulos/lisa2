import numpy as np
from lisa2.objective import StructureObjective
from lisa2.raster import render,optimal_color_structure
from lisa2.geometry import constrain

rng=np.random.default_rng(71)
target=np.zeros((4,36,48,3))
target[:,8:29,12:37]=[.7,.2,.1]
obj=StructureObjective(target)
for i in range(14):
    background=rng.uniform(0,.12,target.shape)
    if i==0: background[:]=0
    v=constrain(rng.normal(size=(3,3))*.6)
    residual=obj.target-background
    reference=rng.uniform(0,.3,3)
    color,gain=optimal_color_structure(v,obj.effective_residual(residual),obj.weights,
        obj.ex,obj.ey,background,obj.mask,obj.sw,obj.visibility,reference)
    actual=obj.terms(background)['total']-obj.terms(background+render([v],[color],48,36))['total']
    assert np.isclose(actual,gain,atol=1e-9), (actual,gain)
    assert gain>=-1e-10
# A colored halo that preserves every interior target pixel must still be worse.
perfect=obj.target.copy()
halo=perfect.copy();halo[:,5:32,9:40]+=.04
assert obj.terms(halo)['total']>obj.terms(perfect)['total']
# Same approximate global color content, with a displaced silhouette, is worse.
shift=np.roll(perfect,6,axis=2)
assert obj.terms(shift)['total']>obj.terms(perfect)['total']
print('PASS: exact combined-loss delta, zero/bright silhouette saturation, halo and shifted-outline penalties.')

# Nonlinear visibility must be able to improve even with a zero quadratic proposal.
shape_only=StructureObjective(target,color=0.,edge=0.,background=0.,silhouette=3.)
v=np.array([[.1,0.,0.],[-.1,.1,0.],[-.1,-.1,.1]])
blank=np.zeros_like(target)
color,gain=optimal_color_structure(v,shape_only.effective_residual(target),shape_only.weights,
    shape_only.ex,shape_only.ey,blank,shape_only.mask,shape_only.sw,shape_only.visibility,np.zeros(3))
assert gain>0 and color.max()>=.119
print('PASS: silhouette-only fitting can introduce visible triangles.')

# Correct black background earns no positive reward, even when most pixels are black.
blank=np.zeros_like(target)
assert np.isclose(1-obj.terms(blank)['total']/obj.baseline,0.)
partial=target.copy();partial[:,:,:24]=0
assert 0<1-obj.terms(partial)['total']/obj.baseline<1
assert np.isclose(1-obj.terms(target)['total']/obj.baseline,1.)
print('PASS: all-black scores zero; foreground must be reconstructed to earn fitness.')

energy=StructureObjective(target,edge_norm='energy')
v=constrain(rng.normal(size=(3,3))*.4)
color,gain=optimal_color_structure(v,energy.effective_residual(target),energy.weights,
    energy.ex,energy.ey,blank,energy.mask,energy.sw,energy.visibility,np.zeros(3))
actual=energy.terms(blank)['total']-energy.terms(render([v],[color],48,36))['total']
assert np.isclose(gain,actual,atol=1e-9)
print('PASS: optional energy-normalized edge term.')
