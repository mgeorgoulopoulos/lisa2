"""Independent geometry and objective checks, runnable without pytest."""
import numpy as np
from lisa2.geometry import BASES,DIRECTIONS,RADIUS,TAN_HALF,ASPECT,project,constrain
from lisa2.raster import render,optimal_color
from lisa2.preview import interpolator
from lisa2.targets import load
from PIL import Image
from tempfile import TemporaryDirectory
from pathlib import Path

assert np.allclose(DIRECTIONS @ DIRECTIONS.T, np.eye(4)*4/3-np.ones((4,4))/3)
for b in BASES:
    assert np.allclose(b @ b.T,np.eye(3)) and np.linalg.det(b)>.999
    assert np.allclose(project(np.zeros((1,3)),b,320,240),[[160,120]])
rng=np.random.default_rng(10)
sphere=rng.normal(size=(20000,3));sphere/=np.linalg.norm(sphere,axis=1)[:,None]
for b in BASES:
    p=project(sphere,b,320,240)
    assert np.all(p>0) and np.all(p[:,0]<320) and np.all(p[:,1]<240)
for a in BASES:
    for b in BASES:
        s=interpolator(a,b)
        assert np.allclose(s(0).as_matrix().T,a)
        assert np.allclose(s(1).as_matrix().T,b)
        mid=s(.5).as_matrix().T
        assert np.allclose(mid @ mid.T,np.eye(3))
for _ in range(10):
    v=constrain(rng.normal(size=(3,3))*.45)
    target=rng.uniform(0,.2,(4,36,48,3))
    background=rng.uniform(0,.1,target.shape)
    weights=rng.uniform(.5,3,target.shape[:3])
    color,gain=optimal_color(v,target-background,weights)
    before=np.sum(weights[:,:,:,None]*(target-background)**2)
    after=np.sum(weights[:,:,:,None]*(target-background-render([v],[color],48,36))**2)
    assert np.isclose(before-after,gain,atol=1e-8), (before-after,gain)
    assert gain>=-1e-10
with TemporaryDirectory() as tmp:
    p=Path(tmp)/'test.png'
    Image.new('RGB',(320,240),(255,80,0)).save(p)
    large=load([p]*4,640,480)
    assert np.allclose(large[:,:,:,0],1), 'Small targets must scale up, not occupy a smaller central rectangle'
print('PASS: tetrahedron, frusta, smooth endpoints, incremental fitness, target upscaling.')
