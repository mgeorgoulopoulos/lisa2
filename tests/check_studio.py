"""Hidden-window controller test: no desktop input, activation or dialogs."""
import json
import hashlib
from pathlib import Path
import tempfile
import time
import tkinter as tk
from unittest.mock import patch
import numpy as np
from lisa2.app import Studio
from lisa2.project import DEFAULTS,read_project,run_directory
from lisa2.checkpoint import read_checkpoint

base=Path('runs/studio-tests');base.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=base.resolve()) as temp:
    folder=Path(temp);project=folder/'test.json'
    images=list(Path('runs/studio-ui-test.data/images').resolve().glob('*.png'))
    if len(images)!=4:
        from PIL import Image,ImageDraw
        images=[]
        for i in range(4):
            p=folder/f'{i}.png';im=Image.new('RGB',(64,48));ImageDraw.Draw(im).ellipse((10,8,50,40),fill=(150,90+i*20,180));im.save(p);images.append(p)
    root=tk.Tk();root.withdraw()
    with patch('lisa2.app.messagebox.showerror',side_effect=lambda *a,**k:(_ for _ in ()).throw(AssertionError(str(a)))):
        app=Studio(root)
        assert app.get_settings()==DEFAULTS
        root.update_idletasks();slot=app.slots[0]
        app.on_drop([str(p) for p in images],slot.winfo_rootx(),slot.winfo_rooty())
        assert all(app.images),'Slot drop mapping failed'
        assert app.drop.enabled
        app.settings['population'].set('4');app.settings['generations'].set('1');app.settings['refine_steps'].set('1')
        with patch('lisa2.app.filedialog.asksaveasfilename',return_value=str(project)): assert app.save()
        assert read_project(project)['settings']['population']==4
        app.basic.set(True);app.set_mode('basic');assert not app.get_settings()['color_fit']
        app.settings['refinement'].set(True);app.set_mode('refine');assert app.get_settings()['color_fit']
        app.start();deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            root.update();app.poll_progress()
            if app.progress.get('step',0)>=2: break
            time.sleep(.1)
        assert app.progress.get('step',0)>=2,'Worker did not publish checkpoints'
        app.stop()
        while app.is_running() and time.monotonic()<deadline: root.update();time.sleep(.1)
        assert not app.is_running(),'Stop did not finish'
        root.update();app.poll_progress()
        app.poll();assert 'Stopped & saved' in app.status_var.get()
        while app.view_stamp!=(run_directory(project)/'best.npz').stat().st_mtime_ns and time.monotonic()<deadline:
            app.poll_derived();root.update();time.sleep(.05)
        assert len(app.best_views)==4 and all(view.size==(640,480) for view in app.best_views)
        assert not list(run_directory(project).glob('*.png'))
        assert 'best_views' not in read_project(project)
        saved=read_checkpoint(run_directory(project)/'best.npz')
        assert len(app.progress['proposal_history'])>=3
        before=saved['history'].copy();proposals=app.progress['proposals']
        app.open_path(project);assert app.progress['proposals']==proposals
        assert np.array_equal(read_checkpoint(run_directory(project)/'best.npz')['history'],before)
        with patch('lisa2.app.subprocess.Popen') as preview:
            app.preview();assert '--read-only' in preview.call_args.args[0]
        model=folder/'model.obj'
        with patch('lisa2.app.filedialog.asksaveasfilename',return_value=str(model)): app.export()
        assert model.exists() and model.with_suffix('.render.json').exists()
        def fake_gif(checkpoint,path,progress):
            progress(1,1);return dict(path=path,duration_ms=20000)
        with patch('lisa2.app.filedialog.asksaveasfilename',return_value=str(folder/'dive.gif')),patch('lisa2.app.export_gif',side_effect=fake_gif):
            app.export_animation()
            while app.gif_future is not None and time.monotonic()<deadline: app.poll_derived();time.sleep(.01)
            assert 'GIF saved' in app.export_status.get()
        clone=folder/'clone.json'
        with patch('lisa2.app.filedialog.asksaveasfilename',return_value=str(clone)): app.save_as()
        assert app.path==clone and np.array_equal(read_checkpoint(run_directory(clone)/'best.npz')['history'],before)
        old_checkpoint=run_directory(clone)/'best.npz';digest=hashlib.sha256(old_checkpoint.read_bytes()).hexdigest()
        new_project=folder/'new-dimensions.json'
        app.settings['triangles'].set('12');app.settings['width'].set('64')
        with patch('lisa2.app.filedialog.asksaveasfilename',return_value=str(new_project)): assert app.save()
        assert app.path==new_project and read_project(new_project)['rendering']['height']==48
        assert read_project(new_project)['settings']['triangles']==12 and app.best_views is None
        assert not (run_directory(new_project)/'best.npz').exists()
        assert hashlib.sha256(old_checkpoint.read_bytes()).hexdigest()==digest
        app.settings['balance_regions'].set(True)
        app.settings['region_share'].set('27')
        copied_settings=app.get_settings()
        app.new(keep_settings=True)
        assert app.path is None and app.images==[None]*4 and not app.progress
        assert app.get_settings()==copied_settings
        for i,image in enumerate(images): app.assign_image(i,image)
        next_project=folder/'new-targets.json'
        with patch('lisa2.app.filedialog.asksaveasfilename',return_value=str(next_project)): assert app.save()
        assert read_project(next_project)['settings']==copied_settings
        assert not (run_directory(next_project)/'best.npz').exists()
        assert hashlib.sha256(old_checkpoint.read_bytes()).hexdigest()==digest
        app.shutdown_renderers(wait=True);app.drop.close();root.destroy()
print('PASS: hidden Studio selection, settings, start/stop, load/history, preview routing, OBJ export and Save As; no desktop interaction.')
