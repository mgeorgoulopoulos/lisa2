"""Snapshot GIF export using the exact established orbit/dive camera path."""
from pathlib import Path
import uuid
import json
import numpy as np
from PIL import Image
from .camera_motion import CameraMove,render_camera,DURATION,MIN_RADIUS
from .checkpoint import read_checkpoint,atomic_replace
from .geometry import BASES


def camera_frames(fps=20,hold=1.4):
    if fps<1 or fps>50 or hold<=0: raise ValueError('Invalid animation timing')
    count=round(DURATION*fps)
    for view in range(4):
        yield view,0.,round(hold*1000)
        for frame in range(1,count+1):
            # GIF stores centiseconds. Distribute rounding rather than drift.
            start=round((frame-1)*DURATION/count*100)
            end=round(frame*DURATION/count*100)
            yield view,frame/count,(end-start)*10


def export_gif(checkpoint,destination,progress=None,fps=20,width=None):
    destination=Path(destination)
    if destination.suffix.lower()!='.gif': raise ValueError('Choose a .gif filename')
    # Read one atomic checkpoint once; training may continue independently.
    data=read_checkpoint(checkpoint);vertices=data['vertices'];colors=data['colors']
    if width is None: width=int(json.loads(str(data['config'])).get('width',640))
    if width<4 or width%4: raise ValueError('Width must be a positive multiple of four')
    if colors.ndim==2: colors=np.repeat(colors[:,None,:],3,axis=1)
    moves=[CameraMove(BASES[i],BASES[(i+1)%4]) for i in range(4)]
    def image(view,t):
        basis,radius=moves[view].at(t)
        raw=render_camera(vertices,colors,basis,width,radius)
        return Image.fromarray(np.uint8(np.clip(raw,0,1)*255))
    # One palette for the entire animation avoids per-frame palette flicker.
    samples=Image.new('RGB',(160*5,120*4))
    for view in range(4):
        for j,t in enumerate((0.,.25,.5,.75,1.)):
            samples.paste(image(view,t).resize((160,120),Image.Resampling.LANCZOS),(160*j,120*view))
    learned=samples.quantize(colors=255,method=Image.Quantize.MEDIANCUT)
    palette=Image.new('P',(1,1));palette.putpalette(([0,0,0]+learned.getpalette()[:255*3])[:768])
    plan=list(camera_frames(fps));frames=[];durations=[]
    for index,(view,t,duration) in enumerate(plan):
        frames.append(image(view,t).quantize(palette=palette,dither=Image.Dither.NONE))
        durations.append(duration)
        if progress: progress(index+1,len(plan))
    temporary=destination.with_name('.'+destination.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        frames[0].save(temporary,format='GIF',save_all=True,append_images=frames[1:],
            duration=durations,loop=0,optimize=False,disposal=2,background=0)
        atomic_replace(temporary,destination)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(path=str(destination),checkpoint_step=int(data['step']),width=width,height=width*3//4,
        duration_ms=sum(durations),fps=fps,minimum_radius=MIN_RADIUS,transition_seconds=DURATION,hold_seconds=1.4)
