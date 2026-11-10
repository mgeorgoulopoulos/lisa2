"""Resumable project evolution with three modes and pass-based plateau stop."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import time
import traceback
import numpy as np
from deap import cma
from .checkpoint import read_checkpoint
from .geometry import BASES,constrain
from .gouraud import fit,render_gouraud
from .hybrid_gouraud import add,local_fit,moments
from .local_refine import refine
from .objective import ColorObjective
from .project import read_project,run_directory,image_paths
from .targets import load
from .train import creator,save,atomic_json,seed_triangle

METRICS=['step','cycle','triangle','proposals','loss','interior_color','black_spill','fitness','seconds','event','mode',
        'refinement_calls','refinement_geometry_probes','refinement_validation_trials']
from .project import DEFAULTS
FIELDS=METRICS+list(DEFAULTS)


def process_alive(pid):
    if os.name=='nt':
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        handle=kernel.OpenProcess(0x1000,False,int(pid))
        if not handle: return ctypes.get_last_error()==5
        code=ctypes.c_ulong()
        kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        try:
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)): return True
            return code.value==259
        finally: kernel.CloseHandle(handle)
    try: os.kill(int(pid),0);return True
    except ProcessLookupError: return False
    except PermissionError: return True


def acquire_lock(folder):
    path=folder/'worker.lock'
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        try: previous=json.loads(path.read_text())
        except (OSError,ValueError): raise RuntimeError('Project lock is unreadable; another process may be starting')
        if process_alive(previous['pid']): raise RuntimeError('This project is already running')
        path.unlink();fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    with os.fdopen(fd,'w') as stream: json.dump(dict(pid=os.getpid()),stream)
    return path


def plateau_count(previous,current,count,cycle,settings):
    relative=(previous-current)/max(abs(previous),1e-20)
    eligible=cycle>=settings['plateau_min_passes']
    count=count+1 if eligible and relative<settings['plateau_relative'] else 0
    return count,relative


def color_gain(v,c,residual,weights):
    gram,rhs=moments(v,residual,weights)
    return float(2*np.sum(c*rhs)-np.sum(c*(gram@c)))


def run(path,max_triangles=None,observer=None):
    path=Path(path).resolve();project=read_project(path);folder=run_directory(path,project)
    folder.mkdir(parents=True,exist_ok=True);lock=acquire_lock(folder)
    try: _run(path,folder,project,max_triangles,observer)
    except Exception as error:
        atomic_json(folder/'error.json',dict(message=str(error),traceback=traceback.format_exc()))
        try:
            progress=json.loads((folder/'progress.json').read_text());progress.update(status='error',message=str(error))
            atomic_json(folder/'progress.json',progress)
        except (OSError,ValueError): pass
        raise
    finally: lock.unlink(missing_ok=True)


def _run(path,folder,project,max_triangles,observer=None):
    s=project['settings'];images=image_paths(path,project)
    for image,digest in zip(images,project['image_sha256']):
        if hashlib.sha256(Path(image).read_bytes()).hexdigest()!=digest: raise ValueError('A project image changed; create a new project for different targets')
    width=s['width'];height=width*3//4
    obj=ColorObjective(load(images,width,height),.15)
    if obj.baseline<=1e-12: raise ValueError('The targets must contain visible foreground')
    checkpoint=folder/'best.npz'
    if checkpoint.exists():
        d=read_checkpoint(checkpoint);v=d['vertices'].copy();colors=d['colors'].copy()
        cfg=json.loads(str(d['config']));state=cfg['project_state'];history=d['history'].tolist()
        if len(v)!=s['triangles'] or cfg.get('width',640)!=width:
            raise ValueError('Checkpoint triangle count/resolution differs; create a new project')
        if cfg.get('project_id')!=project['id']:
            # A Save As clone has a new identity but deliberately retains history.
            cfg['project_id']=project['id']
        if cfg.get('project_settings')!=s: state['plateau_streak']=0
        if project.get('state',{}).get('status')=='plateau': state['plateau_streak']=0
    else:
        rng=np.random.default_rng(s['seed'])
        v=np.array([seed_triangle(obj.target,rng) for _ in range(s['triangles'])])
        colors=np.zeros((s['triangles'],3,3));cfg={};history=[[0,0.]]
        state=dict(cycle=0,within_pass=0,step=0,proposals=0,accepted=0,
                   plateau_streak=0,cycle_start_loss=obj.baseline,elapsed=0.,global_solves=0,
                   refined_candidates=0,refine_steps_accepted=0)
    state.setdefault('pass_seed',s['seed']+state['cycle'])
    if state['within_pass']==0: state['pass_seed']=s['seed']+state['cycle']
    state.setdefault('proposal_history',[[0,0.]])
    for key in ('refinement_calls','refinement_geometry_probes','refinement_validation_trials'): state.setdefault(key,0)
    segment_file=folder/'sessions.json'
    segments=json.loads(segment_file.read_text()) if segment_file.exists() else []
    segments.append(dict(step=state['step'],proposals=state['proposals'],settings=s,started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z')))
    atomic_json(segment_file,segments)
    statistics=folder/'statistics.csv'
    if statistics.exists():
        with statistics.open(newline='',encoding='utf-8') as stream:
            reader=csv.DictReader(stream);old_fields=reader.fieldnames;rows=list(reader)
        if old_fields!=FIELDS:
            with statistics.with_suffix('.tmp').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader()
                for row in rows: writer.writerow({k:row.get(k,s[k] if k in ('triangles','width') else '') for k in FIELDS})
            from .checkpoint import atomic_replace
            atomic_replace(statistics.with_suffix('.tmp'),statistics)
    mode='refined' if s['refinement'] else 'color-fit' if s['color_fit'] else 'evolution-only'
    cfg.update(project_id=project['id'],project_state=state,project_settings=s,
        experiment_method='project',images=images,width=width,height=height,triangles=len(v),
        color_model='affine-gouraud',objective='color',black_penalty=.15)
    current=render_gouraud(v,colors,width,height,BASES)
    base_elapsed=state['elapsed'];began=time.perf_counter();completed=0
    def stopped():
        try: return (folder/'control.txt').read_text().strip()=='stop'
        except OSError: return False
    def publish(status,event=None):
        state['elapsed']=base_elapsed+time.perf_counter()-began
        terms=obj.terms(current);fitness=1-terms['total']/obj.baseline
        if event:
            if not history or history[-1]!=[state['step'],fitness]: history.append([state['step'],fitness])
            if state['proposal_history'][-1]!=[state['proposals'],fitness]: state['proposal_history'].append([state['proposals'],fitness])
        save(checkpoint,v,colors,state['step'],history,cfg)
        progress=dict(status=status,cycle=state['cycle'],triangle=state['within_pass'],step=state['step'],
            triangles=len(v),width=width,height=height,
            proposals=state['proposals'],fitness=fitness,loss=terms['total'],loss_terms=terms,
            baseline=obj.baseline,history=history,seconds=state['elapsed'],mode=mode,
            proposal_history=state['proposal_history'],
            accepted=state['accepted'],global_solves=state['global_solves'],
            plateau_streak=state['plateau_streak'],plateau_patience=s['plateau_patience'],
            relative_cycle_gain=state.get('relative_cycle_gain'),
            refined_candidates=state['refined_candidates'],refine_steps_accepted=state['refine_steps_accepted'])
        progress.update({key:state[key] for key in ('refinement_calls','refinement_geometry_probes','refinement_validation_trials')})
        atomic_json(folder/'progress.json',progress)
        project['state']={k:progress[k] for k in ('status','cycle','triangle','step','proposals','fitness','loss','seconds','plateau_streak')}
        atomic_json(path,project)
        if event:
            # The checkpoint is committed before appending its statistics row.
            file=folder/'statistics.csv';header=not file.exists()
            with file.open('a',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=FIELDS)
                if header: writer.writeheader()
                writer.writerow(dict(step=state['step'],cycle=state['cycle'],triangle=state['within_pass'],
                    proposals=state['proposals'],loss=terms['total'],interior_color=terms['interior_color'],
                    black_spill=terms['black_spill'],fitness=fitness,seconds=state['elapsed'],event=event,mode=mode,
                    **{key:state[key] for key in ('refinement_calls','refinement_geometry_probes','refinement_validation_trials')},**s))
        if observer is not None: observer(progress,event)
    publish('running','resume' if checkpoint.exists() and state['step'] else 'start')
    try:
        while True:
            order=np.random.default_rng(state['pass_seed']).permutation(len(v))
            for j in range(state['within_pass'],len(v)):
                if stopped(): publish('stopped','stop');return
                i=int(order[j]);old=v[i].copy();old_c=colors[i].copy()
                add(current,old,old_c,-1.)
                residual=np.ascontiguousarray(obj.target-current)
                best_v=old;best_c=old_c;best_gain=color_gain(old,old_c,residual,obj.weights)
                if s['color_fit']:
                    c,gain=local_fit(old,residual,obj.weights)
                    if gain>best_gain: best_c=c;best_gain=gain
                np.random.seed((s['seed']+31*state['step'])%(2**32))
                centroid=old.ravel() if s['color_fit'] else np.r_[old.ravel(),old_c.ravel()/6.]
                strategy=cma.Strategy(centroid=centroid,sigma=s['sigma'],lambda_=s['population'])
                proposed=0;refined=0;refined_steps=0
                for generation in range(s['generations']):
                    population=strategy.generate(creator.LisaIndividual)
                    for ind in population:
                        candidate=constrain(ind[:9])
                        if s['color_fit']: c,gain=local_fit(candidate,residual,obj.weights)
                        else:
                            c=np.clip(np.asarray(ind[9:]).reshape(3,3)*6.,0.,.4)
                            gain=color_gain(candidate,c,residual,obj.weights)
                        if s['refinement']:
                            raw=gain;candidate,c,gain,stats=refine(candidate,c,gain,residual,obj.weights,s['refine_radius'],s['refine_difference'],s['refine_steps'])
                            refined+=int(gain>raw+1e-14);refined_steps+=stats['accepted']
                            state['refinement_calls']+=1
                            state['refinement_geometry_probes']+=stats['geometry_probes']
                            state['refinement_validation_trials']+=stats['trials']
                        ind[:]=candidate.ravel().tolist() if s['color_fit'] else np.r_[candidate.ravel(),c.ravel()/6.].tolist()
                        ind.fitness.values=(-gain,);proposed+=1
                        if gain>best_gain+1e-14: best_v=candidate;best_c=c;best_gain=gain
                    strategy.update(population)
                state['accepted']+=int(not np.array_equal(best_v,old) or not np.array_equal(best_c,old_c))
                v[i]=best_v;colors[i]=best_c;add(current,best_v,best_c)
                state['within_pass']=j+1;state['step']+=1;state['proposals']+=proposed
                state['refined_candidates']+=refined;state['refine_steps_accepted']+=refined_steps
                completed+=1;publish('running','triangle')
                if max_triangles is not None and completed>=max_triangles: publish('stopped','budget');return
            if stopped(): publish('stopped','stop');return
            if s['color_fit']:
                publish('global_rgb')
                output=folder/f"global-{state['cycle']+1:06}"
                if not (output/'best.npz').exists(): fit(checkpoint,output)
                solved=read_checkpoint(output/'best.npz')
                if not np.array_equal(solved['vertices'],v): raise ValueError('Global RGB checkpoint geometry mismatch')
                candidate=render_gouraud(v,solved['colors'],width,height,BASES)
                if obj.terms(candidate)['total']<=obj.terms(current)['total']:
                    colors=solved['colors'];current=candidate
                state['global_solves']+=1
            # Plateau decisions use an independent full mesh reconstruction.
            current=render_gouraud(v,colors,width,height,BASES)
            loss=obj.terms(current)['total'];state['cycle']+=1;state['within_pass']=0
            state['pass_seed']=s['seed']+state['cycle']
            state['plateau_streak'],state['relative_cycle_gain']=plateau_count(state['cycle_start_loss'],loss,state['plateau_streak'],state['cycle'],s)
            state['cycle_start_loss']=loss
            converged=s['auto_stop'] and state['plateau_streak']>=s['plateau_patience']
            publish('plateau' if converged else 'running','cycle')
            if converged: return
    except BaseException:
        # Never save a mesh with its current triangle temporarily subtracted.
        current=render_gouraud(v,colors,width,height,BASES)
        publish('stopped','interrupted');raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--max-triangles',type=int)
    args=parser.parse_args();run(args.project,args.max_triangles)


if __name__=='__main__': main()
