"""Reproducible parameter screening on frozen-baseline candidate proposals."""
import argparse, hashlib, json, shutil, time
from pathlib import Path
import numpy as np
from .checkpoint import read_checkpoint
from .geometry import BASES,constrain
from .gouraud import render_gouraud
from .hybrid_gouraud import add,local_fit
from .local_refine import refine
from .objective import ColorObjective
from .targets import load
from .train import atomic_json


def screen(out,seed=73,count=24):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    source=Path('runs/hybrid-gouraud/best.npz')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    frozen=out/'baseline.npz'
    if not frozen.exists(): shutil.copy2(source,frozen)
    assert hashlib.sha256(frozen.read_bytes()).hexdigest()==digest
    d=read_checkpoint(frozen);v=d['vertices'];colors=d['colors'];cfg=json.loads(str(d['config']))
    obj=ColorObjective(load(cfg['images'],640,480),.15)
    image=render_gouraud(v,colors,640,480,BASES)
    baseline=obj.terms(image)
    settings=[(1.,.5,1),(2.,1.,1),(4.,2.,1),(2.,2.,1),(4.,1.,1),(2.,1.,2),
              (2.,2.,2),(4.,2.,2),(4.,2.,3),(8.,4.,1),(4.,4.,2),(2.,1.,3)]
    results=[dict(radius=r,difference=h,steps=s,seconds=0.,gain=0.,wins=0,accepted=0,trials=0,displacement_max=0.,cases=[]) for r,h,s in settings]
    rng=np.random.default_rng(seed)
    began=time.perf_counter()
    for n,i in enumerate(rng.choice(len(v),count,replace=False)):
        rest=image.copy();add(rest,v[i],colors[i],-1.)
        residual=np.ascontiguousarray(obj.target-rest)
        # Include both near-baseline and ordinary CMA-scale perturbations.
        proposal=constrain(v[i]+rng.normal(0,.005,(3,3)))
        c,g=local_fit(proposal,residual,obj.weights)
        for record in results:
            start=time.perf_counter()
            nv,nc,ng,stats=refine(proposal,c,g,residual,obj.weights,record['radius'],record['difference'],record['steps'])
            record['seconds']+=time.perf_counter()-start
            record['gain']+=ng-g;record['wins']+=int(ng>g+1e-14)
            record['accepted']+=stats['accepted'];record['trials']+=stats['trials']
            record['displacement_max']=max(record['displacement_max'],float(np.linalg.norm(nv-proposal,axis=1).max()))
            record['cases'].append(dict(triangle=int(i),gain_before=float(g),gain_after=float(ng)))
        atomic_json(out/f'screen-{seed}.json',dict(seed=seed,count=count,completed=n+1,baseline_sha256=digest,baseline=baseline,settings=results,seconds=time.perf_counter()-began))
        print(f'Screen {seed} {n+1}/{count}: '+str([(r['radius'],r['difference'],r['steps'],round(r['gain'],7),round(r['seconds'],1)) for r in results]),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='runs/baldwin-plus');p.add_argument('--seed',type=int,default=73);p.add_argument('--count',type=int,default=24)
    a=p.parse_args();screen(a.output,a.seed,a.count)
