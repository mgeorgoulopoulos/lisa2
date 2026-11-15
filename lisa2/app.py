"""Lisa2 project studio: target slots, evolution controls and persistent history."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
from bisect import bisect_left
import csv
import json
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageOps,ImageTk
from .project import DEFAULTS,create_project,read_project,run_directory,image_paths,update_settings,clone_project,export_obj
from .windows_drop import FileDrop
from .derived import checkpoint_views
from .gif_export import export_gif
from .runtime import command,configure,child_directory

BG='#10151e';PANEL='#192230';EDGE='#2c3a50';TEXT='#e6edf5';MUTED='#9aacc2';ACCENT='#f4b65f';GREEN='#80d2b0';BLUE='#59b9ff'


class Studio:
    def __init__(self,root,project=None):
        self.root=root;self.path=None;self.images=[None]*4;self.photos=[None]*4
        self.worker=None;self.worker_method=None;self.preview_processes=[];self.progress={};self.stamp=None
        self.closing=False;self.stopping=False;self.failures=0
        self.view_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='Lisa2-views')
        self.gif_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='Lisa2-gif')
        self.view_future=None;self.view_request=None;self.view_epoch=0;self.view_stamp=None
        self.view_started=0.;self.best_views=None;self.best_photos=[None]*4
        self.gif_future=None;self.gif_progress=None;self.renderers_closed=False
        root.title('Lisa2 Studio');root.geometry('1180x850');root.minsize(1040,780);root.configure(bg=BG)
        self.style=ttk.Style();self.style.theme_use('clam')
        self.style.configure('.',background=PANEL,foreground=TEXT,font=('Segoe UI',10))
        self.style.configure('TFrame',background=BG);self.style.configure('Panel.TFrame',background=PANEL)
        self.style.configure('TLabel',background=BG,foreground=TEXT)
        self.style.configure('Muted.TLabel',foreground=MUTED)
        self.style.configure('TButton',background=EDGE,foreground=TEXT,padding=(14,8),borderwidth=0)
        self.style.map('TButton',background=[('active','#3c516d'),('disabled','#202936')],foreground=[('disabled','#677991')])
        self.style.configure('Start.TButton',background=ACCENT,foreground=BG,font=('Segoe UI',11,'bold'))
        self.style.map('Start.TButton',background=[('active','#ffd494'),('disabled','#514635')])
        self.style.configure('Deterministic.TButton',background=BLUE,foreground=BG,font=('Segoe UI',11,'bold'))
        self.style.map('Deterministic.TButton',background=[('active','#9bd7ff'),('disabled','#294760')])
        self.style.configure('Interleaved.TButton',background='#c5a2ff',foreground=BG,font=('Segoe UI',11,'bold'))
        self.style.map('Interleaved.TButton',background=[('active','#ddc8ff'),('disabled','#514066')])
        self.style.configure('TCheckbutton',background=PANEL,foreground=TEXT,padding=3)
        self.style.map('TCheckbutton',background=[('active',PANEL)],foreground=[('disabled','#677991')])
        self.style.configure('TEntry',fieldbackground=BG,foreground=TEXT,insertcolor=TEXT)
        self.style.configure('TSpinbox',fieldbackground=BG,foreground=TEXT,arrowcolor=TEXT)
        self.settings={key:tk.BooleanVar(value=value) if isinstance(value,bool) else tk.StringVar(value=str(value)) for key,value in DEFAULTS.items()}
        self.basic=tk.BooleanVar(value=False)
        self.build_menu();self.build()
        self.drop=FileDrop(root,self.on_drop)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.bind('<Control-o>',lambda e:self.load());root.bind('<Control-s>',lambda e:self.save())
        root.bind('<Control-n>',lambda e:self.new())
        if project: self.open_path(project)
        root.after(400,self.poll)

    def build_menu(self):
        menu=tk.Menu(self.root);file=tk.Menu(menu,tearoff=False)
        file.add_command(label='New project',accelerator='Ctrl+N',command=self.new)
        file.add_command(label='New project with current settings…',command=lambda:self.new(keep_settings=True))
        file.add_command(label='Load project…',accelerator='Ctrl+O',command=self.load)
        file.add_command(label='Save project',accelerator='Ctrl+S',command=self.save)
        file.add_command(label='Save project as…',command=self.save_as)
        file.add_separator();export=tk.Menu(file,tearoff=False)
        export.add_command(label='OBJ with vertex colors…',command=self.export)
        export.add_command(label='GIF · orbit & camera dive…',command=self.export_animation)
        self.export_menu=export
        file.add_cascade(label='Export',menu=export);file.add_command(label='Export statistics CSV…',command=self.export_stats)
        file.add_separator();file.add_command(label='Exit',command=self.close)
        menu.add_cascade(label='File',menu=file)
        help=tk.Menu(menu,tearoff=False);help.add_command(label='About Lisa2',command=lambda:messagebox.showinfo('Lisa2 Studio',
            'One shared mesh · four tetrahedral perspective views\nConfigurable triangle count and 4:3 target resolution\nDefaults: 768 triangles · 640 × 480\n\nFitness is reduction of the physical RGB loss against an all-black render. It is not a perceptual similarity percentage.\n\nOBJ uses vertex RGB. Use the sidecar and rendering metadata with importers that need them.'))
        menu.add_cascade(label='Help',menu=help);self.root.config(menu=menu)

    def build(self):
        # The extra derived-view row stays usable on smaller screens through
        # normal vertical scrolling instead of clipping lower settings.
        outer=ttk.Frame(self.root);outer.pack(fill='both',expand=True)
        viewport=tk.Canvas(outer,bg=BG,highlightthickness=0)
        scrollbar=ttk.Scrollbar(outer,orient='vertical',command=viewport.yview)
        scrollbar.pack(side='right',fill='y');viewport.pack(side='left',fill='both',expand=True)
        viewport.configure(yscrollcommand=scrollbar.set);self.viewport=viewport
        shell=ttk.Frame(viewport,padding=24)
        window=viewport.create_window(0,0,window=shell,anchor='nw')
        shell.bind('<Configure>',lambda e:viewport.configure(scrollregion=viewport.bbox('all')))
        viewport.bind('<Configure>',lambda e:viewport.itemconfigure(window,width=e.width))
        def wheel(event):
            if event.widget.winfo_toplevel()==self.root and event.widget.winfo_class() not in ('Entry','TEntry','TSpinbox'):
                viewport.yview_scroll(-int(event.delta/120),'units')
        self.root.bind('<MouseWheel>',wheel,add='+')
        header=ttk.Frame(shell);header.pack(fill='x')
        ttk.Label(header,text='LISA2',font=('Segoe UI',25,'bold'),foreground=ACCENT).pack(side='left')
        ttk.Label(header,text='  /  FOUR VIEWS. ONE MESH.',style='Muted.TLabel',font=('Segoe UI',10)).pack(side='left',pady=(10,0))
        self.project_label=ttk.Label(header,text='Unsaved project',style='Muted.TLabel');self.project_label.pack(side='right')
        ttk.Label(shell,text='TARGET IMAGES',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(20,8))
        slots=ttk.Frame(shell);slots.pack(fill='x');self.slots=[];self.slot_names=[]
        for i in range(4):
            slots.columnconfigure(i,weight=1,uniform='slots')
            frame=ttk.Frame(slots);frame.grid(row=0,column=i,sticky='nsew',padx=(0 if i==0 else 8,0))
            canvas=tk.Canvas(frame,width=260,height=120,bg='#070b11',highlightbackground=EDGE,highlightthickness=1,cursor='hand2')
            canvas.pack(fill='x');canvas.bind('<Button-1>',lambda e,index=i:self.choose_image(index));self.slots.append(canvas)
            name=ttk.Label(frame,text=f'{i+1}  Drop image or click to choose',style='Muted.TLabel',wraplength=250)
            name.pack(anchor='w',pady=(6,0));self.slot_names.append(name)
            canvas.bind('<Configure>',lambda e,index=i:self.draw_slot(index))
        self.best_note=tk.StringVar(value='BEST SO FAR  ·  Start evolution to generate the four views')
        ttk.Label(shell,textvariable=self.best_note,font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(14,8))
        best=ttk.Frame(shell);best.pack(fill='x');self.best_canvases=[]
        for i in range(4):
            best.columnconfigure(i,weight=1,uniform='best')
            canvas=tk.Canvas(best,width=260,height=120,bg='#070b11',highlightbackground=EDGE,highlightthickness=1)
            canvas.grid(row=0,column=i,sticky='ew',padx=(0 if i==0 else 8,0));self.best_canvases.append(canvas)
            canvas.bind('<Configure>',lambda e,index=i:self.draw_best(index))
        controls=ttk.Frame(shell);controls.pack(fill='x',pady=(18,14))
        run_control=ttk.Frame(controls);run_control.pack(side='left')
        self.start_button=ttk.Button(run_control,text='▶  Start evolution',style='Start.TButton',command=self.toggle_run)
        self.start_button.pack(side='left')
        self.run_menu_button=ttk.Menubutton(run_control,text='▾',style='Start.TButton')
        self.run_menu_button.pack(side='left')
        run_menu=tk.Menu(self.run_menu_button,tearoff=False)
        for method,label in (('evolution','Evolution'),('deterministic','Deterministic'),('interleaved','Interleaved')):
            run_menu.add_command(label=label,command=lambda selected=method:self.start(selected))
        self.run_menu_button.configure(menu=run_menu)
        self.evolve_button=ttk.Button(controls,text='Evolve settings…',command=self.evolve_settings,state='disabled')
        self.evolve_button.pack(side='left',padx=8)
        self.preview_button=ttk.Button(controls,text='◈  3D preview',command=self.preview,state='disabled');self.preview_button.pack(side='left')
        self.status_var=tk.StringVar(value='Add four images to begin.')
        ttk.Label(controls,textvariable=self.status_var,foreground=GREEN,wraplength=530).pack(side='right')
        body=ttk.Frame(shell);body.pack(fill='both',expand=True);body.columnconfigure(0,weight=3);body.columnconfigure(1,weight=2);body.rowconfigure(0,weight=1)
        left=ttk.Frame(body);left.grid(row=0,column=0,sticky='nsew',padx=(0,18))
        graph_header=ttk.Frame(left);graph_header.pack(fill='x',pady=(0,8))
        ttk.Label(graph_header,text='FITNESS HISTORY',font=('Segoe UI',10,'bold')).pack(side='left')
        self.graph_axis_button=ttk.Button(graph_header,text='Show generations',command=self.toggle_graph_axis)
        self.graph_axis_button.pack(side='right')
        self.graph_generations=False
        self.graph_journal=None
        self.graph_records=[]
        self.graph=tk.Canvas(left,bg='#0b111a',highlightthickness=1,highlightbackground=EDGE,height=240)
        self.graph.pack(fill='both',expand=True);self.graph.bind('<Configure>',lambda e:self.draw_graph())
        self.graph_zoom=0
        self.graph.bind('<Control-MouseWheel>',self.zoom_graph)
        self.graph_caption=ttk.Label(left,text='Elapsed run time',style='Muted.TLabel')
        self.graph_caption.pack(anchor='w',pady=(5,10))
        self.stats_var=tk.StringVar(value='Cycle 0  ·  Triangle 0 / 768\nGeometry proposals  0\nFitness  0.000000\nPhysical loss  —\nAccepted updates  0')
        ttk.Label(left,textvariable=self.stats_var,font=('Consolas',11),justify='left').pack(anchor='w')
        right=ttk.Frame(body,style='Panel.TFrame',padding=16);right.grid(row=0,column=1,sticky='nsew')
        tk.Label(right,text='EVOLUTION METHOD',bg=PANEL,fg=ACCENT,font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(0,8))
        self.option_widgets=[]
        for text,var,command in [
            ('Evolution only · positions & colors',self.basic,lambda:self.set_mode('basic')),
            ('Exact vertex-color fitting',self.settings['color_fit'],lambda:self.set_mode('color')),
            ('Local position & color refinement',self.settings['refinement'],lambda:self.set_mode('refine')),
            ('Stop automatically at plateau',self.settings['auto_stop'],self.mark_dirty)]:
            w=ttk.Checkbutton(right,text=text,variable=var,command=command);w.pack(anchor='w');self.option_widgets.append(w)
        self.method_note=tk.Label(right,text='Color fitting, then inherited joint refinement.\nOne bounded mesh is shared by all four views.',bg=PANEL,fg=MUTED,justify='left',wraplength=380,font=('Segoe UI',9));self.method_note.pack(anchor='w',pady=(8,14))
        grid=ttk.Frame(right,style='Panel.TFrame');grid.pack(fill='x');grid.columnconfigure(1,weight=1)
        self.fields=[('Triangles','triangles'),('Target width (px; 4:3)','width'),('Population','population'),('Generations / triangle','generations'),('Random seed','seed'),
                ('Geometry sigma','sigma'),('Refine radius / step (px)','refine_radius'),('Difference scale (px)','refine_difference'),
                ('Refine steps / proposal','refine_steps'),('Plateau gain threshold (%)','plateau_relative'),
                ('Plateau patience (cycles)','plateau_patience'),('Earliest plateau cycle','plateau_min_passes')]
        self.settings['plateau_relative'].set(str(DEFAULTS['plateau_relative']*100))
        fields=[pair for pair in self.fields if pair[1] in ('triangles','width','population','generations','seed','plateau_relative','plateau_patience')]
        for row,(label,key) in enumerate(fields):
            tk.Label(grid,text=label,bg=PANEL,fg=TEXT,font=('Segoe UI',9)).grid(row=row,column=0,sticky='w',pady=3)
            w=ttk.Entry(grid,textvariable=self.settings[key],width=12);w.grid(row=row,column=1,sticky='e',padx=(12,0),pady=3)
            self.option_widgets.append(w)
        self.resolution_note=tk.StringVar(value='640 × 480 target · height follows width at 4:3')
        tk.Label(right,textvariable=self.resolution_note,bg=PANEL,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(6,0))
        self.settings['width'].trace_add('write',lambda *args:self.update_resolution_note())
        advanced=ttk.Button(right,text='Advanced settings…',command=self.advanced);advanced.pack(anchor='w',pady=(10,0));self.option_widgets.append(advanced)
        contours=ttk.LabelFrame(right,text='CONTOURS',padding=8)
        contours.pack(fill='x',pady=(12,0))
        checkbox=ttk.Checkbutton(contours,text='Preserve contours',
                                 variable=self.settings['preserve_contours'],command=self.mark_dirty)
        checkbox.grid(row=0,column=0,columnspan=2,sticky='w')
        self.option_widgets.append(checkbox)
        contours.columnconfigure(0,weight=1)
        self.contour_fields=[]
        for row,(label,key) in enumerate((('Max radius','contour_max_radius'),
                                         ('Internal radius','contour_internal_radius')),1):
            caption=ttk.Label(contours,text=label)
            caption.grid(row=row,column=0,sticky='w',pady=3)
            entry=ttk.Entry(contours,textvariable=self.settings[key],width=12)
            entry.grid(row=row,column=1,sticky='e',pady=3)
            self.contour_fields.extend((caption,entry))
        ttk.Label(contours,text='Pixels at 640 × 480',style='Muted.TLabel').grid(row=3,column=0,columnspan=2,sticky='w')
        thin=ttk.Checkbutton(contours,text='Preserve thin features',
                             variable=self.settings['preserve_thin_features'],command=self.mark_dirty)
        thin.grid(row=4,column=0,columnspan=2,sticky='w',pady=(6,0))
        self.option_widgets.append(thin)
        balance=ttk.Checkbutton(contours,text='Balance separate regions',
                                variable=self.settings['balance_regions'],command=self.mark_dirty)
        balance.grid(row=5,column=0,columnspan=2,sticky='w',pady=(6,0))
        self.option_widgets.append(balance)
        self.region_fields=[]
        for row,(label,key) in enumerate((('Region count','region_count'),
                                         ('Region share (%)','region_share')),6):
            caption=ttk.Label(contours,text=label)
            caption.grid(row=row,column=0,sticky='w',pady=3)
            entry=ttk.Entry(contours,textvariable=self.settings[key],width=12)
            entry.grid(row=row,column=1,sticky='e',pady=3)
            self.region_fields.extend((caption,entry))
        self.settings['preserve_contours'].trace_add('write',lambda *_:self.update_contour_fields(self.is_running()))
        self.settings['balance_regions'].trace_add('write',lambda *_:self.update_contour_fields(self.is_running()))
        self.update_contour_fields(False)
        tk.Label(right,text='Plateau compares exact loss after each full cycle\nand its global RGB fit. Stop always keeps progress.',bg=PANEL,fg=MUTED,justify='left',font=('Segoe UI',9)).pack(anchor='w',pady=(12,0))
        self.export_status=tk.StringVar(value='')
        ttk.Label(shell,textvariable=self.export_status,foreground=GREEN,wraplength=1000).pack(anchor='w',pady=(12,0))
        self.footer=tk.StringVar(value='Software rendering · 640 × 480 · 768 triangles · Additive / two-sided')
        ttk.Label(shell,textvariable=self.footer,style='Muted.TLabel').pack(anchor='w',pady=(8,0))

    def is_running(self):
        if self.worker is not None and self.worker.poll() is None: return True
        if self.path:
            try:
                from .project_worker import process_alive
                pid=json.loads((run_directory(self.path)/'worker.lock').read_text())['pid']
                return process_alive(pid)
            except (OSError,ValueError,KeyError): pass
        return False

    def get_settings(self):
        s={}
        for key,default in DEFAULTS.items():
            value=self.settings[key].get()
            s[key]=bool(value) if isinstance(default,bool) else int(value) if isinstance(default,int) else float(value)
        s['plateau_relative']/=100
        from .project import validate_settings
        return validate_settings(s)

    def put_settings(self,settings):
        for key,value in settings.items():
            if key in self.settings: self.settings[key].set(value*100 if key=='plateau_relative' else value)
        self.basic.set(not settings['color_fit'])
        self.set_mode('sync')

    def mark_dirty(self):
        self.status_var.set('Settings apply on the next Start / Resume.')

    def update_contour_fields(self,running):
        for key,fields in (('preserve_contours',self.contour_fields),
                           ('balance_regions',self.region_fields)):
            enabled=self.settings[key].get() and not running
            for widget in fields:
                widget.state(['!disabled'] if enabled else ['disabled'])

    def update_resolution_note(self):
        try:
            width=int(self.settings['width'].get())
            self.resolution_note.set(f'{width} × {width*3//4} target · height follows width at 4:3')
        except ValueError: self.resolution_note.set('Width must be a multiple of four')

    def set_mode(self,source):
        if source=='basic':
            if self.basic.get(): self.settings['color_fit'].set(False);self.settings['refinement'].set(False)
            else: self.settings['color_fit'].set(True)
        elif source=='refine' and self.settings['refinement'].get(): self.settings['color_fit'].set(True)
        elif source=='color' and not self.settings['color_fit'].get(): self.settings['refinement'].set(False)
        self.basic.set(not self.settings['color_fit'].get())
        note=('CMA-ES evolves positions and vertex colors.\nNo analytic color fits or local refinement.' if self.basic.get()
              else 'Exact bounded RGB fits on each proposed geometry.\nGlobal vertex-color fitting after every cycle.' if not self.settings['refinement'].get()
              else 'Color fitting, then inherited joint refinement.\nOne bounded mesh is shared by all four views.')
        self.method_note.config(text=note)

    def draw_slot(self,index):
        canvas=self.slots[index];canvas.delete('all');width=max(canvas.winfo_width(),260);height=120
        if self.images[index]:
            try:
                with Image.open(self.images[index]) as im: image=ImageOps.contain(ImageOps.exif_transpose(im).convert('RGB'),(width-12,height-12),Image.Resampling.LANCZOS)
                self.photos[index]=ImageTk.PhotoImage(image);canvas.create_image(width//2,height//2,image=self.photos[index])
                self.slot_names[index].config(text=f'{index+1}  {Path(self.images[index]).name}')
            except OSError: canvas.create_text(width//2,height//2,text='Image unavailable',fill='#ff9999')
        else:
            canvas.create_text(width//2,height//2-12,text=f'0{index+1}',fill=ACCENT,font=('Segoe UI',26,'bold'))
            canvas.create_text(width//2,height//2+23,text='DROP IMAGE HERE',fill=MUTED,font=('Segoe UI',9))

    def reset_best(self):
        self.view_epoch+=1;self.view_stamp=None;self.best_views=None;self.best_photos=[None]*4
        self.best_note.set('BEST SO FAR  ·  Waiting for a checkpoint' if self.path else 'BEST SO FAR  ·  Start evolution to generate the four views')
        for i in range(4): self.draw_best(i)

    def draw_best(self,index):
        canvas=self.best_canvases[index];canvas.delete('all')
        width=max(canvas.winfo_width(),260);height=120
        if self.best_views is None:
            canvas.create_text(width//2,height//2,text=f'VIEW {index+1}',fill=MUTED,font=('Segoe UI',10));return
        image=ImageOps.contain(self.best_views[index],(width-12,height-12),Image.Resampling.LANCZOS)
        self.best_photos[index]=ImageTk.PhotoImage(image)
        canvas.create_image(width//2,height//2,image=self.best_photos[index])

    def poll_derived(self):
        if self.view_future is not None and self.view_future.done():
            future=self.view_future;request=self.view_request;self.view_future=None
            try:
                result=future.result()
                if request[0]==self.view_epoch:
                    self.best_views=result['views'];self.view_stamp=request[1]
                    fitness='' if result['fitness'] is None else f"  ·  fitness {result['fitness']:.7f}"
                    self.best_note.set(f"BEST SO FAR  ·  checkpoint {result['step']:,}"+fitness)
                    for i in range(4): self.draw_best(i)
            except Exception:
                if request[0]==self.view_epoch: self.best_note.set('BEST SO FAR  ·  Checkpoint preview unavailable; retrying')
        if self.path and self.view_future is None and not self.closing and time.monotonic()-self.view_started>=1.5:
            checkpoint=run_directory(self.path)/'best.npz'
            try:
                stamp=checkpoint.stat().st_mtime_ns
                if stamp!=self.view_stamp:
                    self.view_started=time.monotonic();self.view_request=(self.view_epoch,stamp)
                    self.view_future=self.view_pool.submit(checkpoint_views,checkpoint)
            except OSError: pass
        if self.gif_future is not None:
            if self.gif_progress:
                done,total=self.gif_progress;self.export_status.set(f'Exporting GIF · {done} / {total} frames ({done/total:.0%})')
            if self.gif_future.done():
                future=self.gif_future;self.gif_future=None;self.gif_progress=None
                self.export_menu.entryconfigure(1,state='normal')
                try:
                    result=future.result();self.export_status.set(f"GIF saved · {result['path']} · {result['duration_ms']/1000:g} s")
                except Exception as error: self.export_status.set(f'GIF export failed: {error}')

    def shutdown_renderers(self,wait=False):
        if not self.renderers_closed:
            self.view_pool.shutdown(wait=wait,cancel_futures=True)
            self.gif_pool.shutdown(wait=wait,cancel_futures=True);self.renderers_closed=True

    def choose_image(self,index):
        if self.path:
            messagebox.showinfo('Targets are fixed','Use File → New project to try a different set of targets.');return
        path=filedialog.askopenfilename(title=f'Choose target {index+1}',filetypes=[('Images','*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff'),('All files','*.*')])
        if path: self.assign_image(index,path)

    def advanced(self):
        dialog=tk.Toplevel(self.root);dialog.title('Advanced evolution settings');dialog.configure(bg=PANEL);dialog.resizable(False,False)
        dialog.transient(self.root);dialog.grab_set();saved={k:v.get() for k,v in self.settings.items()}
        frame=ttk.Frame(dialog,style='Panel.TFrame',padding=22);frame.pack(fill='both',expand=True)
        for row,(label,key) in enumerate(self.fields):
            tk.Label(frame,text=label,bg=PANEL,fg=TEXT).grid(row=row,column=0,sticky='w',pady=7)
            ttk.Entry(frame,textvariable=self.settings[key],width=16).grid(row=row,column=1,padx=(20,0),pady=7)
        def cancel():
            for k,v in saved.items(): self.settings[k].set(v)
            dialog.destroy()
        def apply():
            try: self.get_settings();self.refresh_stats();dialog.destroy()
            except Exception as error: messagebox.showerror('Invalid setting',str(error),parent=dialog)
        buttons=ttk.Frame(frame,style='Panel.TFrame');buttons.grid(row=len(self.fields),column=0,columnspan=2,sticky='e',pady=(14,0))
        ttk.Button(buttons,text='Cancel',command=cancel).pack(side='left',padx=8)
        ttk.Button(buttons,text='Apply',command=apply).pack(side='left')
        dialog.protocol('WM_DELETE_WINDOW',cancel)

    def assign_image(self,index,path):
        try:
            with Image.open(path) as im: im.verify()
            self.images[index]=str(Path(path).resolve());self.draw_slot(index)
            self.status_var.set('Ready to start.' if all(self.images) else f'{sum(p is not None for p in self.images)} / 4 images selected')
        except Exception as e: messagebox.showerror('Cannot open image',str(e))

    def on_drop(self,paths,x,y):
        if self.path:
            messagebox.showinfo('Targets are fixed','Create a new project to replace target images.');return
        index=next((i for i,c in enumerate(self.slots) if c.winfo_rootx()<=x<c.winfo_rootx()+c.winfo_width() and c.winfo_rooty()<=y<c.winfo_rooty()+c.winfo_height()),None)
        if index is None: return
        for offset,path in enumerate(paths[:4-index]): self.assign_image(index+offset,path)

    def new(self,keep_settings=False):
        if self.is_running(): messagebox.showinfo('Evolution is running','Stop and save the current evolution first.');return
        try:
            settings=self.get_settings() if keep_settings else DEFAULTS
        except (ValueError,tk.TclError) as error:
            messagebox.showerror('Invalid setting',str(error));return
        if self.path and not self.save(fork_dimensions=False): return
        if not self.path and any(self.images) and not messagebox.askyesno('New project','Discard the unsaved target selection?'): return
        self.path=None;self.images=[None]*4;self.progress={};self.stamp=None;self.put_settings(settings)
        self.reset_best()
        self.project_label.config(text='Unsaved project');self.root.title('Lisa2 Studio')
        for i in range(4): self.draw_slot(i)
        self.status_var.set('Settings copied. Add four new images.' if keep_settings else 'Add four images to begin.')
        self.draw_graph();self.refresh_stats();self.update_buttons(False)

    def load(self):
        if self.is_running(): messagebox.showinfo('Evolution is running','Stop and save before loading another project.');return
        if self.path and not self.save(fork_dimensions=False): return
        path=filedialog.askopenfilename(title='Load Lisa2 project',filetypes=[('Lisa2 project','*.json')])
        if path: self.open_path(path)

    def open_path(self,path):
        try:
            data=read_project(path);images=image_paths(path,data)
            for image in images:
                with Image.open(image) as im: im.verify()
            self.path=Path(path).resolve();self.images=images;self.put_settings(data['settings']);self.progress={};self.stamp=None
            self.reset_best()
            self.project_label.config(text=data['name']);self.root.title(f"Lisa2 Studio — {data['name']}")
            for i in range(4): self.draw_slot(i)
            self.status_var.set('Project loaded. Start resumes the saved cycle.');self.draw_graph();self.refresh_stats();self.poll_progress()
            self.poll_derived()
        except Exception as error: messagebox.showerror('Cannot load project',str(error))

    def save(self,fork_dimensions=True):
        try:
            if self.is_running(): self.status_var.set('Evolution autosaves after every triangle.');return True
            settings=self.get_settings()
            if not self.path:
                if not all(self.images): raise ValueError('Select all four target images first')
                path=filedialog.asksaveasfilename(title='Save Lisa2 project',defaultextension='.json',filetypes=[('Lisa2 project','*.json')])
                if not path: return False
                create_project(path,self.images,settings);self.open_path(path)
            else:
                previous=read_project(self.path)['settings']
                changed=any(previous[k]!=settings[k] for k in ('triangles','width'))
                if changed and (run_directory(self.path)/'best.npz').exists():
                    if not fork_dimensions: return True
                    name=f"{self.path.stem}-{settings['triangles']}t-{settings['width']}x{settings['width']*3//4}.json"
                    path=filedialog.asksaveasfilename(title='Save a new project for changed triangle count / resolution',initialfile=name,defaultextension='.json',filetypes=[('Lisa2 project','*.json')])
                    if not path: return False
                    create_project(path,self.images,settings);self.open_path(path)
                    self.status_var.set('Created a new project; original mesh and history preserved.');return True
                update_settings(self.path,settings);self.refresh_stats()
            self.status_var.set('Project saved.');return True
        except Exception as error: messagebox.showerror('Cannot save project',str(error));return False

    def save_as(self):
        if self.is_running(): messagebox.showinfo('Evolution is running','Stop and save before copying the project.');return
        if not self.path: self.save();return
        destination=filedialog.asksaveasfilename(title='Save a project copy',defaultextension='.json',filetypes=[('Lisa2 project','*.json')])
        if not destination: return
        try:
            settings=self.get_settings();previous=read_project(self.path)['settings']
            if any(previous[k]!=settings[k] for k in ('triangles','width')):
                create_project(destination,self.images,settings)
            else:
                clone_project(self.path,destination);update_settings(destination,settings)
            self.open_path(destination)
        except Exception as error: messagebox.showerror('Cannot copy project',str(error))

    def evolve_settings(self):
        if not self.path or self.is_running(): return
        project=self.path
        checkpoint=run_directory(project)/'best.npz'
        if not checkpoint.exists(): return
        try:
            settings=self.get_settings()
            saved=read_project(project)['settings']
            if any(settings[key]!=saved[key] for key in ('triangles','width')):
                raise ValueError('Use the saved triangle count and resolution for settings trials.')
        except (ValueError,OSError,tk.TclError) as error:
            messagebox.showerror('Cannot evolve settings',str(error));return

        def apply(selected):
            if self.path!=project or self.is_running():
                raise ValueError('Stop evolution in the original project before applying settings.')
            update_settings(project,selected)
            self.put_settings(selected)
            self.status_var.set('Selected settings saved. Resume to evolve with them.')

        from .settings_dialog import SettingsDialog
        dialog=SettingsDialog(self.root,checkpoint,self.images,settings,apply)
        self.root.wait_window(dialog.window)

    def toggle_run(self):
        if self.is_running():
            if not self.stopping: self.stop()
        else:
            self.start()

    def start(self,method='evolution'):
        if self.is_running(): return
        if not self.save(): return
        folder=run_directory(self.path);(folder/'control.txt').write_text('run');(folder/'error.json').unlink(missing_ok=True)
        try:
            env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            with (folder/'worker.log').open('a',encoding='utf-8') as log:
                self.worker=subprocess.Popen(command('worker','--project',self.path,'--method',method),
                    cwd=str(child_directory(folder)),stdout=log,stderr=subprocess.STDOUT,env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            self.worker_method=method
            self.stopping=False
            self.status_var.set('Starting '+{'evolution':'evolution','deterministic':'deterministic update',
                                             'interleaved':'interleaved updates'}[method]+'…')
            self.update_buttons(True)
        except Exception as error: messagebox.showerror('Cannot start update',str(error))

    def stop(self):
        if self.path and self.is_running():
            (run_directory(self.path)/'control.txt').write_text('stop');self.stopping=True
            self.status_var.set('Stopping at a safe checkpoint…');self.update_buttons(True)

    def preview(self):
        if not self.path: return
        folder=run_directory(self.path)
        if not (folder/'best.npz').exists(): return
        try:
            with (folder/'preview.log').open('a',encoding='utf-8') as log:
                self.preview_processes.append(subprocess.Popen(command('preview','--run',folder,'--read-only'),
                    cwd=str(child_directory(folder)),stdout=log,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
        except Exception as error: messagebox.showerror('Cannot open preview',str(error))

    def export(self):
        if not self.path or not (run_directory(self.path)/'best.npz').exists():
            messagebox.showinfo('No mesh yet','Start evolution to create the first mesh.');return
        path=filedialog.asksaveasfilename(title='Export OBJ with vertex RGB',defaultextension='.obj',initialfile='model.obj',filetypes=[('Wavefront OBJ','*.obj')])
        if path:
            try:
                export_obj(run_directory(self.path)/'best.npz',path)
                self.status_var.set('Exported OBJ, vertex RGB sidecar and rendering metadata.')
            except Exception as error: messagebox.showerror('Export failed',str(error))

    def export_stats(self):
        import shutil
        if not self.path or not (run_directory(self.path)/'statistics.csv').exists(): messagebox.showinfo('No statistics yet','Start evolution first.');return
        path=filedialog.asksaveasfilename(title='Export complete experiment statistics',defaultextension='.csv',initialfile='statistics.csv',filetypes=[('CSV','*.csv')])
        if path:
            try:
                source=run_directory(self.path)/'statistics.csv'
                if source.resolve()!=Path(path).resolve(): shutil.copy2(source,path)
                self.status_var.set('Exported complete statistics CSV.')
            except Exception as error: messagebox.showerror('Export failed',str(error))

    def export_animation(self):
        if self.gif_future is not None: return
        if not self.path or not (run_directory(self.path)/'best.npz').exists():
            messagebox.showinfo('No mesh yet','Start evolution to create the first mesh.');return
        path=filedialog.asksaveasfilename(title='Export GIF with orbit and camera dive',defaultextension='.gif',initialfile='camera-dive.gif',filetypes=[('Animated GIF','*.gif')])
        if not path: return
        def progress(done,total): self.gif_progress=(done,total)
        self.gif_progress=None;self.export_status.set('Preparing GIF snapshot and shared palette…')
        self.export_menu.entryconfigure(1,state='disabled')
        self.gif_future=self.gif_pool.submit(export_gif,run_directory(self.path)/'best.npz',path,progress)

    def update_buttons(self,running):
        method=(self.worker_method or self.progress.get('method','evolution')) if running else 'evolution'
        label,style={'evolution':('evolution','Start.TButton'),
                     'deterministic':('deterministic update','Deterministic.TButton'),
                     'interleaved':('interleaved updates','Interleaved.TButton')}[method]
        ready_to_start=not running and all(self.images)
        self.start_button.config(state='normal' if ready_to_start or (running and not self.stopping) else 'disabled',
                                 style=style,text=f'■  Stop {label}' if running else f'▶  Start {label}')
        self.run_menu_button.config(state='normal' if ready_to_start else 'disabled',style=style)
        for widget in self.option_widgets: widget.config(state='disabled' if running else 'normal')
        self.update_contour_fields(running)
        ready=self.path and (run_directory(self.path)/'best.npz').exists()
        self.evolve_button.config(state='normal' if ready and not running else 'disabled')
        self.preview_button.config(state='normal' if ready else 'disabled')

    def poll_progress(self):
        if not self.path: return
        folder=run_directory(self.path);file=folder/'progress.json'
        try:
            stamp=file.stat().st_mtime_ns
            if stamp==self.stamp: return
            progress=json.loads(file.read_text());self.progress=progress;self.stamp=stamp
            running=self.is_running()
            if not self.stopping:
                status=progress['status']
                if running: self.worker_method=self.worker_method or progress.get('method','evolution')
                active=progress.get('active_method',progress.get('method'))
                running_text='Deterministic update in progress…' if active=='deterministic' else 'Evolution in progress…'
                if progress.get('method')=='interleaved': running_text='Interleaved · '+running_text
                self.status_var.set({'running':running_text,'global_rgb':'Fitting all vertex colors…','stopped':'Stopped & saved. Ready to resume.',
                    'plateau':'Plateau detected · automatically stopped & saved.','error':'Evolution stopped with an error.'}.get(status,status))
                if not running and status in ('running','global_rgb'): self.status_var.set('Saved checkpoint recovered. Ready to resume.')
            self.draw_graph();self.refresh_stats()
        except (OSError,ValueError): pass

    def refresh_stats(self):
        p=self.progress;terms=p.get('loss_terms',{})
        try: triangles=int(self.settings['triangles'].get());width=int(self.settings['width'].get())
        except ValueError: triangles=768;width=640
        triangles=p.get('triangles',triangles);width=p.get('width',width)
        self.footer.set(f'Software rendering · {width} × {width*3//4} · {triangles:,} triangles · Additive / two-sided')
        loss=f"{p['loss']:.8f}" if 'loss' in p else '—'
        rel=p.get('relative_cycle_gain');gain='—' if rel is None else f'{rel*100:.4f}%'
        self.stats_var.set(f"Completed cycles  {p.get('cycle',0):,}    Triangle  {p.get('triangle',0)} / {triangles}\n"
            f"CMA proposals     {p.get('proposals',0):,}\nFitness           {p.get('fitness',0):.7f}\nPhysical loss     {loss}\n"
            f"Interior / spill  {terms.get('interior_color',0):.6f} / {terms.get('black_spill',0):.6f}\n"
            f"Accepted updates  {p.get('accepted',0):,}    Global RGB fits  {p.get('global_solves',0)}\n"
            f"Refined proposals {p.get('refined_candidates',0):,}    Local steps  {p.get('refine_steps_accepted',0):,}\n"
            f"Last cycle gain   {gain}    Plateau  {p.get('plateau_streak',0)} / {p.get('plateau_patience',3)}")

    def zoom_graph(self,event):
        if event.delta:
            steps=max(1,abs(event.delta)//120)
            zoom=max(0,min(7,self.graph_zoom+(steps if event.delta>0 else -steps)))
            if zoom!=self.graph_zoom:
                self.graph_zoom=zoom
                self.draw_graph()
        return 'break'

    def toggle_graph_axis(self):
        self.graph_generations=not self.graph_generations
        self.graph_axis_button.config(text='Show time' if self.graph_generations else 'Show generations')
        self.graph_caption.config(text='Generations · one per deterministic update'
                                  if self.graph_generations else 'Elapsed run time')
        self.draw_graph()

    def read_graph_journal(self):
        path=run_directory(self.path)/'statistics.csv' if self.path else None
        if path is None:
            self.graph_journal=None
            self.graph_records=[]
            return
        try:
            stat=path.stat()
            key=(path,stat.st_ino,stat.st_mtime_ns,stat.st_size)
            if key==self.graph_journal:
                return
            records=[]
            previous_step=0
            generations=0
            with path.open(newline='',encoding='utf-8') as stream:
                for row in csv.DictReader(stream):
                    step=int(row['step'])
                    deterministic=row.get('mode','').startswith('deterministic')
                    generations+=max(0,step-previous_step)*(1 if deterministic else int(row.get('generations') or 1))
                    records.append((step,float(row['seconds']),generations,float(row['fitness']),
                                    BLUE if deterministic else ACCENT))
                    previous_step=step
            self.graph_records=records
            self.graph_journal=key
        except (OSError,ValueError,KeyError,TypeError):
            if self.graph_journal is None or self.graph_journal[0]!=path:
                self.graph_records=[]

    def draw_graph(self):
        c=self.graph;c.delete('all');width=max(c.winfo_width(),400);height=max(c.winfo_height(),220)
        left=65;right=width-18;top=22;bottom=height-34
        self.read_graph_journal()
        axis=2 if self.graph_generations else 1
        step=self.progress.get('step',0)
        seconds=self.progress.get('seconds',0)
        records=self.graph_records
        end=bisect_left(records,(step,seconds,float('inf')))
        latest=None
        if 'fitness' in self.progress:
            color=BLUE if self.progress.get('active_method',self.progress.get('method'))=='deterministic' else ACCENT
            last_step,_,generations,_,_=records[end-1] if end else (0,0,0,0,None)
            if step>last_step:
                generations+=(step-last_step)*(1 if color==BLUE else self.get_graph_generations())
            latest=(generations if self.graph_generations else seconds,self.progress['fitness'],color)
        xmax=max(1,records[end-1][axis] if end else 0,latest[0] if latest else 0)
        xmin=xmax*(1-max(.01,2**-self.graph_zoom))
        begin=bisect_left(records,xmin,hi=end,key=lambda record:record[axis])
        points=[(r[axis],r[3],r[4]) for r in records[begin:end]]
        if latest and latest[0]>=xmin and (not points or points[-1][:2]!=latest[:2]):
            points.append(latest)
        ymin=min((p[1] for p in points),default=0.)
        ymax=max((p[1] for p in points),default=.01)
        span=max(ymax-ymin,.001)
        ymax=min(1.,ymax+span*.06);ymin=min(ymin-span*.03,ymax-span*.03)
        for i in range(5):
            y=top+(bottom-top)*i/4;value=ymax-(ymax-ymin)*i/4
            c.create_line(left,y,right,y,fill='#243044');c.create_text(left-9,y,text=f'{value:.3f}',anchor='e',fill=MUTED,font=('Consolas',9))
        for frac in (0,.5,1):
            value=xmin+(xmax-xmin)*frac
            minutes,seconds=divmod(round(value),60)
            label=f'{value:,.0f}' if self.graph_generations else f'{minutes}:{seconds:02d}'
            x=left+(right-left)*frac;c.create_text(x,bottom+16,text=label,fill=MUTED,font=('Consolas',9))
        if points:
            xy=[(left+(right-left)*(x-xmin)/(xmax-xmin),
                 bottom-(bottom-top)*(min(y,1.)-ymin)/(ymax-ymin),color) for x,y,color in points]
            if len(xy)>1:
                line=list(xy[0][:2])
                active=xy[1][2]
                for index,(x,y,color) in enumerate(xy[1:],1):
                    if color!=active:
                        c.create_line(*line,fill=active,width=2)
                        line=list(xy[index-1][:2])
                        active=color
                    line.extend((x,y))
                c.create_line(*line,fill=active,width=2)
            else:
                x,y,color=xy[0];c.create_oval(x-2,y-2,x+2,y+2,fill=color,outline='')
        else: c.create_text((left+right)/2,(top+bottom)/2,text='Your complete evolution history will appear here.',fill=MUTED)

    def get_graph_generations(self):
        try: return int(self.settings['generations'].get())
        except ValueError: return DEFAULTS['generations']

    def poll(self):
        try:
            self.poll_progress();self.poll_derived();running=self.is_running();self.update_buttons(running)
            if not running and self.stopping:
                self.stopping=False;self.stamp=None;self.poll_progress()
            if self.worker is not None and self.worker.poll() is not None:
                code=self.worker.returncode;self.worker=None;self.worker_method=None;self.stopping=False
                self.stamp=None;self.poll_progress()
                if code:
                    folder=run_directory(self.path)
                    try: error=json.loads((folder/'error.json').read_text())['message']
                    except (OSError,ValueError): error=f'Worker exited with code {code}. See worker.log in the project data folder.'
                    messagebox.showerror('Evolution failed',error)
            if self.closing and not running and self.gif_future is None:
                self.shutdown_renderers();self.drop.close();self.root.destroy();return
        finally:
            try:
                if self.root.winfo_exists(): self.root.after(500,self.poll)
            except tk.TclError: pass

    def close(self):
        if self.is_running() or self.gif_future is not None:
            self.closing=True;self.stop();self.status_var.set('Finishing GIF export before closing…' if self.gif_future is not None else 'Saving checkpoint before closing…');return
        if not self.path and any(self.images):
            response=messagebox.askyesnocancel('Save project','Save your target selection before closing?')
            if response is None: return
            if response and not self.save(): return
        elif self.path:
            if not self.save(): return
        self.shutdown_renderers();self.drop.close();self.root.destroy()


def main():
    import argparse
    import faulthandler
    import traceback
    parser=argparse.ArgumentParser();parser.add_argument('--project');args=parser.parse_args()
    log_path=configure()/'studio.log'
    log_path.parent.mkdir(parents=True,exist_ok=True)
    with log_path.open('a',encoding='utf-8',buffering=1) as log:
        faulthandler.enable(file=log)
        root=tk.Tk()
        root.report_callback_exception=lambda kind,error,tb:traceback.print_exception(kind,error,tb,file=log)
        studio=Studio(root,args.project)
        try: root.mainloop()
        except Exception:
            traceback.print_exc(file=log)
            raise
        finally: faulthandler.disable()


if __name__=='__main__':main()
