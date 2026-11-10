"""Independent uniform-CMA trials: curriculum, simultaneous scales, control."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from deap import cma
from .train import creator,save,export_obj,atomic_json,seed_triangle
from .checkpoint import read_checkpoint
from .geometry import constrain
from .objective import ColorObjective
from .raster import render,add_triangle,optimal_color
from .pyramid import decompose
from .multiscale import MultiscaleObjective


def run(args):
    from .targets import load
    from PIL import Image
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if args.resume:
        d=read_checkpoint(out/'best.npz');cfg=json.loads(str(d['config']))
        parameters=cfg['experiment_parameters']
        state=cfg['experiment_state']
        # An explicit extension always continues at full detail.
        parameters['passes']+=args.extra_rounds
        if args.extra_rounds:
            state['complete']=False
            state['level']=4 if cfg['experiment_method']=='curriculum' else 0
            state['extension_left']=args.extra_rounds
            state['level_pass']=0
    else:
        if (out/'best.npz').exists(): raise FileExistsError('Existing experiment; use --resume')
        d=read_checkpoint(args.source);cfg=json.loads(str(d['config']))
        parameters=dict(method=args.method,source=str(Path(args.source).resolve()),
            generations=args.generations,population=args.population,passes=args.passes,
            max_stage_rounds=args.max_stage_rounds,tolerance=args.tolerance,seed=args.seed)
        state=dict(level=0,level_pass=0,pass_no=0,within_pass=0,stage_losses=[],events=[],complete=False)
        cfg.update(experiment_method=args.method,experiment_parameters=parameters,
                   objective='color',mutation='uniform',mutation_space='pixel',black_penalty=.15)
    method=parameters['method'];cfg['experiment_parameters']=parameters
    v=d['vertices'].copy();colors=d['colors'].copy()
    width=cfg['width'];height=width*3//4
    target=load(cfg['images'],width,height)
    reference=ColorObjective(target,.15)
    current=render(v,colors,width,height)
    history=d['history'].tolist() if args.resume else []
    best_reference=float(reference.terms(current)['total'])
    if args.resume and (out/'best-common.npz').exists():
        old=read_checkpoint(out/'best-common.npz')
        best_reference=float(reference.terms(render(old['vertices'],old['colors'],width,height))['total'])
    cumulative=None
    sigmas=(16.,8.,4.,2.,0.)
    if method=='curriculum':
        bands,cumulative=decompose(target,sigmas)
        if not args.resume:
            assets=out/'pyramid';assets.mkdir(exist_ok=True)
            np.savez_compressed(assets/'decomposition.npz',bands=bands,sigmas=sigmas)
            for level,images in enumerate(cumulative):
                for view,image in enumerate(images):
                    Image.fromarray(np.uint8(np.clip(image,0,1)*255)).save(assets/f'level-{level+1}-view-{view+1}.png')
            atomic_json(assets/'validation.json',dict(max_reconstruction_error=float(np.abs(bands.sum(axis=0)-target).max()),
                signed_detail_bands=True,sigmas=list(sigmas)))
        del bands
    start_time=time.perf_counter()
    cap=5*parameters['max_stage_rounds'] if method=='curriculum' else parameters['passes']
    if args.extra_rounds and method=='curriculum': cap=max(cap,state['pass_no']+args.extra_rounds)
    cfg.update(width=width,triangles=len(v),rounds=cap,generations=parameters['generations'],
               population=parameters['population'],seed=parameters['seed'],experiment_state=state)
    stage_objective=None
    def checkpoint(status):
        nonlocal best_reference
        step=state['pass_no']*len(v)+state['within_pass']
        common_loss=float(reference.terms(current)['total'])
        common_fitness=1-common_loss/reference.baseline
        cfg['experiment_state']=state
        save(out/'best.npz',v,colors,step,history,cfg)
        if common_loss<=best_reference or not (out/'best-common.npz').exists():
            best_reference=common_loss
            save(out/'best-common.npz',v,colors,step,history,cfg)
        atomic_json(out/'progress.json',dict(status=status,step=step,total=cap*len(v),fitness=common_fitness,
            loss=common_loss,baseline=reference.baseline,history=history,
            active_triangles=int(np.sum(colors.max(axis=1)>1e-5)),
            stage=state['level']+1,pass_no=state['pass_no'],
            stage_loss=None if stage_objective is None else stage_objective.terms(current)['total'],
            best_common_loss=best_reference,seconds=time.perf_counter()-start_time,events=state['events']))
    checkpoint('running')
    try:
        while not state['complete'] and state['pass_no']<cap:
            level=state['level']
            if method=='curriculum': stage_objective=ColorObjective(cumulative[level],.15)
            elif method=='multiscale': stage_objective=MultiscaleObjective(target,.15)
            else: stage_objective=reference
            if state['within_pass']==0:
                state['start_loss']=float(stage_objective.terms(current)['total'])
            order=np.random.default_rng(parameters['seed']+state['pass_no']).permutation(len(v))
            for j in range(state['within_pass'],len(v)):
                control=out/'control.txt'
                command=control.read_text().strip() if control.exists() else 'run'
                if command=='stop':
                    checkpoint('stopped');export_obj(out/'model.obj',v,colors);return
                if command=='pause':
                    checkpoint('paused')
                    while control.exists() and control.read_text().strip()=='pause': time.sleep(.15)
                    checkpoint('running')
                    if control.exists() and control.read_text().strip()=='stop':
                        checkpoint('stopped');export_obj(out/'model.obj',v,colors);return
                i=int(order[j]);step=state['pass_no']*len(v)+j
                rng=np.random.default_rng(parameters['seed']+step*31)
                np.random.seed(parameters['seed']+step*31)
                old=v[i].copy();old_c=colors[i].copy()
                add_triangle(current,old,old_c,-1.)
                if method=='multiscale':
                    residuals=stage_objective.prepare(current)
                    residual=residuals[0]
                    def candidate(vertices): return stage_objective.candidate(vertices,residuals)
                else:
                    residual=np.ascontiguousarray(stage_objective.target-current)
                    def candidate(vertices): return optimal_color(vertices,residual,stage_objective.weights)
                best_c,best_gain=candidate(old);best_v=old
                centroid=old if best_gain>1e-5 else seed_triangle(residual,rng)
                scale=sigmas[level] if method=='curriculum' else (float(rng.choice([1.,4.,16.],p=[.5,.35,.15])) if method=='multiscale' else 1.)
                sigma=.025*128/width*max(1.,scale)
                strategy=cma.Strategy(centroid=centroid.ravel(),sigma=sigma,lambda_=parameters['population'])
                for generation in range(parameters['generations']):
                    population=strategy.generate(creator.LisaIndividual)
                    if generation==0: population[0][:]=centroid.ravel().tolist()
                    for ind in population:
                        vertices=constrain(ind);color,gain=candidate(vertices)
                        ind.fitness.values=(-gain,)
                        if gain>best_gain: best_v=vertices;best_c=color;best_gain=gain
                    strategy.update(population)
                v[i]=best_v;colors[i]=best_c;add_triangle(current,best_v,best_c)
                state['within_pass']=j+1
                if (j+1)%64==0:
                    common=float(reference.terms(current)['total'])
                    history.append([step+1,1-common/reference.baseline]);checkpoint('running')
            end_loss=float(stage_objective.terms(current)['total'])
            improvement=(state['start_loss']-end_loss)/max(state['start_loss'],1e-12)
            normalized_gain=(state['start_loss']-end_loss)/max(stage_objective.baseline,1e-12)
            state['pass_no']+=1;state['level_pass']+=1;state['within_pass']=0
            state['stage_losses'].append(end_loss)
            print(f'{method}: pass {state["pass_no"]}, level {level+1}, relative gain {improvement:.4%}, reference {1-reference.terms(current)["total"]/reference.baseline:.6f}',flush=True)
            if method=='curriculum':
                plateau=state['level_pass']>=2 and normalized_gain<parameters['tolerance']
                limited=state['level_pass']>=parameters['max_stage_rounds']
                if plateau or limited:
                    state['events'].append(dict(level=level+1,passes=state['level_pass'],
                        reason='normalized_fitness_plateau' if plateau else 'stage_cap',relative_gain=improvement,normalized_gain=normalized_gain,
                        reference_loss=float(reference.terms(current)['total'])))
                    if level==4: state['complete']=True
                    else:
                        state['level']+=1;state['level_pass']=0;state['stage_losses']=[]
            else: state['complete']=state['pass_no']>=cap
            if state.get('extension_left',0)>0:
                state['extension_left']-=1
                state['complete']=state['extension_left']==0
            checkpoint('complete' if state['complete'] else 'running')
            save(out/f'pass-{state["pass_no"]:03}.npz',v,colors,state['pass_no']*len(v),history,cfg)
    except KeyboardInterrupt:
        checkpoint('stopped');export_obj(out/'model.obj',v,colors);return
    checkpoint('complete');export_obj(out/'model.obj',v,colors)
    print('Saved',out,flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--method',choices=['curriculum','multiscale','control'],default='curriculum')
    p.add_argument('--output',required=True)
    p.add_argument('--source',default='runs/uniform-fine640/best.npz')
    p.add_argument('--passes',type=int,default=10)
    p.add_argument('--generations',type=int,default=6)
    p.add_argument('--population',type=int,default=12)
    p.add_argument('--max-stage-rounds',type=int,default=4)
    p.add_argument('--tolerance',type=float,default=.002)
    p.add_argument('--seed',type=int,default=23)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--extra-rounds',type=int,default=0)
    args=p.parse_args()
    if args.generations<1 or args.population<4 or args.passes<1 or args.max_stage_rounds<2: p.error('Invalid budget')
    run(args)

if __name__=='__main__':main()
