"""End-to-end installed-application check; all UI stays withdrawn or SDL dummy."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--report',required=True)
    args=parser.parse_args(argv);report=Path(args.report).resolve()
    from .runtime import configure,command,child_directory
    folder=configure()/'release-check';folder.mkdir(exist_ok=True)
    try:
        run_check(folder)
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(dict(status='passed',checks=[
            'native JIT renderer','bounded worker subprocess','Studio resume subprocess',
            'global RGB fit','checkpoint/history','four derived views','OBJ + cameras',
            'GIF','SDL dummy preview subprocess','withdrawn Tk controller']),indent=2),encoding='utf-8')
    except Exception:
        import traceback
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(dict(status='failed',error=traceback.format_exc()),indent=2),encoding='utf-8')
        raise


def run_check(folder):
    import numpy as np
    from PIL import Image,ImageDraw
    import tkinter as tk
    from .runtime import command,child_directory
    from .project import create_project,run_directory,export_obj
    from .checkpoint import read_checkpoint
    from .derived import checkpoint_views
    from .gif_export import export_gif
    from .app import Studio
    with tempfile.TemporaryDirectory(prefix='Lisa2 Δ test ',dir=folder) as temp:
        work=Path(temp);images=[]
        for i in range(4):
            path=work/f'target {i+1}.png';im=Image.new('RGB',(32,24))
            ImageDraw.Draw(im).ellipse((5,4,27,20),fill=(120,60+30*i,180));im.save(path);images.append(path)
        project=work/'project.json'
        create_project(project,images,dict(triangles=4,width=32,population=4,generations=1,
            refine_steps=1,plateau_relative=.99,plateau_patience=1,plateau_min_passes=1))
        data=run_directory(project)
        with (work/'child.log').open('w',encoding='utf-8') as log:
            subprocess.run(command('worker','--project',project,'--max-triangles',1),
                cwd=child_directory(work),stdout=log,stderr=subprocess.STDOUT,timeout=240,check=True)
        first=read_checkpoint(data/'best.npz');assert int(first['step'])==1
        root=tk.Tk();root.withdraw();app=None;errors=[]
        root.report_callback_exception=lambda *args:errors.append(str(args))
        try:
            app=Studio(root,str(project));root.update_idletasks();app.start()
            assert app.worker is not None
            deadline=time.monotonic()+240
            while app.worker.poll() is None:
                root.update()
                if time.monotonic()>deadline:
                    app.stop();app.worker.wait(timeout=30)
                    raise TimeoutError('Studio worker did not finish')
                time.sleep(.05)
            assert app.worker.returncode==0,(data/'worker.log').read_text()
            app.poll_progress();assert not errors,errors
            progress=json.loads((data/'progress.json').read_text())
            assert progress['status']=='plateau' and progress['cycle']==1
            assert progress['global_solves']==1
            final=read_checkpoint(data/'best.npz')
            assert final['vertices'].shape==(4,3,3)
            assert np.array_equal(final['history'][:len(first['history'])],first['history'])
            assert all(im.size==(32,24) for im in checkpoint_views(data/'best.npz')['views'])
            obj=work/'mesh.obj';export_obj(data/'best.npz',obj)
            assert obj.read_text().count('# camera ')==4
            gif=work/'preview.gif';export_gif(data/'best.npz',gif,fps=2)
            with Image.open(gif) as image: assert image.size==(32,24) and image.n_frames>4
            with (work/'preview.log').open('w',encoding='utf-8') as log:
                subprocess.run(command('preview','--run',data,'--read-only','--smoke-test'),
                    cwd=child_directory(work),stdout=log,stderr=subprocess.STDOUT,timeout=120,check=True)
        finally:
            if app is not None:
                if app.is_running(): app.stop();app.worker.wait(timeout=30)
                app.shutdown_renderers(wait=True);app.drop.close()
            root.destroy()
