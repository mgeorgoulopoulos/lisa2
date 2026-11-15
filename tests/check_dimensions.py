"""Custom project sizes propagate through training, RGB, previews and exports."""
import hashlib,json,tempfile
from pathlib import Path
from PIL import Image,ImageDraw
from lisa2.project import DEFAULTS,create_project,read_project,run_directory,update_settings,export_obj,validate_settings
from lisa2.project_worker import run
from lisa2.checkpoint import read_checkpoint
from lisa2.derived import checkpoint_views
from lisa2.gif_export import export_gif

assert DEFAULTS['triangles']==768 and DEFAULTS['width']==640
root=Path('runs/dimension-tests');root.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=root.resolve()) as temp:
    folder=Path(temp);images=[]
    for i in range(4):
        p=folder/f'{i}.png';im=Image.new('RGB',(64,48));ImageDraw.Draw(im).ellipse((10,6,54,42),fill=(120,60+i*30,180));im.save(p);images.append(p)
    project=folder/'custom.json'
    create_project(project,images,dict(triangles=8,width=64,population=4,generations=1,refine_steps=1,plateau_relative=.99,plateau_patience=1,plateau_min_passes=1))
    run(project)
    data=read_project(project);path=run_directory(project);d=read_checkpoint(path/'best.npz')
    progress=json.loads((path/'progress.json').read_text())
    assert progress['status']=='plateau' and progress['cycle']==1
    assert progress['triangles']==8 and progress['width']==64 and progress['height']==48 and progress['global_solves']==1
    assert d['vertices'].shape==(8,3,3) and d['colors'].shape==(8,3,3)
    assert json.loads((path/'global-000001-contours-20-6-thickness/progress.json').read_text())['matrix_shape'][1]==24
    assert all(im.size==(64,48) for im in checkpoint_views(path/'best.npz')['views'])
    gif=folder/'custom.gif';export_gif(path/'best.npz',gif,fps=5)
    with Image.open(gif) as im: assert im.size==(64,48)
    obj=folder/'custom.obj';export_obj(path/'best.npz',obj)
    assert sum(line.startswith('v ') for line in obj.read_text().splitlines())==24
    assert json.loads(obj.with_suffix('.render.json').read_text())['target_resolution']==[64,48]
    original=project.read_bytes();changed=data['settings'].copy();changed['width']=128
    try: update_settings(project,changed);raise AssertionError('Mixed-resolution history accepted')
    except ValueError: pass
    assert project.read_bytes()==original
    changed=data['settings'].copy();changed['auto_stop']=False;update_settings(project,changed)
    history=d['history'].copy();run(project,max_triangles=2)
    resumed=read_checkpoint(path/'best.npz');assert len(resumed['vertices'])==8 and (resumed['history'][:len(history)]==history).all()
    # Older manifests omit the two fields; infer from their rendering metadata.
    legacy=read_project(project);legacy['settings'].pop('width');legacy['settings'].pop('triangles')
    project.write_text(json.dumps(legacy));assert read_project(project)['settings']['width']==64 and read_project(project)['settings']['triangles']==8
    fresh=folder/'fresh.json';create_project(fresh,images,dict(width=64,triangles=8))
    settings=read_project(fresh)['settings'];settings.update(width=80,triangles=12);update_settings(fresh,settings)
    assert read_project(fresh)['rendering']['height']==60 and read_project(fresh)['rendering']['triangles']==12
    for invalid in (dict(width=66),dict(triangles=0)):
        try: validate_settings(invalid);raise AssertionError('Invalid dimension accepted')
        except ValueError: pass
print('PASS: configurable topology/resolution, full memetic cycle/global fit, resume/history, native previews/GIF/OBJ, legacy manifests and dimension-change protection.')
