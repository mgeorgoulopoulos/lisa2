"""Writable state and subprocess commands for source and frozen distributions."""
import os
from pathlib import Path
import sys


def data_directory():
    if os.environ.get('LISA2_DATA_DIR'):
        return Path(os.environ['LISA2_DATA_DIR']).expanduser().resolve()
    if not getattr(sys,'frozen',False):
        return Path(__file__).resolve().parent.parent/'runs'/'runtime'
    if os.name=='nt':
        base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))
    else:
        base=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local'/'share'))
    return base/'Lisa2'


def configure():
    folder=data_directory();folder.mkdir(parents=True,exist_ok=True)
    cache=folder/'numba-cache';cache.mkdir(exist_ok=True)
    os.environ.setdefault('NUMBA_CACHE_DIR',str(cache))
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ.setdefault(key,'1')
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
    return folder


def command(mode,*args):
    if mode not in ('worker','preview'): raise ValueError('Unknown child mode')
    entry=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,'-m','lisa2.launcher']
    return [*entry,'--'+mode,*map(str,args)]


def child_directory(project_folder):
    return Path(project_folder) if getattr(sys,'frozen',False) else Path(__file__).resolve().parent.parent
