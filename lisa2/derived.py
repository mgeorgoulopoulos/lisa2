"""Derived checkpoint views: in-memory UI previews, never project payloads."""
import numpy as np
import json
from PIL import Image
from .checkpoint import read_checkpoint
from .geometry import BASES
from .gouraud import render_gouraud


def checkpoint_views(path):
    data=read_checkpoint(path)
    config=json.loads(str(data['config']));width=int(config.get('width',640));height=width*3//4
    colors=data['colors']
    if colors.ndim==2: colors=np.repeat(colors[:,None,:],3,axis=1)
    rendered=render_gouraud(data['vertices'],colors,width,height,BASES)
    views=[Image.fromarray(np.uint8(np.clip(view,0,1)*255)) for view in rendered]
    history=data.get('history',np.empty((0,2)))
    return dict(views=views,step=int(data['step']),fitness=float(history[-1,1]) if len(history) else None)
