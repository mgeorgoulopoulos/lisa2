import numpy as np
from lisa2.geometry import BASES,RADIUS
from lisa2.camera_motion import CameraMove,clipped_mesh,render_camera,NEAR
from lisa2.raster import render
rng=np.random.default_rng(17);v=rng.normal(0,.3,(8,3,3));c=rng.uniform(0,.4,(8,3,3))
move=CameraMove(BASES[0],BASES[1])
for t,expected in [(0,BASES[0]),(1,BASES[1])]:
 b,r=move.at(t);assert np.array_equal(b,expected) and r==RADIUS
 assert np.array_equal(render_camera(v,c,b,64,r),render(v,c,64,48,b[None])[0])
for t in np.linspace(0,1,101):
 b,r=move.at(t);assert np.allclose(b@b.T,np.eye(3),atol=1e-12) and np.linalg.det(b)>0
 assert .95-1e-12<=r<=RADIUS+1e-12
b,r=move.at(.47);retarget=CameraMove(b,BASES[3],r);bb,rr=retarget.at(0)
assert np.array_equal(bb,b) and rr==r
# Triangles crossing the eye plane must be clipped, never projected backwards.
v=np.array([[[-.3,-.2,1.2],[.4,-.2,.1],[0,.4,.2]]]);c=rng.uniform(0,.4,(1,3,3));b=np.eye(3)
a,colors=clipped_mesh(v,c,b,.8)
assert len(a)==2 and np.all(RADIUS-a[:,:,2]>=NEAR-1e-12)
assert colors.min()>=0 and colors.max()<=.4
actual=render_camera(v,c,b,64,.8);reverse=render_camera(v[:,[0,2,1]].copy(),c[:,[0,2,1]].copy(),b,64,.8)
assert np.isfinite(actual).all() and np.any(actual>0) and np.allclose(actual,reverse,atol=1e-10)
assert not render_camera(np.array([[[-.2,-.2,1.2],[.2,-.2,1.3],[0,.2,1.4]]]),c,b,64,.8).any()
print('PASS: exact original endpoints; bounded smooth orbit/dolly; continuous retarget; near-plane crossing and behind-eye rejection; two-sided clipped RGB rendering.')
