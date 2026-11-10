import argparse
import json
import os
from pathlib import Path
import time
import numpy as np
from deap import base, creator, cma
from .geometry import BASES, DIRECTIONS, TAN_HALF, ASPECT, RADIUS, constrain
from .raster import render, add_triangle, optimal_color, optimal_color_structure
from .targets import generate, load
from .objective import StructureObjective, ColorObjective
from .mutation import outside_any_silhouette,adaptive_mutation
from .checkpoint import read_checkpoint, atomic_replace

creator.create('LisaFitnessMin', base.Fitness, weights=(-1.,))
creator.create('LisaIndividual', list, fitness=creator.LisaFitnessMin)


def atomic_json(path,data):
    path=Path(path)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,indent=2),encoding='utf-8')
    atomic_replace(tmp,path)


def save(path,vertices,colors,step,history,config):
    tmp=Path(path).with_suffix('.tmp')
    with tmp.open('wb') as f:
        np.savez_compressed(f,vertices=vertices,colors=colors,step=step,
                            history=np.array(history),config=json.dumps(config))
    atomic_replace(tmp,path)


def export_obj(path,vertices,colors):
    if np.asarray(colors).ndim==3:
        from .gouraud import export_vertex_obj
        return export_vertex_obj(path,vertices,colors)
    path=Path(path)
    with path.open('w',encoding='ascii') as f, path.with_suffix('.mtl').open('w',encoding='ascii') as m:
        f.write('# Lisa2: flat RGB, two-sided ADDITIVE rendering required\n')
        f.write('# OBJ/MTL does not specify additive blending; use the companion renderer.\n')
        f.write(f'mtllib {path.stem}.mtl\n')
        for i,(v,c) in enumerate(zip(vertices,colors)):
            m.write(f'newmtl triangle_{i}\nKa 0 0 0\nKd {c[0]:.8f} {c[1]:.8f} {c[2]:.8f}\nillum 0\n\n')
            for p in v: f.write('v '+' '.join(f'{x:.9f}' for x in p)+'\n')
            f.write(f'usemtl triangle_{i}\nf {3*i+1} {3*i+2} {3*i+3}\n')


def seed_triangle(residual,rng):
    k=int(rng.integers(4))
    score=np.maximum(residual[k],0).sum(axis=2)
    score=score*score+1e-8
    index=int(rng.choice(score.size,p=(score/score.sum()).ravel()))
    h,w=score.shape;y,x=divmod(index,w)
    z=rng.uniform(-.65,.65)
    center=BASES[k,0]*((2*(x+.5)/w-1)*ASPECT*TAN_HALF*(RADIUS-z))
    center+=BASES[k,1]*((1-2*(y+.5)/h)*TAN_HALF*(RADIUS-z))+DIRECTIONS[k]*z
    size=rng.uniform(.035,.17)
    offsets=rng.normal(size=(3,2))*size
    v=center+offsets[:,0,None]*BASES[k,0]+offsets[:,1,None]*BASES[k,1]
    return constrain(v)


