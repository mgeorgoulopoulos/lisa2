"""OBJ camera comments reproduce the actual four renderer projections."""
import json
import tempfile
from pathlib import Path
import numpy as np
from lisa2.geometry import BASES, project
from lisa2.gouraud import export_vertex_obj

base=Path('runs/obj-camera-tests');base.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=base.resolve()) as temp:
    path=Path(temp)/'camera.obj'
    vertices=np.array([[[-.2,.1,.3],[.1,.4,-.1],[.3,-.2,.2]]])
    colors=np.full_like(vertices,.2)
    images=['εικόνα.png','two.png','three.png','four.png']
    export_vertex_obj(path,vertices,colors,images)
    lines=path.read_text(encoding='ascii').splitlines()
    cameras=[json.loads(line[len('# camera '):]) for line in lines if line.startswith('# camera ')]
    assert len(cameras)==4 and all(line.startswith('#') for line in lines[:8])
    for i,camera in enumerate(cameras):
        assert camera['view']==i+1 and camera['image']==images[i]
        eye=np.array(camera['center']);target=np.array(camera['lookAt']);up=np.array(camera['up'])
        backward=(eye-target)/np.linalg.norm(eye-target)
        right=np.cross(up,backward);right/=np.linalg.norm(right)
        reconstructed=np.array([right,np.cross(backward,right),backward])
        assert np.allclose(reconstructed,BASES[i])
        local=(vertices[0]-eye)@reconstructed.T
        xy=local[:,:2]/(-local[:,2,None]*np.tan(np.deg2rad(camera['fovY_degrees']/2)))
        xy[:,0]/=camera['aspect']
        pixels=np.column_stack(((xy[:,0]+1)*320,(1-xy[:,1])*240))
        assert np.allclose(pixels,project(vertices[0],BASES[i],640,480))
    assert sum(line.startswith('v ') for line in lines)==3
    assert sum(line.startswith('f ') for line in lines)==1
print('PASS: four OBJ camera comments, Unicode filenames, exact renderer projection and mesh records')
