"""General joint inverse graphics: one additive mesh, ready-made Adam optimizer.

Soft edge coverage is used only for training derivatives. Every selected model
is evaluated by the original CPU rasterizer; no learned/per-view output exists.
"""
import argparse,json,os,shutil,subprocess,sys,time
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint
from .geometry import BASES,RADIUS,TAN_HALF,ASPECT
from .checkpoint import read_checkpoint,atomic_replace


def chunk_image(points,colors,grid,temperature):
    a,b,c=points[:,0],points[:,1],points[:,2]
    area=(b[:,0]-a[:,0])*(c[:,1]-a[:,1])-(b[:,1]-a[:,1])*(c[:,0]-a[:,0])
    direction=torch.where(area.detach()>=0,1.,-1.)
    coverage=None;perimeter=torch.zeros_like(area)
    for start,end in [(a,b),(b,c),(c,a)]:
        delta=end-start
        length=(delta.square().sum(dim=1)+1e-8).sqrt()
        perimeter=perimeter+length
        distance=(delta[:,0,None,None]*(grid[1]-start[:,1,None,None])-delta[:,1,None,None]*(grid[0]-start[:,0,None,None]))
        distance=distance*direction[:,None,None]/length[:,None,None]
        edge=torch.sigmoid(distance/temperature)
        coverage=edge if coverage is None else coverage*edge
    # Avoid treating a degenerate triangle as a luminous soft line.
    coverage=coverage*(area.abs()/(temperature*perimeter+1e-8)).clamp(max=1)[:,None,None]
    return torch.einsum('nhw,nc->hwc',coverage,colors)


def soft_render(vertices,colors,width,temperature,chunk_size=48,use_checkpoint=True,camera_indices=None):
    height=width*3//4
    yy,xx=torch.meshgrid(torch.arange(height,device=vertices.device,dtype=vertices.dtype)+.5,
                         torch.arange(width,device=vertices.device,dtype=vertices.dtype)+.5,indexing='ij')
    grid=torch.stack([xx,yy])
    bases=torch.tensor(BASES,dtype=vertices.dtype,device=vertices.device)
    if camera_indices is not None: bases=bases[camera_indices]
    images=[]
    for basis in bases:
        local=vertices@basis.T
        z=RADIUS-local[:,:,2]
        x=(1+local[:,:,0]/z/TAN_HALF/ASPECT)*width/2
        y=(1-local[:,:,1]/z/TAN_HALF)*height/2
        points=torch.stack([x,y],dim=2)
        image=torch.zeros((height,width,3),device=vertices.device,dtype=vertices.dtype)
        for first in range(0,len(vertices),chunk_size):
            args=(points[first:first+chunk_size],colors[first:first+chunk_size],grid,temperature)
            piece=checkpoint(chunk_image,*args,use_reentrant=False) if use_checkpoint else chunk_image(*args)
            image=image+piece
        images.append(image)
    return torch.stack(images)


