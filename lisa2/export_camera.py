"""Export the exact preview camera path as a reviewable movie, GIF and index."""
import argparse,json,shutil,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from .camera_motion import CameraMove,render_camera,DURATION,MIN_RADIUS
from .geometry import BASES
from .checkpoint import read_checkpoint


def export(run,ffmpeg):
    run=Path(run);d=read_checkpoint(run/'best.npz');v=d['vertices'];c=d['colors'];fps=24
    movie=run/'camera-dive.mp4'
    process=subprocess.Popen([str(ffmpeg),'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','640x480','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(movie)],stdin=subprocess.PIPE)
    frames=[];index=[];sheet=Image.new('RGB',(1440,816),(12,14,20));draw=ImageDraw.Draw(sheet)
    try:
        for view in range(4):
            move=CameraMove(BASES[view],BASES[(view+1)%4])
            for t in [0.] * round(1.4*fps)+list(np.linspace(0,1,round(DURATION*fps))):
                basis,radius=move.at(t);raw=render_camera(v,c,basis,640,radius)
                rgb=np.uint8(np.clip(raw,0,1)*255);process.stdin.write(rgb.tobytes())
                im=Image.fromarray(rgb);frames.append(im.resize((320,240)))
                index.append(dict(frame=len(index),seconds=len(index)/fps,source_view=view+1,target_view=(view+1)%4+1,transition_t=float(t),radius=float(radius)))
            for col,t in enumerate([0.,.30,.42,.50,.65,1.]):
                basis,radius=move.at(t);im=Image.fromarray(np.uint8(np.clip(render_camera(v,c,basis,640,radius),0,1)*255))
                sheet.paste(im.resize((240,180)),(240*col,204*view+24));draw.text((240*col+5,204*view+5),f'{view+1} -> {(view+1)%4+1} / t={t:.2f}',fill='white')
    finally:
        process.stdin.close();result=process.wait()
    if result: raise RuntimeError(f'FFmpeg failed: {result}')
    frames[0].save(run/'camera-dive.gif',save_all=True,append_images=frames[1:],duration=round(1000/fps),loop=0)
    sheet.save(run/'camera-dive-frames.png')
    (run/'camera-dive-index.json').write_text(json.dumps(dict(fps=fps,duration_seconds=len(index)/fps,transition_seconds=DURATION,hold_seconds=1.4,minimum_radius=MIN_RADIUS,frames=index),indent=2),encoding='utf-8')
    print('Exported',movie,len(index),'frames',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',default='runs/hybrid-gouraud');p.add_argument('--ffmpeg',default=shutil.which('ffmpeg'))
    a=p.parse_args()
    if not a.ffmpeg: p.error('Provide --ffmpeg PATH or put ffmpeg on PATH')
    export(a.run,a.ffmpeg)

if __name__=='__main__': main()
