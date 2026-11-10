"""Serial, end-to-end pure-evolution versus memetic plateau benchmark.

Parent prepares immutable paired starts; children time actual project workers.
No desktop windows are opened. JSONL records include publication/I/O costs.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time


class SystemLoad:
    """Aggregate Windows CPU diagnostics; no process control or desktop access."""
    def __init__(self):
        self.previous=None
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            self.ctypes=ctypes;self.FILETIME=wintypes.FILETIME
            self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            self.kernel.GetSystemTimes.argtypes=[ctypes.POINTER(wintypes.FILETIME)]*3

    def sample(self,wall,cpu):
        if os.name!='nt': return {}
        values=[self.FILETIME() for _ in range(3)]
        if not self.kernel.GetSystemTimes(*(self.ctypes.byref(v) for v in values)): return {}
        idle,kernel,user=[(v.dwHighDateTime<<32)+v.dwLowDateTime for v in values]
        current=(idle,kernel+user,wall,cpu);previous=self.previous;self.previous=current
        if previous is None: return {}
        total=current[1]-previous[1];dt=wall-previous[2]
        if total<=0 or dt<=0: return {}
        busy=max(0.,min(1.,1-(idle-previous[0])/total))
        own=max(0.,(cpu-previous[3])/dt/max(1,os.cpu_count() or 1))
        return dict(system_cpu_percent=100*busy,estimated_other_cpu_percent=100*max(0.,busy-own))


def first_fitness_hit(rows,target,initial_fitness,tolerance=1e-8):
    if initial_fitness>=target-tolerance:
        return dict(wall_seconds=0.,cpu_seconds=0.,fitness=initial_fitness,proposals=0,event='initial_state')
    return next((row for row in rows if row['fitness']>=target-tolerance),None)


def wait_for_quiet(root):
    """Wait for 20 seconds of reasonably low aggregate CPU load."""
    if os.name!='nt': return
    from .train import atomic_json
    load=SystemLoad();load.sample(time.perf_counter(),time.process_time());samples=[]
    while not (root/'CANCEL').exists():
        time.sleep(2)
        reading=load.sample(time.perf_counter(),time.process_time())
        samples.append(reading.get('system_cpu_percent',100.));samples=samples[-10:]
        atomic_json(root/'load-gate.json',dict(samples=samples,mean=sum(samples)/len(samples),required_samples=10,mean_limit=5.,peak_limit=10.))
        if len(samples)==10 and sum(samples)/10<5. and max(samples)<10.: return


def child(project):
    began=time.perf_counter();cpu=time.process_time()
    load=SystemLoad();load.sample(time.perf_counter(),time.process_time())
    from .project_worker import run
    from .project import run_directory
    from .train import atomic_json
    folder=run_directory(project);trace=folder/'timing.jsonl'
    # New trial folders only. Resuming a timing trial would require accounting
    # for separate measured sessions, so it is deliberately not automatic.
    if trace.exists(): raise FileExistsError('Timing trace already exists')
    with trace.open('w',encoding='utf-8') as stream:
        def observe(p,event):
            record={k:p.get(k) for k in ('status','cycle','triangle','step','proposals','loss','fitness','loss_terms','plateau_streak','relative_cycle_gain',
                'refinement_calls','refinement_geometry_probes','refinement_validation_trials')}
            record.update(event=event,wall_seconds=time.perf_counter()-began,cpu_seconds=time.process_time()-cpu)
            record.update(load.sample(time.perf_counter(),time.process_time()))
            stream.write(json.dumps(record)+'\n');stream.flush()
            if (folder.parent/'CANCEL').exists(): (folder/'control.txt').write_text('stop')
        run(project,observer=observe)
    atomic_json(folder/'timing-end.json',dict(wall_seconds=time.perf_counter()-began,cpu_seconds=time.process_time()-cpu))


def prepare(root,seeds,source):
    import numpy as np
    from .checkpoint import read_checkpoint
    from .geometry import BASES
    from .gouraud import render_gouraud
    from .objective import ColorObjective
    from .targets import load
    from .project import create_project,run_directory
    from .train import save,atomic_json
    source=Path(source).resolve();d=read_checkpoint(source);cfg=json.loads(str(d['config']))
    obj=ColorObjective(load(cfg['images'],640,480),.15)
    initial_loss=obj.terms(render_gouraud(d['vertices'],d['colors'],640,480,BASES))['total']
    tasks=[]
    for pair,seed in enumerate(seeds):
        # Counterbalance method order to reduce cache/order bias.
        order=['ga','memetic'] if pair%2==0 else ['memetic','ga']
        for method in order:
            path=root/f'{method}-s{seed}.json'
            settings=dict(seed=seed,color_fit=method=='memetic',refinement=method=='memetic',auto_stop=True)
            if not path.exists():
                project=create_project(path,cfg['images'],settings);folder=run_directory(path,project)
                state=dict(cycle=0,within_pass=0,step=0,proposals=0,accepted=0,
                    plateau_streak=0,cycle_start_loss=initial_loss,elapsed=0.,global_solves=0,
                    refined_candidates=0,refine_steps_accepted=0,pass_seed=seed,
                    proposal_history=[[0,1-initial_loss/obj.baseline]])
                copied=dict(cfg,project_id=project['id'],project_state=state,project_settings=project['settings'],experiment_method='project')
                save(folder/'best.npz',d['vertices'],d['colors'],0,[[0,1-initial_loss/obj.baseline]],copied)
            tasks.append(dict(method=method,seed=seed,project=str(path.resolve())))
    manifest=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),initial_loss=initial_loss,initial_fitness=1-initial_loss/obj.baseline,
        relative_targets=[.001,.005,.01,.02,.05],seeds=seeds,tasks=tasks,
        equal_quality_rule='Minimum of the two best attained fitness values; first recorded attainment in each timeline',fitness_tolerance=1e-8,
        settings=dict(population=8,generations=3,sigma=.005,refine_radius=4.,refine_difference=2.,refine_steps=3,
            plateau_relative=.001,plateau_patience=3,plateau_min_passes=3),
        scope='Identical warm-start geometry and colors; actual application workers, no UI; sequential runs, one BLAS thread',
        platform=platform.platform(),python=sys.version,processor=platform.processor())
    atomic_json(root/'protocol.json',manifest)
    return manifest


def summarize(root):
    from .train import atomic_json
    if (root/'INVALIDATED.json').exists(): raise RuntimeError('This timing batch was invalidated; do not report its times')
    protocol=json.loads((root/'protocol.json').read_text());initial=protocol['initial_loss'];records=[]
    for task in protocol['tasks']:
        from .project import run_directory
        folder=run_directory(task['project']);trace=folder/'timing.jsonl'
        if not trace.exists(): continue
        rows=[]
        for line in trace.read_text().splitlines():
            try: rows.append(json.loads(line))
            except ValueError: pass
        if not rows: continue
        last=rows[-1];end=folder/'timing-end.json'
        item=dict(method=task['method'],seed=task['seed'],last=last,complete=end.exists() and last['status']=='plateau',terminated=end.exists(),targets=[])
        item['best_fitness']=max(r['fitness'] for r in rows)
        item['best_fitness_time']=first_fitness_hit(rows,item['best_fitness'],protocol['initial_fitness'],protocol['fitness_tolerance'])
        loads=[r['estimated_other_cpu_percent'] for r in rows if 'estimated_other_cpu_percent' in r]
        item['load_diagnostics']=dict(max_estimated_other_cpu_percent=max(loads,default=0.),samples_above_10_percent=sum(x>10 for x in loads),samples=len(loads))
        if end.exists(): item['timing']=json.loads(end.read_text())
        outer=folder/'process-timing.json'
        if outer.exists(): item['process_timing']=json.loads(outer.read_text())
        for relative in protocol['relative_targets']:
            threshold=initial*(1-relative)
            hit=next((r for r in rows if r['loss']<=threshold),None)
            item['targets'].append(dict(relative_gain=relative,target_loss=threshold,hit=hit))
        records.append(item)
    # User-defined equal quality: rewind the better run's actual timeline to
    # the weaker run's best attained fitness. Also retain first hits for both.
    shared=[]
    for seed in protocol['seeds']:
        pair=[r for r in records if r['seed']==seed]
        if len(pair)!=2: continue
        both_complete=all(r['complete'] for r in pair)
        # Once a finished weaker run is below an unfinished run's attained
        # best, future improvements cannot change their shared target.
        target_finalized=both_complete or any(r['complete'] and r['best_fitness']<=other['best_fitness'] for r in pair for other in pair if r is not other)
        if not target_finalized: continue
        quality=min(r['best_fitness'] for r in pair)
        hits={}
        for r in pair:
            folder=run_directory(next(t['project'] for t in protocol['tasks'] if t['seed']==seed and t['method']==r['method']))
            rows=[json.loads(line) for line in (folder/'timing.jsonl').read_text().splitlines()]
            hit=first_fitness_hit(rows,quality,protocol['initial_fitness'],protocol['fitness_tolerance'])
            hits[r['method']]=hit
        shared.append(dict(seed=seed,fitness=quality,fitness_tolerance=protocol['fitness_tolerance'],
            criterion=protocol['equal_quality_rule'],hits=hits,
            both_plateaus_measured=both_complete,target_finalized=target_finalized,
            target_already_in_initial_state=protocol['initial_fitness']>=quality-protocol['fitness_tolerance']))
    not_started=[task for task in protocol['tasks'] if not (run_directory(task['project'])/'timing.jsonl').exists()]
    atomic_json(root/'results.json',dict(valid=True,protocol=protocol,runs=records,shared_quality=shared,not_started=not_started))
    return records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--child');parser.add_argument('--output',default='runs/timing-convergence')
    parser.add_argument('--source',default='runs/baldwin-plus/baseline.npz');parser.add_argument('--seeds',type=int,nargs='+',default=[23,47,71]);parser.add_argument('--summarize',action='store_true')
    parser.add_argument('--user-confirmed-idle',action='store_true',help='User confirmed no builds/heavy jobs; retain load diagnostics without an automatic start gate')
    args=parser.parse_args()
    if args.child: child(args.child);return
    root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=True)
    if (root/'INVALIDATED.json').exists(): raise RuntimeError('Invalidated output directory; choose a new batch')
    if args.summarize: summarize(root);return
    manifest=prepare(root,args.seeds,args.source)
    from .project import run_directory
    from .train import atomic_json
    manifest['user_confirmed_no_heavy_jobs']=args.user_confirmed_idle
    atomic_json(root/'protocol.json',manifest)
    atomic_json(root/'coordinator.json',dict(pid=os.getpid()))
    for task in manifest['tasks']:
        if (root/'CANCEL').exists(): atomic_json(root/'active.json',dict(status='cancelled'));return
        folder=run_directory(task['project'])
        if (folder/'timing-end.json').exists():
            rows=[json.loads(line) for line in (folder/'timing.jsonl').read_text().splitlines()]
            if rows[-1]['status']!='plateau': raise RuntimeError('This run stopped before plateau; resume its project separately or create a new timed batch. Do not silently skip it.')
            continue
        if (folder/'timing.jsonl').exists(): raise RuntimeError('Incomplete timed run requires explicit recovery, not silent restart')
        atomic_json(root/'active.json',dict(status='waiting_for_low_load',next_task=task))
        if not args.user_confirmed_idle: wait_for_quiet(root)
        if (root/'CANCEL').exists(): atomic_json(root/'active.json',dict(status='cancelled'));return
        atomic_json(root/'active.json',task)
        print('START',task,flush=True);began=time.perf_counter()
        flags=(subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name=='nt' else 0
        with (folder/'timed-worker.log').open('w',encoding='utf-8') as log:
            process=subprocess.run([sys.executable,'-m','lisa2.timing_trial','--child',task['project']],stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        atomic_json(folder/'process-timing.json',dict(wall_seconds=time.perf_counter()-began,returncode=process.returncode))
        if (root/'CANCEL').exists(): atomic_json(root/'active.json',dict(status='cancelled'));return
        summarize(root)
        if process.returncode: raise RuntimeError(f"Timed run failed: {task}")
        print('FINISH',task,flush=True)
    atomic_json(root/'active.json',dict(status='complete'));summarize(root)


if __name__=='__main__':main()