def load_targets(paths,width,device):
    values=[];h=width*3//4
    for path in paths:
        im=ImageOps.contain(Image.open(path).convert('RGB'),(width,h),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(width,h));canvas.paste(im,((width-im.width)//2,(h-im.height)//2))
        values.append(np.asarray(canvas,dtype=np.float32)/255)
    t=torch.tensor(np.array(values),device=device)
    mask=t.amax(dim=3)>.025
    t=torch.where(mask[:,:,:,None],t,0.)
    count=mask.sum(dim=(1,2),keepdim=True).clamp(min=1)
    weights=(mask.float()+.15*(~mask).float())/count
    return t,weights


def loss_for(image,target,weights):
    total=0.
    for factor,coefficient in [(1,.25),(4,.35),(16,.40)]:
        if factor==1:
            im=image;t=target;w=weights
        else:
            im=F.avg_pool2d(image.permute(0,3,1,2),factor).permute(0,2,3,1)
            t=F.avg_pool2d(target.permute(0,3,1,2),factor).permute(0,2,3,1)
            w=F.avg_pool2d(weights[:,None],factor)[:,0]*factor*factor
        total=total+coefficient*(w[:,:,:,None]*(im-t).square()).sum()
    return total


def run(args):
    root=Path.cwd();out=Path(args.run);out.mkdir(parents=True,exist_ok=True)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if device.type!='cuda' and not args.allow_cpu: raise RuntimeError('CUDA unavailable; refusing an unexpectedly slow CPU run')
    torch.set_num_threads(1)
    torch.manual_seed(23)
    if args.resume:
        saved=torch.load(out/'optimizer.pt',map_location=device,weights_only=False)
        d=read_checkpoint(out/'best.npz');cfg=json.loads(str(d['config']))
        plan=saved['plan'];start_stage=saved['stage'];offset=saved['offset'];global_step=saved['global_step']
        if args.extra_steps: plan=plan+[(plan[-1][0],args.extra_steps)]
        verts=saved['vertices'].to(device);cols=saved['colors'].to(device)
        history=d['history'].tolist()
    else:
        if (out/'best.npz').exists(): raise FileExistsError('Run already exists')
        d=read_checkpoint(args.source);cfg=json.loads(str(d['config']))
        verts=torch.tensor(d['vertices'],dtype=torch.float32,device=device)
        cols=torch.tensor(d['colors'],dtype=torch.float32,device=device)
        plan=[(128,args.steps128),(256,args.steps256),(320,args.steps320)]
        start_stage=offset=global_step=0;history=[]
        cfg.update(experiment_method='gradient',training_python=sys.executable,
            objective='color',black_penalty=.15,mutation='uniform',width=640,
            gradient_plan=plan,source=str(Path(args.source).resolve()))
    vertices=torch.nn.Parameter(verts);colors=torch.nn.Parameter(cols)
    validator=root/'.venv/Scripts/python.exe'
    began=time.perf_counter();best_loss=float('inf')
    if (out/'best-hard.json').exists(): best_loss=json.loads((out/'best-hard.json').read_text())['loss']
    last_report=None
    for stage in range(start_stage,len(plan)):
        width,steps=plan[stage]
        target,weights=load_targets(cfg['images'],width,device)
        optimizer=torch.optim.Adam([{'params':[vertices],'lr':.002},{'params':[colors],'lr':.003}])
        if args.resume and stage==start_stage: optimizer.load_state_dict(saved['optimizer'])
        first=offset if stage==start_stage else 0
        chunk=256 if width<=128 else (96 if width<=256 else 64)
        for index in range(first,steps):
            command=(out/'control.txt').read_text().strip() if (out/'control.txt').exists() else 'run'
            if command=='pause':
                if (out/'progress.json').exists():
                    paused=json.loads((out/'progress.json').read_text());paused['status']='paused'
                    (out/'progress.json').write_text(json.dumps(paused),encoding='utf-8')
                while (out/'control.txt').exists() and (out/'control.txt').read_text().strip()=='pause': time.sleep(.15)
                command=(out/'control.txt').read_text().strip()
            if command=='stop':
                if (out/'progress.json').exists():
                    stopped=json.loads((out/'progress.json').read_text());stopped['status']='stopped'
                    (out/'progress.json').write_text(json.dumps(stopped),encoding='utf-8')
                return
            fraction=index/max(steps-1,1)
            temperature=(1.5*(1-fraction)+.25*fraction) if width<320 else (.6*(1-fraction)+.12*fraction)
            rate=.002*(128/width)*(1-.7*fraction)
            optimizer.param_groups[0]['lr']=rate
            optimizer.param_groups[1]['lr']=.003*(1-.7*fraction)
            optimizer.zero_grad(set_to_none=True)
            loss=torch.zeros((),device=device)
            # Loss is separable across cameras: accumulate identical gradients
            # while retaining only one camera's autograd graph at a time.
            for camera in range(4):
                image=soft_render(vertices,colors,width,temperature,chunk,use_checkpoint=width>128,camera_indices=[camera])
                partial=loss_for(image,target[camera:camera+1],weights[camera:camera+1])
                if not torch.isfinite(partial): raise FloatingPointError('Non-finite gradient objective')
                partial.backward()
                loss=loss+partial.detach()
            torch.nn.utils.clip_grad_norm_([vertices,colors],10.)
            optimizer.step()
            with torch.no_grad():
                vertices.div_(vertices.norm(dim=2,keepdim=True).clamp(min=1))
                colors.clamp_(0,.4)
            global_step+=1
            if global_step%50==0 or index==steps-1 or global_step==1:
                cfg.update(gradient_plan=plan,gradient_stage=stage,gradient_offset=index+1,gradient_steps=global_step)
                tmp=out/'best.tmp'
                with tmp.open('wb') as f:
                    np.savez_compressed(f,vertices=vertices.detach().cpu().numpy().astype(np.float64),
                        colors=colors.detach().cpu().numpy().astype(np.float64),step=global_step,
                        history=np.array(history),config=json.dumps(cfg))
                atomic_replace(tmp,out/'best.npz')
                state=dict(vertices=vertices.detach().cpu(),colors=colors.detach().cpu(),optimizer=optimizer.state_dict(),
                    stage=stage,offset=index+1,global_step=global_step,plan=plan)
                torch.save(state,out/'optimizer.tmp');atomic_replace(out/'optimizer.tmp',out/'optimizer.pt')
                subprocess.run([str(validator),'-m','lisa2.gradient_validate','--checkpoint',str(out/'best.npz'),
                                '--output',str(out/'hard-current.json')],check=True,stdout=subprocess.DEVNULL)
                last_report=json.loads((out/'hard-current.json').read_text())
                history.append([global_step,last_report['fitness']])
                if last_report['loss']<best_loss:
                    best_loss=last_report['loss']
                    shutil.copy2(out/'best.npz',out/'best-common.npz')
                    shutil.copy2(out/'optimizer.pt',out/'best-common-optimizer.pt')
                    shutil.copy2(out/'hard-current.json',out/'best-hard.json')
                progress=dict(status='running',step=global_step,total=sum(s for _,s in plan),
                    fitness=last_report['fitness'],loss=last_report['loss'],baseline=None,history=history,
                    soft_loss=float(loss.detach()),training_width=width,seconds=time.perf_counter()-began)
                temporary=out/'progress.tmp';temporary.write_text(json.dumps(progress,indent=2),encoding='utf-8')
                atomic_replace(temporary,out/'progress.json')
                print(f'Adam {global_step}, {width}px, soft={float(loss.detach()):.6f}, HARD 640 fitness={last_report["fitness"]:.6f}',flush=True)
        offset=0
    if (out/'best-common.npz').exists():
        shutil.copy2(out/'best.npz',out/'last.npz')
        shutil.copy2(out/'best-common.npz',out/'best.npz')
        shutil.copy2(out/'best-common-optimizer.pt',out/'optimizer.pt')
    progress=json.loads((out/'progress.json').read_text());progress['status']='complete'
    progress['selected_hard_loss']=best_loss
    if (out/'best-hard.json').exists():
        selected=json.loads((out/'best-hard.json').read_text());progress['fitness']=selected['fitness'];progress['loss']=selected['loss'];progress['selected_step']=selected['step']
    (out/'progress.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True)
    p.add_argument('--source',default='runs/uniform-fine640/best.npz')
    p.add_argument('--steps128',type=int,default=600);p.add_argument('--steps256',type=int,default=400)
    p.add_argument('--steps320',type=int,default=200);p.add_argument('--resume',action='store_true')
    p.add_argument('--extra-steps',type=int,default=0);p.add_argument('--allow-cpu',action='store_true')
    run(p.parse_args())

if __name__=='__main__':main()
