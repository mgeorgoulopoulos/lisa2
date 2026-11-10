"""Portable small JSON projects; meshes and full histories live beside them."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
from PIL import Image,ImageOps
from .train import atomic_json

DEFAULTS=dict(color_fit=True,refinement=True,auto_stop=True,population=8,
              generations=3,seed=23,sigma=.005,refine_radius=4.,
              refine_difference=2.,refine_steps=3,plateau_relative=.001,
              plateau_patience=3,plateau_min_passes=3,triangles=768,width=640)


def validate_settings(settings):
    s={**DEFAULTS,**settings}
    for key in ('color_fit','refinement','auto_stop'):
        if type(s[key]) is not bool: raise ValueError(f'{key} must be true or false')
    for key,minimum in (('population',4),('generations',1),('seed',0),('refine_steps',1),('plateau_patience',1),('plateau_min_passes',1),('triangles',1),('width',4)):
        if type(s[key]) is not int or s[key]<minimum: raise ValueError(f'Invalid {key}')
    import math
    for key in ('sigma','refine_radius','refine_difference','plateau_relative'):
        if not math.isfinite(float(s[key])) or s[key]<=0: raise ValueError(f'Invalid {key}')
    if s['plateau_relative']>=1: raise ValueError('Plateau threshold must be below 100%')
    if s['width']%4: raise ValueError('Target width must be a multiple of four (4:3 aspect ratio)')
    if s['refinement'] and not s['color_fit']: raise ValueError('Joint refinement requires exact color fitting')
    return s


def read_project(path):
    path=Path(path).resolve()
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('format')!='Lisa2 project' or data.get('version')!=1: raise ValueError('Not a supported Lisa2 project')
    if len(data.get('images',[]))!=4: raise ValueError('Project must contain four image slots')
    settings=data['settings'].copy()
    for key in ('triangles','width'): settings.setdefault(key,data.get('rendering',{}).get(key,DEFAULTS[key]))
    data['settings']=validate_settings(settings)
    return data


def resolve(path,value):
    return (Path(path).resolve().parent/value).resolve()


def run_directory(path,data=None):
    return resolve(path,(data or read_project(path))['data_directory'])


def image_paths(path,data=None):
    return [str(resolve(path,p)) for p in (data or read_project(path))['images']]


def create_project(path,images,settings=None):
    path=Path(path).resolve()
    if path.exists(): raise FileExistsError('Choose a new project filename; existing projects are never overwritten')
    if len(images)!=4: raise ValueError('Choose exactly four images')
    settings=validate_settings(settings or {})
    # Validate all inputs before creating the project or its data directory.
    for source in images:
        with Image.open(source) as im: im.verify()
    folder=path.parent/(path.stem+'.data')
    if folder.exists(): folder=path.parent/(path.stem+'-'+uuid.uuid4().hex[:8]+'.data')
    (folder/'images').mkdir(parents=True)
    managed=[];hashes=[]
    for i,source in enumerate(images):
        dest=folder/'images'/f'{i+1}.png'
        with Image.open(source) as im: ImageOps.exif_transpose(im).convert('RGB').save(dest)
        managed.append(os.path.relpath(dest,path.parent))
        hashes.append(hashlib.sha256(dest.read_bytes()).hexdigest())
    data=dict(format='Lisa2 project',version=1,id=uuid.uuid4().hex,name=path.stem,
              data_directory=os.path.relpath(folder,path.parent),images=managed,
              image_sha256=hashes,settings=settings,
              rendering=dict(width=settings['width'],height=settings['width']*3//4,triangles=settings['triangles'],color_model='affine-gouraud',
                             two_sided=True,additive=True,depth_test=False),
              state=dict(status='ready',cycle=0,triangle=0,proposals=0,fitness=0.))
    atomic_json(path,data)
    return data


def update_settings(path,settings):
    data=read_project(path);settings=validate_settings(settings)
    if (run_directory(path,data)/'best.npz').exists() and any(settings[k]!=data['settings'][k] for k in ('triangles','width')):
        raise ValueError('Triangle count/resolution changes require a new project to preserve the old mesh and fitness history')
    data['settings']=settings
    data['rendering'].update(width=settings['width'],height=settings['width']*3//4,triangles=settings['triangles'])
    atomic_json(Path(path),data)
    return data


def clone_project(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists(): raise FileExistsError('Choose a new project filename')
    data=read_project(source)
    folder=destination.parent/(destination.stem+'.data')
    if folder.exists(): raise FileExistsError('The destination data folder already exists')
    shutil.copytree(run_directory(source,data),folder,ignore=shutil.ignore_patterns('worker.lock','control.txt','worker.log'))
    old_folder=run_directory(source,data)
    data['images']=[os.path.relpath(folder/resolve(source,p).relative_to(old_folder),destination.parent) for p in data['images']]
    data['data_directory']=os.path.relpath(folder,destination.parent)
    data['id']=uuid.uuid4().hex;data['name']=destination.stem
    atomic_json(destination,data)
    return data


def export_obj(checkpoint,path):
    from .checkpoint import read_checkpoint
    from .gouraud import export_vertex_obj
    d=read_checkpoint(checkpoint);path=Path(path)
    cfg=json.loads(str(d['config']));width=int(cfg.get('width',640))
    export_vertex_obj(path,d['vertices'],d['colors'],images=cfg.get('images'))
    atomic_json(path.with_suffix('.render.json'),dict(format='Lisa2 rendering',version=1,
        vertex_color='OBJ v x y z r g b extension; full precision in .vertex-colors.npy',
        blending='additive',background=[0,0,0],two_sided=True,depth_test=False,
        interpolation='affine screen-space Gouraud',color_range=[0,.4],
        triangles=int(len(d['vertices'])),vertices=int(d['vertices'].size//3),target_resolution=[width,width*3//4]))