def train(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if args.images:
        paths=[Path(p).resolve() for p in args.images]
    else:
        generate('assets/targets')
        paths=sorted(Path('assets/targets').glob('*.png'))
    target=load(paths,args.width,args.width*3//4)
    # Equal total influence per camera, with foreground emphasis but real black penalties.
    weights=1+3*target.max(axis=3)
    weights/=weights.mean(axis=(1,2),keepdims=True)
    objective=None
    if args.objective=='structure':
        objective=StructureObjective(target,args.color_weight,args.edge_weight,args.background_weight,args.background_linear,args.silhouette_weight,args.edge_norm)
        target=objective.target
        weights=objective.weights
    if args.objective=='color':
        objective=ColorObjective(target,args.black_penalty)
        target=objective.target
        weights=objective.weights
    baseline=objective.baseline if objective else float(np.sum(weights[:,:,:,None]*target**2))
    def total_loss(image):
        return objective.terms(image)['total'] if objective else float(np.sum(weights[:,:,:,None]*(target-image)**2))
    if baseline<=1e-12: raise ValueError('At least one target must contain visible foreground')
    config=vars(args).copy();config['images']=[str(p.resolve()) for p in paths]
    config['optimizer']='DEAP CMA-ES; silhouette-aware color candidates' if isinstance(objective,StructureObjective) else 'DEAP CMA-ES, block-coordinate geometry + exact RGB least squares'
    config['fov_y']=42.;config['aspect']=4/3;config['camera_radius']=RADIUS
    vertices=np.zeros((args.triangles,3,3));colors=np.zeros((args.triangles,3))
    start=0;history=[]
    started_from_mesh=bool(args.warm_start)
    checkpoint=out/'best.npz'
    if checkpoint.exists() and not args.resume:
        raise FileExistsError(f'{checkpoint} exists; use --resume or choose a new output directory')
    if args.warm_start and not args.resume:
        warm=read_checkpoint(args.warm_start)
        if warm['vertices'].shape!=vertices.shape: raise ValueError('Warm-start triangle count differs')
        vertices=warm['vertices'].copy();colors=warm['colors'].copy()
    if args.resume and checkpoint.exists():
        old=read_checkpoint(checkpoint)
        vertices=old['vertices'];colors=old['colors'];start=int(old['step'])
        history=old['history'].tolist()
        previous=json.loads(str(old['config']))
        started_from_mesh=bool(previous.get('warm_start'))
        config['warm_start']=previous.get('warm_start')
        if previous.get('objective','rgb')!=args.objective: raise ValueError('Objective changed; use a new warm-start run')
        if previous.get('mutation_space','world')!=args.mutation_space: raise ValueError('Mutation step space changed; use a new warm-start run')
        if previous.get('mutation','uniform')!=args.mutation: raise ValueError('Mutation changed; use a new warm-start run')
        if args.objective=='color' and previous.get('black_penalty')!=args.black_penalty: raise ValueError('Black penalty changed; use a new warm-start run')
        if isinstance(objective,StructureObjective):
            if previous.get('edge_norm','area')!=args.edge_norm: raise ValueError('Edge normalization changed; use a new warm-start run')
            for key in ['color_weight','edge_weight','background_weight','background_linear','silhouette_weight']:
                if previous.get(key)!=config[key]: raise ValueError(f'Resume objective changed: {key}')
        for key in ['width','triangles','images','seed','generations','population']:
            if previous[key]!=config[key]: raise ValueError(f'Resume configuration changed: {key}')
    images=render(vertices,colors,args.width,args.width*3//4)
    began=time.perf_counter()
    current_step=start
    def checkpoint_now(status):
        loss=total_loss(images)
        save(checkpoint,vertices,colors,current_step,history,config)
        atomic_json(out/'progress.json',dict(status=status,step=current_step,
            total=args.triangles*args.rounds,fitness=1-loss/baseline,
            loss=loss,baseline=baseline,active_triangles=int(np.sum(colors.max(axis=1)>1e-5)),
            seconds=time.perf_counter()-began,history=history,loss_terms=objective.terms(images) if objective else {}))
    checkpoint_now('running')
    try:
        for step in range(start,args.triangles*args.rounds):
            current_step=step
            control=out/'control.txt'
            if control.exists() and control.read_text().strip()=='stop': break
            if control.exists() and control.read_text().strip()=='pause':
                checkpoint_now('paused')
                while control.exists() and control.read_text().strip()=='pause': time.sleep(.15)
                checkpoint_now('running')
                if control.exists() and control.read_text().strip()=='stop': break
            block=step//args.triangles
            order=np.random.default_rng(args.seed+block).permutation(args.triangles)
            i=int(order[step%args.triangles])
            rng=np.random.default_rng(args.seed+step*31)
            np.random.seed(args.seed+step*31)
            old_v=vertices[i].copy();old_c=colors[i].copy()
            add_triangle(images,old_v,old_c,-1.)
            residual=np.ascontiguousarray(target-images)
            effective=objective.effective_residual(residual) if isinstance(objective,StructureObjective) else None
            def evaluate(v):
                if isinstance(objective,StructureObjective):
                    return optimal_color_structure(v,effective,weights,objective.ex,objective.ey,images,objective.mask,objective.sw,objective.visibility,old_c)
                return optimal_color(v,residual,weights)
            old_color,old_gain=evaluate(old_v)
            best_v=old_v;best_color=old_color;best_gain=old_gain
            centroid=seed_triangle(residual,rng) if (block==0 and args.objective!='color') or old_gain<1e-5 else old_v
            sigma=(.055 if block==0 and not started_from_mesh else .025) if args.objective=='color' else (.055 if block==0 else .025)
            if args.mutation_space=='pixel': sigma*=128/args.width
            strategy=cma.Strategy(centroid=centroid.ravel(),sigma=sigma,
                                  lambda_=args.population)
            # The framework owns sampling, covariance adaptation and selection.
            for generation in range(args.generations):
                population=strategy.generate(creator.LisaIndividual)
                if args.mutation=='adaptive':
                    parent=constrain(strategy.centroid)
                    masks=objective.mask if objective else target.max(axis=3)>.025
                    outside=outside_any_silhouette(parent,masks)
                    for ind in population: adaptive_mutation(ind,strategy.centroid,outside,rng)
                if generation==0: population[0][:]=centroid.ravel().tolist()
                for ind in population:
                    v=constrain(ind)
                    color,gain=evaluate(v)
                    ind.fitness.values=(-gain,)
                    if gain>best_gain: best_v=v;best_color=color;best_gain=gain
                strategy.update(population)
            vertices[i]=best_v;colors[i]=best_color
            add_triangle(images,best_v,best_color)
            current_step=step+1
            if current_step%16==0:
                loss=total_loss(images)
                history.append([current_step,1-loss/baseline])
                checkpoint_now('running')
            if current_step%128==0:
                print(f'{current_step}/{args.triangles*args.rounds}: fitness={history[-1][1]:.5f}',flush=True)
    except KeyboardInterrupt:
        checkpoint_now('stopped')
        export_obj(out/'model.obj',vertices,colors)
        return
    checkpoint_now('complete' if current_step==args.triangles*args.rounds else 'stopped')
    export_obj(out/'model.obj',vertices,colors)
    print((out/'progress.json').read_text()[:450],flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--images',nargs=4)
    p.add_argument('--output',default='runs/dos640')
    p.add_argument('--triangles',type=int,default=768)
    p.add_argument('--rounds',type=int,default=4)
    p.add_argument('--generations',type=int,default=10)
    p.add_argument('--population',type=int,default=16)
    p.add_argument('--width',type=int,default=640)
    p.add_argument('--seed',type=int,default=23)
    p.add_argument('--edge-norm',choices=['area','energy'],default='area')
    p.add_argument('--objective',choices=['rgb','structure','color'],default='color')
    p.add_argument('--mutation',choices=['uniform','adaptive'],default='uniform')
    p.add_argument('--mutation-space',choices=['pixel','world'],default='pixel')
    p.add_argument('--black-penalty',type=float,default=.15)
    p.add_argument('--color-weight',type=float,default=4.)
    p.add_argument('--edge-weight',type=float,default=1.5)
    p.add_argument('--background-weight',type=float,default=6.)
    p.add_argument('--background-linear',type=float,default=.08)
    p.add_argument('--silhouette-weight',type=float,default=3.)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--warm-start',help='Initialize geometry from a different-resolution checkpoint')
    args=p.parse_args()
    if args.triangles<1 or args.width%4 or args.population<4 or args.generations<1: p.error('Invalid experiment dimensions')
    if min(args.black_penalty,args.color_weight,args.edge_weight,args.background_weight,args.background_linear,args.silhouette_weight)<0: p.error('Loss weights must be nonnegative')
    train(args)

if __name__=='__main__': main()
