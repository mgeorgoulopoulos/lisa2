"""Bounded matched pilot: residual-driven triangle proposals vs local CMA.

Not integrated into Studio until actual images justify the extra option.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from deap import cma
from PIL import Image,ImageDraw
from .checkpoint import read_checkpoint
from .geometry import BASES,constrain,project
from .gouraud import render_gouraud,fit,export_vertex_obj
from .hybrid_gouraud import add,moments,local_fit
from .local_refine import refine
from .objective import ColorObjective
from .targets import load
from .train import creator,save,atomic_json


def marginal_utilities(vertices,colors,image,objective):
    residual=np.ascontiguousarray(objective.target-image);values=[]
    for v,c in zip(vertices,colors):
        gram,rhs=moments(v,residual,objective.weights)
        # Exact increase in physical loss when this triangle is removed.
        values.append(float(2*np.sum(c*rhs)+np.sum(c*(gram@c))))
    return np.asarray(values)


def residual_centers(residual,weights,rng,count=2048):
    points=rng.normal(size=(count,3))
    points/=np.linalg.norm(points,axis=1)[:,None]
    points*=rng.random(count)[:,None]**(1/3)
    rhs=np.zeros((count,3));denominator=np.zeros(count)
    height,width=weights.shape[1:]
    for k,basis in enumerate(BASES):
        xy=np.floor(project(points,basis,width,height)).astype(int)
        x=np.clip(xy[:,0],0,width-1);y=np.clip(xy[:,1],0,height-1)
        w=weights[k,y,x];rhs+=w[:,None]*residual[k,y,x];denominator+=w
    colors=np.clip(rhs/np.maximum(denominator[:,None],1e-30),0,.4)
    scores=np.maximum(0.,np.sum(2*colors*rhs-denominator[:,None]*colors**2,axis=1))
    probabilities=scores/scores.sum() if scores.sum()>0 else np.full(count,1/count)
    return points,probabilities


def new_triangle(points,probabilities,rng):
    center=points[rng.choice(len(points),p=probabilities)]
    offsets=rng.normal(size=(3,3));offsets-=offsets.mean(axis=0)
    offsets/=max(float(np.sqrt(np.mean(offsets**2))),1e-12)
    size=np.exp(rng.uniform(np.log(.006),np.log(.12)))
    return constrain(center+offsets*size)


def run_arm(source,out,objective,indices,seed,replacement):
    out.mkdir(parents=True,exist_ok=False)
    d=read_checkpoint(source);v=d['vertices'].copy();colors=d['colors'].copy()
    cfg=json.loads(str(d['config']));image=render_gouraud(v,colors,640,480,BASES)
    initial=objective.terms(image)['total'];history=[[0,1-initial/objective.baseline]]
    records=[];began=time.perf_counter();calls=0;injected=0
    order=np.random.default_rng(seed).permutation(indices)
    for j,i in enumerate(order):
        i=int(i);old=v[i].copy();old_c=colors[i].copy();add(image,old,old_c,-1.)
        residual=np.ascontiguousarray(objective.target-image)
        gram,rhs=moments(old,residual,objective.weights)
        old_gain=float(2*np.sum(old_c*rhs)-np.sum(old_c*(gram@old_c)))
        best_v=old;best_c=old_c;best_gain=old_gain;origin='unchanged'
        c,g=local_fit(old,residual,objective.weights)
        if g>best_gain: best_c=c;best_gain=g;origin='parent-rgb'
        rng=np.random.default_rng(seed+1009*j)
        centers,probabilities=residual_centers(residual,objective.weights,rng) if replacement else (None,None)
        np.random.seed(seed+31*j)
        strategy=cma.Strategy(centroid=old.ravel(),sigma=.005,lambda_=8)
        for generation in range(2):
            population=strategy.generate(creator.LisaIndividual)
            for index,individual in enumerate(population):
                external=replacement and index<4
                candidate=new_triangle(centers,probabilities,rng) if external else constrain(individual)
                injected+=int(external)
                c,g=local_fit(candidate,residual,objective.weights)
                candidate,c,g,_=refine(candidate,c,g,residual,objective.weights,4.,2.,3)
                calls+=1;individual[:]=candidate.ravel().tolist();individual.fitness.values=(-g,)
                if g>best_gain+1e-14:
                    best_v=candidate;best_c=c;best_gain=g;origin='replacement' if external else 'local'
            strategy.update(population)
        v[i]=best_v;colors[i]=best_c;add(image,best_v,best_c)
        records.append(dict(triangle=i,origin=origin,gain=best_gain-old_gain,max_world_move=float(np.linalg.norm(best_v-old,axis=1).max())))
        if (j+1)%16==0:
            loss=objective.terms(image)['total'];history.append([(j+1)*16,1-loss/objective.baseline])
            atomic_json(out/'progress.json',dict(status='running',triangles=j+1,total=len(order),loss=loss,seconds=time.perf_counter()-began))
    cfg.update(experiment_method='replacement-pilot',pilot=dict(seed=seed,replacement=replacement,triangles=len(order),population=8,generations=2))
    save(out/'best.npz',v,colors,calls,history,cfg)
    before_global=objective.terms(image)['total']
    fit(out/'best.npz',out/'global',max_iterations=8)
    solved=read_checkpoint(out/'global/best.npz')
    candidate=render_gouraud(v,solved['colors'],640,480,BASES)
    if objective.terms(candidate)['total']<=before_global: colors=solved['colors'];image=candidate
    # Independent reconstruction also removes incremental rounding history.
    image=render_gouraud(v,colors,640,480,BASES);terms=objective.terms(image)
    history.append([calls,1-terms['total']/objective.baseline])
    assert terms['total']<=initial+1e-10
    assert np.min(np.diff(np.asarray(history)[:,1]))>=-1e-10
    assert np.max(np.linalg.norm(v,axis=2))<=1+1e-10 and colors.min()>=0 and colors.max()<=.4+1e-10
    assert np.allclose(image,render_gouraud(v[:,::-1],colors[:,::-1],640,480,BASES),atol=1e-10)
    save(out/'best.npz',v,colors,calls,history,cfg);export_vertex_obj(out/'model.obj',v,colors)
    report=dict(status='complete',seed=seed,replacement=replacement,initial_loss=initial,loss=terms['total'],loss_terms=terms,
        before_global=before_global,proposals=calls,injected=injected,seconds=time.perf_counter()-began,
        accepted_replacements=sum(r['origin']=='replacement' for r in records),
        changed_triangles=sum(r['origin']!='unchanged' for r in records),updates=records)
    atomic_json(out/'progress.json',report)
    print(out.name,report['loss'],'replacements',report['accepted_replacements'],'seconds',report['seconds'],flush=True)
    return report,image


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='runs/replacement-pilot')
    parser.add_argument('--source',default='runs/timing-convergence-clean/snapshots/memetic-s23-stopped.npz')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    source=Path(args.source);d=read_checkpoint(source);cfg=json.loads(str(d['config']))
    obj=ColorObjective(load(cfg['images'],640,480),.15)
    baseline=render_gouraud(d['vertices'],d['colors'],640,480,BASES)
    utilities=marginal_utilities(d['vertices'],d['colors'],baseline,obj)
    indices=np.argsort(utilities,kind='stable')[:64]
    atomic_json(out/'protocol.json',dict(source=str(source.resolve()),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        initial_loss=obj.terms(baseline)['total'],selected=indices.tolist(),utilities=utilities[indices].tolist(),
        budget=dict(triangles=64,population=8,generations=2,seeds=[23,47],replacement_fraction=.5,global_rgb_iterations=8),
        criteria='Exact physical loss and actual before/after images; no checkbox based only on a small numeric gain.'))
    reports=[];images=[('baseline',baseline)]
    for seed in (23,47):
        for replacement in (False,True):
            name=('replacement' if replacement else 'control')+f'-s{seed}'
            report,image=run_arm(source,out/name,obj,indices,seed,replacement)
            reports.append(report);images.append((name,image))
            atomic_json(out/'results.json',dict(runs=reports))
    canvas=Image.new('RGB',(1280,264*len(images)),(15,18,24));draw=ImageDraw.Draw(canvas)
    for row,(name,data) in enumerate(images):
        draw.text((8,264*row+5),name,fill='white')
        for k in range(4):
            im=Image.fromarray(np.uint8(np.clip(data[k],0,1)*255))
            canvas.paste(im.resize((320,240),Image.Resampling.LANCZOS),(320*k,264*row+24))
    canvas.save(out/'comparison.png')
    best=min(range(1,len(images)),key=lambda i:obj.terms(images[i][1])['total'])
    for k,name in enumerate(('portrait','spacecraft','dragon','island')):
        pair=Image.new('RGB',(1280,508),(15,18,24));draw=ImageDraw.Draw(pair)
        for col,index in enumerate((0,best)):
            draw.text((640*col+10,8),images[index][0],fill='white')
            pair.paste(Image.fromarray(np.uint8(np.clip(images[index][1][k],0,1)*255)),(640*col,28))
        pair.save(out/f'compare-{name}.png')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==json.loads((out/'protocol.json').read_text())['source_sha256']


if __name__=='__main__':main()
