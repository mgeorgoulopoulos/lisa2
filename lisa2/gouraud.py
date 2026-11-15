"""Classic affine Gouraud RGB, fitted jointly with bounded least squares."""
import argparse,json,time
from pathlib import Path
import numpy as np
from numba import njit
from scipy.sparse import coo_matrix
from scipy.optimize import lsq_linear
from .raster import projected,cross,bounds,inside
from .geometry import BASES
from .checkpoint import read_checkpoint
from .objective import ColorObjective
from .targets import load


@njit(cache=True)
def footprint(vertices,basis,width,height):
    p=projected(vertices,basis,width,height)
    area=cross(p[0],p[1],p[2,0],p[2,1])
    x0,x1,y0,y1=bounds(p,width,height)
    count=max(0,x1-x0+1)*max(0,y1-y0+1)
    rows=np.empty(count,dtype=np.int64);coeff=np.empty((count,3));n=0
    if abs(area)<1e-8: return rows[:0],coeff[:0]
    for y in range(y0,y1+1):
        for x in range(x0,x1+1):
            if inside(p,x+.5,y+.5):
                a=cross(p[1],p[2],x+.5,y+.5)/area
                b=cross(p[2],p[0],x+.5,y+.5)/area
                rows[n]=y*width+x;coeff[n,0]=a;coeff[n,1]=b;coeff[n,2]=1-a-b;n+=1
    return rows[:n],coeff[:n]


@njit(cache=True)
def render_gouraud(vertices,colors,width,height,bases):
    images=np.zeros((len(bases),height,width,3))
    for k in range(len(bases)):
        for i in range(len(vertices)):
            p=projected(vertices[i],bases[k],width,height)
            area=cross(p[0],p[1],p[2,0],p[2,1])
            if abs(area)<1e-8: continue
            x0,x1,y0,y1=bounds(p,width,height)
            for y in range(y0,y1+1):
                for x in range(x0,x1+1):
                    if inside(p,x+.5,y+.5):
                        a=cross(p[1],p[2],x+.5,y+.5)/area
                        b=cross(p[2],p[0],x+.5,y+.5)/area
                        c=1-a-b
                        for channel in range(3):
                            images[k,y,x,channel]+=a*colors[i,0,channel]+b*colors[i,1,channel]+c*colors[i,2,channel]
    return images


def export_vertex_obj(path,vertices,colors,images=None):
    from .geometry import DIRECTIONS, RADIUS, FOV_Y, ASPECT
    path=Path(path)
    with path.open('w',encoding='ascii') as f:
        f.write('# Lisa2 cameras: JSON comments; center = camera position, lookAt = target.\n')
        f.write('# World coordinates match OBJ vertices; up is orthonormal; perspective fovY is vertical degrees.\n')
        for i,(direction,camera_basis) in enumerate(zip(DIRECTIONS,BASES)):
            camera=dict(view=i+1,center=(RADIUS*direction).tolist(),lookAt=[0.,0.,0.],
                        up=camera_basis[1].tolist(),fovY_degrees=FOV_Y,aspect=ASPECT,
                        image=str(images[i]) if images is not None and i<len(images) else None)
            f.write('# camera '+json.dumps(camera,ensure_ascii=True)+'\n')
        f.write('# Lisa2 Gouraud; OBJ vertex RGB extension: v x y z r g b\n')
        f.write('# Requires two-sided additive blending on black; affine Gouraud RGB.\n')
        for v,c in zip(vertices.reshape(-1,3),colors.reshape(-1,3)):
            f.write('v '+' '.join(f'{x:.9f}' for x in [*v,*c])+'\n')
        for i in range(len(vertices)): f.write(f'f {3*i+1} {3*i+2} {3*i+3}\n')
    np.save(path.with_suffix('.vertex-colors.npy'),colors)


def color_matrix(vertices, width, height, ids):
    rows, columns, values = [], [], []
    for k, basis in enumerate(BASES):
        for i, triangle in enumerate(vertices):
            pixels, barycentric = footprint(triangle, basis, width, height)
            rows.append(np.repeat(pixels + k * width * height, 3))
            columns.append(np.tile(ids[i], len(pixels)))
            values.append(barycentric.ravel())
    return coo_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(columns))),
                      shape=(4 * width * height, int(ids.max()) + 1)).tocsr()


def fit(source,output,max_iterations=40):
    from .train import save,atomic_json
    source=Path(source);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if (out/'best.npz').exists(): raise FileExistsError('Existing run')
    d=read_checkpoint(source);v=d['vertices'];cfg=json.loads(str(d['config']))
    width=int(cfg.get('width',640));height=width*3//4
    target=load(cfg['images'],width,height)
    objective=ColorObjective(target,.15,**cfg.get('contours',{}))
    ids=d.get('vertex_ids',np.arange(len(v)*3).reshape(len(v),3))
    n_colors=int(ids.max())+1
    cap=cfg.get('color_cap',.4)
    original=d['colors']
    if original.ndim==2: original=np.repeat(original[:,None,:],3,axis=1)
    original_image=render_gouraud(v,original,width,height,BASES)
    old_loss=objective.terms(original_image)['total']
    began=time.perf_counter()
    matrix=color_matrix(v,width,height,ids)
    occupied=np.diff(matrix.indptr)>0
    sqrt_weights=np.sqrt(objective.weights.ravel()[occupied])
    design=matrix[occupied].multiply(sqrt_weights[:,None]).tocsr()
    targets=objective.target.reshape(-1,3)[occupied]*sqrt_weights[:,None]
    colors=np.empty((n_colors,3));solvers=[]
    cfg.update(experiment_method='gouraud',source=str(source.resolve()),color_model='affine-gouraud',
        optimizer='SciPy bounded joint least squares; fixed geometry',objective='color',black_penalty=.15)
    history=[]
    for channel in range(3):
        result=lsq_linear(design,targets[:,channel],bounds=(0.,cap),tol=1e-6,
                          lsq_solver='lsmr',lsmr_tol=1e-5,lsmr_maxiter=250,max_iter=max_iterations,verbose=0)
        colors[:,channel]=result.x
        solvers.append(dict(channel=channel,iterations=result.nit,success=bool(result.success),status=int(result.status),optimality=float(result.optimality)))
        print('Gouraud channel',channel,solvers[-1],flush=True)
    colors=colors[ids]
    candidate=render_gouraud(v,colors,width,height,BASES)
    terms=objective.terms(candidate)
    if terms['total']>old_loss:
        colors=original;terms=objective.terms(original_image)
    score=1-terms['total']/objective.baseline
    history=[[0,1-old_loss/objective.baseline],[1,score]]
    save(out/'best.npz',v,colors,1,history,cfg)
    export_vertex_obj(out/'model.obj',v,colors)
    np.save(out/'vertex-ids.npy',ids)
    report=dict(status='complete',step=1,total=1,fitness=score,loss=terms['total'],baseline=objective.baseline,
        loss_terms=terms,history=history,seconds=time.perf_counter()-began,source_loss=old_loss,
        geometry_unchanged=bool(np.array_equal(v,d['vertices'])),triangles=len(v),vertex_colors=len(v)*3,
        solver=solvers,matrix_shape=list(design.shape),nonzeros=int(design.nnz),width=width,height=height)
    atomic_json(out/'progress.json',report)
    print(json.dumps(report,indent=2),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',default='runs/uniform-fine640/best.npz')
    p.add_argument('--output',required=True);p.add_argument('--iterations',type=int,default=40)
    a=p.parse_args();fit(a.source,a.output,a.iterations)

if __name__=='__main__':main()
