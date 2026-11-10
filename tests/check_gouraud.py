import numpy as np
from scipy.sparse import coo_matrix
from lisa2.raster import render
from lisa2.gouraud import footprint
from lisa2.geometry import BASES

rng=np.random.default_rng(47)
v=rng.normal(0,.25,(5,3,3));flat=rng.uniform(0,.2,(5,3))
constant=np.repeat(flat[:,None,:],3,axis=1)
assert np.allclose(render(v,flat,64,48),render(v,constant,64,48),atol=1e-12)
colors=rng.uniform(0,.4,(5,3,3))
before=render(v,colors,64,48)
reverse=render(v[:,[0,2,1]],colors[:,[0,2,1]],64,48)
assert np.allclose(before,reverse,atol=1e-12), 'Winding must never cull a triangle'
rows=[];cols=[];values=[]
for k,basis in enumerate(BASES):
    for i,triangle in enumerate(v):
        r,a=footprint(triangle,basis,64,48)
        rows.append(np.repeat(r+k*64*48,3));cols.append(np.tile(np.arange(3)+i*3,len(r)));values.append(a.ravel())
A=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),shape=(4*64*48,15)).tocsr()
assert np.allclose((A@colors.reshape(-1,3)).reshape(before.shape),before,atol=1e-12)
assert np.any(before[0]>0) and np.any(before[1]>0) and np.any(before[2]>0) and np.any(before[3]>0)
print('PASS: flat-color equivalence, two-sided winding invariance, all four cameras, exact global color design matrix.')
