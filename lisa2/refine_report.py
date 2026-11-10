"""Independently validate and visualize finished Baldwinian+ experiments."""
import csv,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from .checkpoint import read_checkpoint
from .geometry import BASES,project
from .gouraud import render_gouraud,export_vertex_obj
from .objective import ColorObjective
from .targets import load
from .train import atomic_json


def report(root='runs/baldwin-plus'):
    root=Path(root);baseline=read_checkpoint(root/'baseline.npz')
    cfg=json.loads(str(baseline['config']))
    obj=ColorObjective(load(cfg['images'],640,480),.15)
    baseline_loss=obj.terms(render_gouraud(baseline['vertices'],baseline['colors'],640,480,BASES))['total']
    original=Path('runs/hybrid-gouraud/best.npz')
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(original)==digest(root/'baseline.npz')
    records=[];renders={};convergence=[]
    paths=[root/'baseline.npz']+[p/'best.npz' for p in sorted(root.iterdir()) if p.is_dir() and (p/'progress.json').exists() and json.loads((p/'progress.json').read_text())['status']=='complete']
    for path in paths:
        d=read_checkpoint(path);v=d['vertices'];c=d['colors'];config=json.loads(str(d['config']))
        image=render_gouraud(v,c,640,480,BASES);terms=obj.terms(image)
        assert np.all(np.isfinite(v)) and np.all(np.isfinite(c))
        assert np.max(np.linalg.norm(v,axis=2))<=1+1e-9
        assert np.min(c)>=0 and np.max(c)<=.4+1e-9
        assert np.allclose(image,render_gouraud(v[:,::-1],c[:,::-1],640,480,BASES),atol=1e-10)
        name='baseline' if path.name=='baseline.npz' else path.parent.name
        item=dict(name=name,loss=terms['total'],terms=terms,fitness=1-terms['total']/obj.baseline,sha256=digest(path),parameters=config.get('hybrid_parameters'),refinement=config.get('hybrid_state',{}).get('refinement'))
        displacement=np.linalg.norm(v-baseline['vertices'],axis=2)
        projected_moves=np.stack([np.linalg.norm(project(v.reshape(-1,3),b,640,480)-project(baseline['vertices'].reshape(-1,3),b,640,480),axis=1) for b in BASES])
        item['movement']=dict(world_rms=float(np.sqrt(np.mean(displacement**2))),world_max=float(displacement.max()),projected_max=float(projected_moves.max()),vertices_over_one_pixel=int(np.sum(projected_moves.max(axis=0)>1.)),moved_triangles=int(np.sum(displacement.max(axis=1)>1e-10)))
        if name!='baseline':
            progress=json.loads((path.parent/'progress.json').read_text())
            assert np.isclose(progress['loss'],terms['total'],atol=1e-12)
            assert np.min(np.diff(d['history'][:,1]))>=-1e-10
            item['seconds']=progress['seconds']
            parameters=config['hybrid_parameters']
            multiplier=parameters['generations']*parameters['population']
            item['cma_geometry_proposals']=int(progress['step']*multiplier)
            item['loss_reduction_percent']=100*(1-terms['total']/baseline_loss)
            for step,fitness in d['history']:
                convergence.append(dict(run=name,seed=parameters['seed'],cma_geometry_proposals=int(step*multiplier),loss=(1-fitness)*obj.baseline))
            atomic_json(path.parent/'validation.json',dict(**item,bounds_valid=True,winding_invariant=True,full_loss_matches=True))
            export_vertex_obj(path.parent/'model.obj',v,c)
        records.append(item);renders[name]=image
    atomic_json(root/'results.json',dict(baseline_unchanged=True,baseline_sha256=digest(original),runs=records))
    with (root/'loss-vs-proposals.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=['run','seed','cma_geometry_proposals','loss'])
        writer.writeheader();writer.writerows(convergence)
    labels=['targets','baseline']+[r['name'] for r in sorted(records[1:],key=lambda r:r['loss'])]
    canvas=Image.new('RGB',(1280,len(labels)*264),(15,18,24));draw=ImageDraw.Draw(canvas)
    for row,label in enumerate(labels):
        record=next((r for r in records if r['name']==label),None)
        caption=label if record is None else f"{label}: loss {record['loss']:.10f}"
        draw.text((8,row*264+5),caption,fill='white')
        data=obj.target if label=='targets' else renders[label]
        for k in range(4):
            image=Image.fromarray(np.uint8(np.clip(data[k],0,1)*255))
            image=image.resize((320,240),Image.Resampling.LANCZOS)
            canvas.paste(image,(k*320,row*264+24))
    canvas.save(root/'comparison.png')
    winner=min(records,key=lambda r:r['loss'])['name']
    detail=Image.new('RGB',(2560,3*504),(15,18,24));draw=ImageDraw.Draw(detail)
    for row,label in enumerate(['targets','baseline',winner]):
        draw.text((8,row*504+5),label,fill='white')
        data=obj.target if label=='targets' else renders[label]
        for k in range(4):
            image=Image.fromarray(np.uint8(np.clip(data[k],0,1)*255))
            detail.paste(image,(k*640,row*504+24))
            if label==winner: image.save(root/f'best-view-{k+1}.png')
    detail.save(root/'best-comparison.png')
    for r in records: print(r['name'],r['loss'],r.get('seconds'),flush=True)


if __name__=='__main__':report()
