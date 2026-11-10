"""Project portability, deterministic resume, all modes and real auto-stop."""
import csv,json,shutil
from pathlib import Path
import tempfile
import numpy as np
from PIL import Image,ImageDraw
from lisa2.project import create_project,read_project,run_directory,clone_project,export_obj,update_settings
from lisa2.project_worker import run,plateau_count,acquire_lock
from lisa2.checkpoint import read_checkpoint
from lisa2.train import save

base=Path('runs/project-tests');base.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=base.resolve()) as temp:
    root=Path(temp);images=[]
    for i in range(4):
        im=Image.new('RGB',(80,60));draw=ImageDraw.Draw(im)
        draw.polygon([(12,45),(40+i*3,8),(65,43)],fill=(70+i*20,140,190-i*20))
        path=root/f'image-{i}.png';im.save(path);images.append(path)
    settings=dict(population=4,generations=1,refine_steps=1,auto_stop=False,seed=19)
    a=root/'a.json';b=root/'b.json'
    create_project(a,images,settings);create_project(b,images,settings)
    run(a,max_triangles=2);run(b,max_triangles=1);run(b,max_triangles=1)
    da=read_checkpoint(run_directory(a)/'best.npz');db=read_checkpoint(run_directory(b)/'best.npz')
    assert np.array_equal(da['vertices'],db['vertices']) and np.array_equal(da['colors'],db['colors'])
    assert np.array_equal(da['history'],db['history'])
    assert json.loads(str(db['config']))['project_state']['proposals']==8
    assert a.stat().st_size<6000
    try: acquire_lock(run_directory(a));acquire_lock(run_directory(a));raise AssertionError('Double writer accepted')
    except RuntimeError: (run_directory(a)/'worker.lock').unlink()
    clone=root/'copy.json';clone_project(b,clone)
    assert read_project(clone)['id']!=read_project(b)['id']
    assert np.array_equal(read_checkpoint(run_directory(clone)/'best.npz')['history'],db['history'])
    changed=read_project(clone)['settings'];changed.update(population=5,generations=2,color_fit=False,refinement=False)
    update_settings(clone,changed);run(clone,max_triangles=1)
    resumed=read_checkpoint(run_directory(clone)/'best.npz');resumed_cfg=json.loads(str(resumed['config']))
    assert resumed_cfg['project_state']['proposals']==18
    assert np.array_equal(resumed['history'][:len(db['history'])],db['history'])
    with (run_directory(clone)/'statistics.csv').open(newline='') as stream:
        last=list(csv.DictReader(stream))[-1]
    assert last['population']=='5' and last['generations']=='2' and last['mode']=='evolution-only'
    relocated=root/'relocated';relocated.mkdir()
    shutil.copy2(clone,relocated/clone.name);shutil.copytree(run_directory(clone),relocated/run_directory(clone).name)
    run(relocated/clone.name,max_triangles=1)
    assert json.loads(str(read_checkpoint(run_directory(relocated/clone.name)/'best.npz')['config']))['project_state']['proposals']==28
    out=root/'mesh.obj';export_obj(run_directory(b)/'best.npz',out)
    lines=out.read_text().splitlines();assert sum(x.startswith('v ') for x in lines)==2304
    assert all(len(x.split())==7 for x in lines if x.startswith('v '))
    assert np.array_equal(np.load(out.with_suffix('.vertex-colors.npy')),db['colors'])
    assert json.loads(out.with_suffix('.render.json').read_text())['depth_test'] is False
    # All modes share the same physical objective; only their search differs.
    for name,extra in [('ga',dict(color_fit=False,refinement=False)),('rgb',dict(color_fit=True,refinement=False))]:
        path=root/f'{name}.json';create_project(path,images,{**settings,**extra});run(path,max_triangles=1)
        d=read_checkpoint(run_directory(path)/'best.npz');cfg=json.loads(str(d['config']))
        assert cfg['project_state']['proposals']==4
        assert cfg['project_state']['refined_candidates']==0
        assert np.min(d['colors'])>=0 and np.max(d['colors'])<=.4
        assert d['history'][-1,1]>=d['history'][0,1]
    # Exercise the actual cycle boundary and auto-stop without running 768 trials.
    folder=run_directory(root/'ga.json');d=read_checkpoint(folder/'best.npz');cfg=json.loads(str(d['config']))
    progress=json.loads((folder/'progress.json').read_text())
    cfg['project_state'].update(within_pass=768,cycle_start_loss=progress['loss'])
    save(folder/'best.npz',d['vertices'],d['colors'],int(d['step']),d['history'],cfg)
    new=read_project(root/'ga.json')['settings'];new.update(auto_stop=True,plateau_patience=1,plateau_min_passes=1)
    update_settings(root/'ga.json',new);run(root/'ga.json')
    progress=json.loads((folder/'progress.json').read_text());assert progress['status']=='plateau' and progress['cycle']==1
    assert plateau_count(1.,.9995,2,5,new)[0]==3
    assert plateau_count(1.,.9,2,5,new)[0]==0
    sessions=json.loads((run_directory(b)/'sessions.json').read_text());assert len(sessions)==2
    assert not (run_directory(b)/'worker.lock').exists()
print('PASS: portable small projects, exact stop/resume equivalence, all evolution modes, full history, locking, OBJ vertex RGB and automatic plateau stop.')
