import numpy as np
from lisa2.pyramid import decompose
from lisa2.multiscale import MultiscaleObjective
from lisa2.objective import ColorObjective
from lisa2.geometry import constrain
from lisa2.raster import render

rng=np.random.default_rng(193)
target=np.zeros((4,48,64,3));target[:,10:39,15:51]=rng.uniform(.1,.9,(4,29,36,3))
bands,levels=decompose(target,(8.,4.,2.,1.,0.))
assert np.max(np.abs(bands.sum(axis=0)-target))<1e-14
assert np.max(np.abs(np.cumsum(bands,axis=0)-levels))<1e-14
assert bands[1:].min()<0, 'Detail bands must remain signed'
assert np.array_equal(levels[-1],target)
objective=MultiscaleObjective(target)
for _ in range(10):
    base=rng.uniform(0,.15,target.shape);vertices=constrain(rng.normal(size=(3,3))*.5)
    color,gain=objective.candidate(vertices,objective.prepare(base))
    actual=objective.terms(base)['total']-objective.terms(base+render([vertices],[color],64,48))['total']
    assert np.isclose(gain,actual,atol=1e-9), (gain,actual)
assert np.isclose(1-objective.terms(np.zeros_like(target))['total']/objective.baseline,0.)
print('PASS: exact signed pyramid reconstruction, cumulative levels, multiscale/full-image loss equivalence, blank score zero.')
