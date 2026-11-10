"""Two-sided Gouraud geometry CMA with profiled RGB and periodic global solves."""
import argparse,json,time
from pathlib import Path
import numpy as np
from numba import njit
from deap import cma
from .gouraud import footprint,render_gouraud,fit
from .geometry import BASES,constrain
from .objective import ColorObjective
from .targets import load
from .checkpoint import read_checkpoint
from .train import creator,save,atomic_json,export_obj


@njit(cache=True)
def bounded_rgb(gram,rhs,cap=.4):
    colors=np.zeros((3,3));total_gain=0.
    for channel in range(3):
        best=0.;chosen=np.zeros(3)
        for code in range(27):
            state=code;free=np.empty(3,np.int64);n=0;x=np.zeros(3)
            for j in range(3):
                mode=state%3;state//=3
                if mode==0: free[n]=j;n+=1
                elif mode==2: x[j]=cap
            q=rhs[:,channel]-gram@x
            if n==1:
                i=free[0]
                if gram[i,i]<1e-20: continue
                x[i]=q[i]/gram[i,i]
            elif n==2:
                i,j=free[0],free[1];det=gram[i,i]*gram[j,j]-gram[i,j]**2
                if det<=1e-12*max(gram[i,i]*gram[j,j],1e-40): continue
                x[i]=(q[i]*gram[j,j]-q[j]*gram[i,j])/det
                x[j]=(q[j]*gram[i,i]-q[i]*gram[i,j])/det
            elif n==3:
                if np.linalg.det(gram)<=1e-12*max(gram[0,0]*gram[1,1]*gram[2,2],1e-60): continue
                x=np.linalg.solve(gram,q)
            if np.min(x)<-1e-9 or np.max(x)>cap+1e-9: continue
            x=np.minimum(cap,np.maximum(0.,x))
            gain=2*np.dot(x,rhs[:,channel])-np.dot(x,gram@x)
            if gain>best: best=gain;chosen=x.copy()
        colors[:,channel]=chosen;total_gain+=best
    return colors,total_gain


@njit(cache=True)
def moments(vertices,residual,weights):
    height,width=weights.shape[1:];gram=np.zeros((3,3));rhs=np.zeros((3,3))
    for k in range(4):
        rows,a=footprint(vertices,BASES[k],width,height)
        r=residual[k].reshape((-1,3));w=weights[k].reshape(-1)
        for p in range(len(rows)):
            row=rows[p];weight=w[row]
            for i in range(3):
                for j in range(3): gram[i,j]+=weight*a[p,i]*a[p,j]
                for c in range(3): rhs[i,c]+=weight*a[p,i]*r[row,c]
    return gram,rhs


@njit(cache=True)
def local_fit(vertices,residual,weights):
    gram,rhs=moments(vertices,residual,weights)
    return bounded_rgb(gram,rhs)


