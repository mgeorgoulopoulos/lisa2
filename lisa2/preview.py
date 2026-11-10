import argparse
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy.spatial.transform import Rotation, Slerp
from .geometry import BASES,RADIUS
from .raster import render
from .train import export_obj
from .checkpoint import read_checkpoint
from .camera_motion import CameraMove,render_camera,DURATION,MIN_RADIUS


def image_for(vertices,colors,basis,width=640,radius=RADIUS):
    rgb=render_camera(vertices,colors,basis,width,radius)
    return Image.fromarray(np.uint8(np.clip(rgb,0,1)*255))


def interpolator(start,end):
    return Slerp([0.,1.],Rotation.from_matrix(np.array([start.T,end.T])))


def export_preview(run):
    run=Path(run);data=read_checkpoint(run/'best.npz')
    v=data['vertices'];c=data['colors'];config=json.loads(str(data['config']))
    canvas=Image.new('RGB',(2560,992),(12,14,20));d=ImageDraw.Draw(canvas)
    for i in range(4):
        target=ImageOps.contain(Image.open(config['images'][i]).convert('RGB'),(640,480),Image.Resampling.LANCZOS)
        canvas.paste(target,(i*640+(640-target.width)//2,20))
        image=image_for(v,c,BASES[i]);image.save(run/f'view_{i+1}.png')
        canvas.paste(image,(i*640,512))
        d.text((i*640+8,3),f'{i+1}: target',fill='white')
        d.text((i*640+8,494),'same evolved mesh',fill='white')
    canvas.save(run/'comparison.png')
    frames=[]
    for i in range(4):
        transition=CameraMove(BASES[i],BASES[(i+1)%4])
        for t in [0.]*17+list(np.linspace(0,1,43)):
            b,radius=transition.at(t)
            frames.append(image_for(v,c,b,radius=radius))
    frames[0].save(run/'orbit.gif',save_all=True,append_images=frames[1:],duration=83,loop=0)
    progress=json.loads((run/'progress.json').read_text())
    plot=Image.new('RGB',(800,360),(16,20,29));d=ImageDraw.Draw(plot)
    history=np.array(progress['history'])
    if len(history)>1:
        points=[(40+720*x/max(history[-1,0],1),320-260*y) for x,y in history]
        d.line(points,fill=(255,183,73),width=3)
    d.text((40,12),'Fitness = 1 - weighted reconstruction error / black baseline',fill='white')
    d.text((40,338),'Accepted triangle updates (fixed resolution, all four views)',fill='white')
    plot.save(run/'fitness.png')
    # Modern CPU triangle/pixel workload only; never claim retro FPS from this.
    began=time.perf_counter()
    for _ in range(10): image_for(v,c,BASES[0])
    summary=dict(triangles=len(v),active_triangles=int(np.sum(c.reshape(len(c),-1).max(axis=1)>1e-5)),
                 vertices=3*len(v),width=640,height=480,
                 contemporary_cpu_render_ms=(time.perf_counter()-began)*100,
                 occupied_fraction=[float(np.mean(np.asarray(Image.open(run/f'view_{i+1}.png')).max(axis=2)>8)) for i in range(4)],
                 fitness=progress['fitness'],retro_fps_verified=False)
    (run/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


def view(run,read_only=False,smoke_test=False):
    import pygame
    import subprocess
    import shutil
    import sys
    pygame.init()
    screen=pygame.display.set_mode((960,480))
    pygame.display.set_caption(f'Lisa2 / {Path(run).name} - 1 2 3 4')
    font=pygame.font.SysFont('consolas',17)
    small=pygame.font.SysFont('consolas',14)
    clock=pygame.time.Clock();run=Path(run)
    data=read_checkpoint(run/'best.npz');v=data['vertices'];c=data['colors']
    view_config=json.loads(str(data['config']))
    read_only=read_only or view_config.get('experiment_method')=='project'
    current=BASES[0].copy();radius=RADIUS;transition=None;began=0.;selected=0
    autoplay=False;dive=True;next_move=0.
    last_reload=0.;stamp=0;progress={};dropped=[];process=None
    def text(s,y,color=(220,225,235),tiny=False):
        screen.blit((small if tiny else font).render(s,True,color),(656,y))
    alive=True
    while alive:
        now=time.perf_counter()
        for event in pygame.event.get():
            if event.type==pygame.QUIT: alive=False
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE: alive=False
                if event.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4):
                    selected=event.key-pygame.K_1
                    transition=CameraMove(current,BASES[selected],radius,MIN_RADIUS if dive else RADIUS);began=now
                if event.key==pygame.K_a:
                    autoplay=not autoplay;next_move=now+1.4
                if event.key==pygame.K_d: dive=not dive
                if event.key==pygame.K_e: export_obj(run/'model.obj',v,c)
                if event.key==pygame.K_SPACE and not read_only:
                    control=run/'control.txt'
                    if progress.get('status') in ('running','paused'):
                        control.write_text('run' if progress['status']=='paused' else 'pause')
                    elif process is None or process.poll() is not None:
                        cfg=json.loads(str(read_checkpoint(run/'best.npz')['config']))
                        if (run/'frozen.flag').exists():
                            fork=Path('runs')/time.strftime('continue-%Y%m%d-%H%M%S')
                            fork.mkdir(parents=True,exist_ok=False)
                            shutil.copy2(run/'best.npz',fork/'best.npz')
                            shutil.copy2(run/'progress.json',fork/'progress.json')
                            run=fork;control=run/'control.txt';stamp=0
                        control.write_text('run')
                        cmd=[sys.executable,'-m','lisa2.train','--resume','--output',str(run),
                             '--triangles',str(cfg['triangles']),'--width',str(cfg['width']),
                             '--rounds',str(cfg['rounds']+1),'--seed',str(cfg['seed']),
                             '--generations',str(cfg['generations']),'--population',str(cfg['population']),
                             '--objective',cfg.get('objective','rgb'),
                             '--mutation',cfg.get('mutation','uniform'),
                             '--mutation-space',cfg.get('mutation_space','world'),
                             '--black-penalty',str(cfg.get('black_penalty',.15)),
                             '--edge-norm',cfg.get('edge_norm','area'),
                             '--color-weight',str(cfg.get('color_weight',1.)),
                             '--edge-weight',str(cfg.get('edge_weight',1.5)),
                             '--background-weight',str(cfg.get('background_weight',6.)),
                             '--background-linear',str(cfg.get('background_linear',.08)),
                             '--silhouette-weight',str(cfg.get('silhouette_weight',3.)),
                             '--images',*cfg['images']]
                        method=cfg.get('experiment_method')
                        if method in ('curriculum','multiscale','control'):
                            cmd=[sys.executable,'-m','lisa2.experiments','--resume','--output',str(run),'--extra-rounds','1']
                        elif method=='hybrid-gouraud':
                            cmd=[sys.executable,'-m','lisa2.hybrid_gouraud','--resume','--output',str(run),'--extra-passes','1']
                        elif method=='gradient':
                            cmd=[cfg.get('training_python',sys.executable),'-m','lisa2.gradient_trial','--resume','--run',str(run),'--extra-steps','100']
                        elif method=='gouraud':
                            # The fixed-geometry bounded color fit has already converged.
                            # Never route vertex colors into the flat-color CMA trainer.
                            continue
                        process=subprocess.Popen(cmd,stdout=(run/'viewer-training.log').open('w'),stderr=subprocess.STDOUT)
            if event.type==pygame.DROPFILE and not read_only:
                try:
                    with Image.open(event.file) as im: im.verify()
                    dropped.append(event.file);dropped=dropped[-4:]
                except Exception: pass
                if len(dropped)==4:
                    # New targets always create a distinct run, never overwrite the experiment.
                    new=Path('runs')/time.strftime('custom-%Y%m%d-%H%M%S')
                    if process is None or process.poll() is not None:
                        process=subprocess.Popen([sys.executable,'-m','lisa2.train','--output',str(new),'--images',*dropped],
                                                 stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
                        run=new;progress={};stamp=0
        if autoplay and transition is None and now>=next_move:
            selected=(selected+1)%4
            transition=CameraMove(current,BASES[selected],radius,MIN_RADIUS if dive else RADIUS);began=now
        if transition is not None:
            t=min(1.,(now-began)/DURATION)
            current,radius=transition.at(t)
            if t==1: transition=None;next_move=now+1.4
        if now-last_reload>.5:
            last_reload=now
            try:
                progress=json.loads((run/'progress.json').read_text())
                updated=(run/'best.npz').stat().st_mtime_ns
                if updated!=stamp:
                    data=read_checkpoint(run/'best.npz');v=data['vertices'];c=data['colors'];view_config=json.loads(str(data['config']));stamp=updated
            except (OSError,ValueError): pass
        native_width=int(view_config.get('width',640)) if read_only else 640
        rgb=np.asarray(image_for(v,c,current,width=native_width,radius=radius))
        surface=pygame.surfarray.make_surface(np.swapaxes(rgb,0,1))
        screen.fill((16,20,29));screen.blit(pygame.transform.scale(surface,(640,480)),(0,0))
        text('LISA2 / PROJECT PREVIEW' if read_only else 'LISA2 / PROOF OF CONCEPT',18,(255,188,83))
        text(f'View {selected+1} / perspective',52)
        text(f'{len(v)} additive triangles',80)
        text('1 2 3 4  smooth camera',126)
        text(f'A auto:{"on" if autoplay else "off"} / D dive:{"on" if dive else "off"}',154)
        text('Training controlled in Studio' if read_only else 'Color fit converged' if view_config.get('experiment_method')=='gouraud' else 'SPACE    pause / continue',182,tiny=read_only)
        text('E export / ESC close',210)
        text('Live saved project checkpoint' if read_only else 'Drop four image files here',260,tiny=True)
        text('Close preview to return to Studio' if read_only else f'Custom images: {len(dropped)}/4',282,tiny=True)
        text(str(progress.get('status','starting')),324,(137,214,164))
        text(f"Fitness: {progress.get('fitness',0):.4f}",352)
        text('vs. all-black baseline',377,tiny=True)
        history=progress.get('history',[])
        pygame.draw.rect(screen,(31,39,54),(656,400,285,60))
        if len(history)>1:
            xmax=max(history[-1][0],1)
            points=[(658+280*x/xmax,458-55*y) for x,y in history]
            pygame.draw.lines(screen,(255,188,83),False,points,2)
        text('All four views, same mesh',465,tiny=True)
        pygame.display.flip();clock.tick(60)
        if smoke_test: alive=False
    if process is not None and process.poll() is None: (run/'control.txt').write_text('stop')
    pygame.quit()


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',default='runs/hybrid-gouraud');p.add_argument('--export',action='store_true')
    p.add_argument('--read-only',action='store_true',help='Preview a project without trainer or target-drop controls')
    p.add_argument('--smoke-test',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    if args.smoke_test:
        import os
        os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
    export_preview(args.run) if args.export else view(args.run,args.read_only,args.smoke_test)

if __name__=='__main__':main()
