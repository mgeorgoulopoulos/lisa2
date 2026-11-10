"""Derived views and GIFs match checkpoint/camera semantics without UI input."""
import hashlib
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from lisa2.camera_motion import CameraMove,MIN_RADIUS,DURATION,render_camera
from lisa2.checkpoint import read_checkpoint
from lisa2.derived import checkpoint_views
from lisa2.geometry import BASES
from lisa2.gif_export import camera_frames,export_gif
from lisa2.train import save

root=Path('runs/derived-tests');root.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=root.resolve()) as temp:
    folder=Path(temp);checkpoint=folder/'mesh.npz'
    rng=np.random.default_rng(617)
    v=rng.normal(0,.15,(8,3,3));c=rng.uniform(0,.4,(8,3,3))
    save(checkpoint,v,c,7,[[0,0.],[7,.42]],{})
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    result=checkpoint_views(checkpoint)
    assert result['step']==7 and result['fitness']==.42 and len(result['views'])==4
    for i,view in enumerate(result['views']):
        expected=np.uint8(np.clip(render_camera(v,c,BASES[i]),0,1)*255)
        assert view.size==(640,480) and np.array_equal(np.asarray(view),expected)
    assert list(folder.iterdir())==[checkpoint],'UI previews wrote derived files'
    plan=list(camera_frames())
    assert sum(item[2] for item in plan)==20000
    for view in range(4):
        part=[item for item in plan if item[0]==view]
        assert part[0]==(view,0.,1400) and part[-1][1]==1.
        move=CameraMove(BASES[view],BASES[(view+1)%4]);_,radius=move.at(.5)
        assert abs(radius-MIN_RADIUS)<1e-12
    # Lower-resolution execution uses the identical path; native-size rendering
    # is already verified above and a real 640x480 export is checked separately.
    progress=[];path=folder/'dive.gif'
    metadata=export_gif(checkpoint,path,lambda done,total:progress.append((done,total)),fps=5,width=80)
    assert metadata['duration_ms']==20000 and metadata['checkpoint_step']==7
    assert progress[-1][0]==progress[-1][1]
    with Image.open(path) as gif:
        assert gif.size==(80,60) and gif.info['loop']==0 and gif.n_frames>4
        duration=0;first=None;last=None
        for i in range(gif.n_frames):
            gif.seek(i);duration+=gif.info['duration']
            last=gif.convert('RGB').copy()
            if first is None: first=last.copy()
        assert duration==20000 and np.array_equal(np.asarray(first),np.asarray(last))
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==digest
    assert not list(folder.glob('*.tmp'))
print('PASS: native checkpoint previews, no derived serialization, exact camera endpoints/dive, GIF timing/loop, immutable input and atomic output.')
