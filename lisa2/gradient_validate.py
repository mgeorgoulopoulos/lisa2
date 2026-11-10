"""Judge training snapshots with the unchanged hard software renderer."""
import argparse,json
from pathlib import Path
import numpy as np
from .checkpoint import read_checkpoint
from .targets import load
from .objective import ColorObjective,quality_metrics
from .raster import render


def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();d=read_checkpoint(args.checkpoint);cfg=json.loads(str(d['config']))
    t=load(cfg['images'],640,480);obj=ColorObjective(t,.15)
    im=render(d['vertices'],d['colors'],640,480)
    terms=obj.terms(im)
    report=dict(loss=terms['total'],fitness=1-terms['total']/obj.baseline,
        terms=terms,views=quality_metrics(t,np.clip(im,0,1)),
        finite=bool(np.isfinite(im).all()),step=int(d['step']))
    Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':main()