@njit(cache=True)
def add(images,vertices,colors,scale=1.):
    height,width=images.shape[1:3]
    for k in range(4):
        rows,a=footprint(vertices,BASES[k],width,height)
        pixels=images[k].reshape((-1,3))
        for p in range(len(rows)):
            for c in range(3):
                for j in range(3): pixels[rows[p],c]+=scale*a[p,j]*colors[j,c]


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if args.resume:
        d=read_checkpoint(out/'best.npz');cfg=json.loads(str(d['config']));state=cfg['hybrid_state']
        params=cfg['hybrid_parameters']
        if args.extra_passes: params['passes']=state['pass_no']+args.extra_passes
    else:
        if (out/'best.npz').exists(): raise FileExistsError('Existing run; use --resume')
        d=read_checkpoint(args.source);cfg=json.loads(str(d['config']))
        params=dict(passes=args.passes,generations=args.generations,population=args.population,seed=args.seed,sigma=args.sigma)
        params.update(refine_radius=getattr(args,'refine_radius',0.),refine_difference=getattr(args,'refine_difference',1.),refine_steps=getattr(args,'refine_steps',1))
        state=dict(pass_no=0,within_pass=0,global_solves=0)
        cfg.update(source=str(Path(args.source).resolve()),experiment_method='hybrid-gouraud',color_model='affine-gouraud',objective='color',black_penalty=.15,mutation='uniform',width=640)
    v=d['vertices'].copy();colors=d['colors'].copy()
    state.setdefault('refinement',dict(calls=0,improved=0,accepted_steps=0,trials=0,seconds=0.,summed_candidate_gain=0.))
    if colors.ndim==2: colors=np.repeat(colors[:,None,:],3,axis=1)
    objective=ColorObjective(load(cfg['images'],640,480),.15)
    current=render_gouraud(v,colors,640,480,BASES);initial=float(objective.terms(current)['total'])
    history=d['history'].tolist() if args.resume else [[0,1-initial/objective.baseline]]
    cfg.update(hybrid_parameters=params,hybrid_state=state,optimizer='DEAP geometry CMA-ES; profiled local RGB; periodic SciPy global RGB',generations=params['generations'],population=params['population'],seed=params['seed'],rounds=params['passes'])
    if params.get('refine_radius',0)>0:
        cfg['optimizer']='DEAP CMA-ES; exact local RGB; inherited hard-raster joint local refinement; periodic global RGB'
    began=time.perf_counter()
    def checkpoint(status):
        step=state['pass_no']*len(v)+state['within_pass'];terms=objective.terms(current)
        save(out/'best.npz',v,colors,step,history,cfg)
        atomic_json(out/'progress.json',dict(status=status,step=step,total=params['passes']*len(v),fitness=1-terms['total']/objective.baseline,loss=terms['total'],baseline=objective.baseline,loss_terms=terms,history=history,pass_no=state['pass_no'],global_solves=state['global_solves'],seconds=time.perf_counter()-began))
    checkpoint('running')
    try:
        while state['pass_no']<params['passes']:
            order=np.random.default_rng(params['seed']+state['pass_no']).permutation(len(v))
            for j in range(state['within_pass'],len(v)):
                control=out/'control.txt';command=control.read_text().strip() if control.exists() else 'run'
                if command=='pause':
                    checkpoint('paused')
                    while control.exists() and control.read_text().strip()=='pause': time.sleep(.15)
                    command=control.read_text().strip() if control.exists() else 'run';checkpoint('running')
                if command=='stop': checkpoint('stopped');export_obj(out/'model.obj',v,colors);return
                i=int(order[j]);old=v[i].copy();old_c=colors[i].copy();add(current,old,old_c,-1.)
                residual=np.ascontiguousarray(objective.target-current)
                best_v=old;gram,rhs=moments(old,residual,objective.weights)
                best_c,best_gain=bounded_rgb(gram,rhs)
                # The current colors are always feasible; protect against degenerate fits.
                old_gain=float(2*np.sum(old_c*rhs)-np.sum(old_c*(gram@old_c)))
                if old_gain>best_gain: best_gain=old_gain;best_c=old_c
                step=state['pass_no']*len(v)+j;np.random.seed(params['seed']+31*step)
                strategy=cma.Strategy(centroid=old.ravel(),sigma=params['sigma'],lambda_=params['population'])
                for generation in range(params['generations']):
                    population=strategy.generate(creator.LisaIndividual)
                    for ind in population:
                        candidate=constrain(ind);c,gain=local_fit(candidate,residual,objective.weights)
                        if params.get('refine_radius',0)>0:
                            from .local_refine import refine
                            raw_gain=gain;refine_started=time.perf_counter()
                            candidate,c,gain,stats=refine(candidate,c,gain,residual,objective.weights,
                                params['refine_radius'],params['refine_difference'],params['refine_steps'])
                            counters=state['refinement'];counters['calls']+=1
                            counters['seconds']+=time.perf_counter()-refine_started
                            counters['improved']+=int(gain>raw_gain+1e-14)
                            counters['accepted_steps']+=stats['accepted'];counters['trials']+=stats['trials']
                            counters['summed_candidate_gain']+=float(gain-raw_gain)
                            # Inherit the evaluated, repaired/refined coordinates.
                            ind[:]=candidate.ravel().tolist()
                        ind.fitness.values=(-gain,)
                        if gain>best_gain: best_v=candidate;best_c=c;best_gain=gain
                    strategy.update(population)
                v[i]=best_v;colors[i]=best_c;add(current,best_v,best_c)
                state['within_pass']=j+1
                if (j+1)%64==0:
                    loss=objective.terms(current)['total'];history.append([step+1,1-loss/objective.baseline]);checkpoint('running')
                    print(f'Hybrid {step+1}: physical loss={loss:.9f}',flush=True)
            # Coordinate updates have moved the mesh; jointly re-optimize every color.
            checkpoint('running');state['global_solves']+=1
            global_out=out/f'global-{state["global_solves"]:03}'
            if not (global_out/'best.npz').exists(): fit(out/'best.npz',global_out)
            solved=read_checkpoint(global_out/'best.npz');candidate=render_gouraud(v,solved['colors'],640,480,BASES)
            if objective.terms(candidate)['total']<=objective.terms(current)['total']:
                colors=solved['colors'];current=candidate
            state['pass_no']+=1;state['within_pass']=0
            history.append([state['pass_no']*len(v),1-objective.terms(current)['total']/objective.baseline]);checkpoint('running')
            export_obj(out/'model.obj',v,colors)
    except KeyboardInterrupt:
        # A signal may arrive after subtracting a triangle: reconstruct the
        # committed geometry/colors before reporting or saving any state.
        current=render_gouraud(v,colors,640,480,BASES)
        checkpoint('stopped');export_obj(out/'model.obj',v,colors);return
    checkpoint('complete');export_obj(out/'model.obj',v,colors)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--source',default='runs/joint-gouraud/best.npz')
    p.add_argument('--passes',type=int,default=4);p.add_argument('--generations',type=int,default=6);p.add_argument('--population',type=int,default=12)
    p.add_argument('--sigma',type=float,default=.005);p.add_argument('--seed',type=int,default=23);p.add_argument('--resume',action='store_true');p.add_argument('--extra-passes',type=int,default=0)
    p.add_argument('--refine-radius',type=float,default=0.,help='Maximum projected vertex move per local step in pixels; zero disables')
    p.add_argument('--refine-difference',type=float,default=1.,help='Finite-difference pixel scale')
    p.add_argument('--refine-steps',type=int,default=1)
    a=p.parse_args()
    if a.passes<1 or a.population<4 or a.generations<1 or a.sigma<=0: p.error('Invalid optimization budget')
    if a.refine_radius<0 or a.refine_difference<=0 or a.refine_steps<1: p.error('Invalid refinement parameters')
    run(a)

if __name__=='__main__':main()
