"""Modal Studio window for visually selecting settings."""
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, SimpleQueue
from threading import Event
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from PIL import ImageTk

from .settings_evolution import POPULATION_SIZE, Trials, next_population


class SettingsDialog:
    def __init__(self, root, checkpoint, images, settings, apply):
        self.apply_settings = apply
        self.source = (checkpoint, tuple(images), settings.copy())
        self.trials = None
        self.rng = np.random.default_rng(settings['seed'])
        self.selected = None
        self.round = 0
        self.ready = False
        self.cancelled = Event()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Lisa2-settings')
        self.poll_id = None
        self.photos = []
        self.incoming_photos = []
        self.previews = []
        self.view = 0
        self.completed = SimpleQueue()
        self.window = tk.Toplevel(root)
        self.window.title('Evolve settings')
        self.window.transient(root)
        self.window.geometry(f'+{root.winfo_x()}+{root.winfo_y()}')
        self.window.resizable(False, False)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Escape>', lambda _: self.close())
        self.window.bind('<MouseWheel>', lambda event: self.change_view(1 if event.delta < 0 else -1) if event.delta else None)
        self.window.bind('<Button-4>', lambda _: self.change_view(-1))
        self.window.bind('<Button-5>', lambda _: self.change_view(1))
        self.tile_width = max(84, min(224, (root.winfo_screenwidth()-90)//4,
                                      (root.winfo_screenheight()-235)//3))
        self.tile_height = self.tile_width*3//4
        panel = ttk.Frame(self.window, padding=12)
        panel.pack(fill='both', expand=True)
        self.status = tk.StringVar(master=self.window)
        ttk.Label(panel, textvariable=self.status, wraplength=610).pack(anchor='w', pady=(0,8))
        style = ttk.Style(self.window)
        style.configure('Settings.Horizontal.TProgressbar', background='#318cff',
                        troughcolor='#000000', bordercolor='#000000',
                        lightcolor='#318cff', darkcolor='#318cff')
        self.progress = ttk.Progressbar(panel, maximum=POPULATION_SIZE, mode='determinate',
                                        style='Settings.Horizontal.TProgressbar')
        self.progress.pack(fill='x', pady=(0,8))
        board = ttk.Frame(panel)
        board.pack()
        self.cards = []
        for index in range(POPULATION_SIZE):
            card = tk.Canvas(board, width=self.tile_width, height=self.tile_height+24,
                             background='#10151e', highlightthickness=4,
                             highlightbackground='#405169', highlightcolor='#405169')
            card.grid(row=index//4, column=index%4, padx=3, pady=3)
            card.bind('<Enter>', lambda _, i=index: self.hover(i, True))
            card.bind('<Leave>', lambda _, i=index: self.hover(i, False))
            card.bind('<Button-1>', lambda _, i=index: self.select(i))
            self.cards.append(card)
        footer = ttk.Frame(panel)
        footer.pack(fill='x', pady=(8,0))
        ttk.Button(footer, text='Cancel', command=self.close).pack(side='right')
        self.use = ttk.Button(footer, text='Use selected settings', command=self.commit, state='disabled')
        self.use.pack(side='right', padx=8)
        self.window.grab_set()
        self.start_round(settings, settings)

    def hover(self, index, entered):
        if self.ready:
            self.cards[index].configure(highlightbackground='#f4b65f' if entered else '#405169')

    def start_round(self, parent, partner):
        self.ready = False
        self.round += 1
        self.population = next_population(parent, partner, self.rng)
        self.rng.shuffle(self.population)
        self.progress.configure(value=0)
        self.status.set(f'Round {self.round} · Rendering 0 / {POPULATION_SIZE} options…')
        self.window.configure(cursor='watch')
        for card in self.cards:
            card.configure(cursor='watch')
        self.future = self.pool.submit(self.render_round, self.population)
        self.poll_id = self.window.after(80, self.poll)

    def render_round(self, population):
        if self.trials is None:
            self.trials = Trials(*self.source)
        previews = []
        for settings in population:
            if self.cancelled.is_set():
                return None
            previews.append(self.trials.preview(settings, self.cancelled))
            self.completed.put(len(previews))
        return previews

    def poll(self):
        self.poll_id = None
        try:
            while True:
                count = self.completed.get_nowait()
                self.progress.configure(value=count)
                self.status.set(f'Round {self.round} · Rendering {count} / {POPULATION_SIZE} options…')
        except Empty:
            pass
        if not self.future.done():
            self.poll_id = self.window.after(80, self.poll)
            return
        try:
            self.previews = self.future.result()
        except Exception as error:
            self.window.configure(cursor='')
            for card in self.cards:
                card.configure(cursor='')
            self.status.set(f'Could not render round {self.round}: {error}')
            return
        self.photos = []
        for index, card in enumerate(self.cards):
            card.delete('all')
            card.configure(highlightbackground='#405169')
            card.create_text(8,12,anchor='w',text=f'Option {index+1}',fill='#eef3ff',tags='title')
        self.draw_view(self.view, 0)
        offset = self.tile_height+24
        for card in self.cards:
            card.move('all',0,offset)
        self.animate_cards(0,offset,offset,round_transition=True)

    def draw_view(self, view, offset):
        self.incoming_photos = []
        for card, previews in zip(self.cards, self.previews):
            image = previews[view].resize((self.tile_width,self.tile_height))
            photo = ImageTk.PhotoImage(image, master=self.window)
            self.incoming_photos.append(photo)
            card.create_image(self.tile_width/2+offset,24+self.tile_height/2,image=photo,tags='incoming')

    def change_view(self, direction):
        if not self.ready:
            return
        self.ready = False
        self.view = (self.view+direction)%4
        offset = direction*self.tile_width
        for card in self.cards:
            card.configure(cursor='')
        self.draw_view(self.view,offset)
        self.animate_cards(0,offset,offset)
        return 'break'

    def animate_cards(self, frame, previous_offset, distance, round_transition=False):
        frames = 10
        offset = round(distance * (1-frame/frames)**3)
        for card in self.cards:
            delta = offset-previous_offset
            if round_transition:
                card.move('all',0,delta)
            else:
                card.move('incoming',delta,0)
                card.move('view',delta,0)
        if frame < frames:
            self.poll_id = self.window.after(18,self.animate_cards,frame+1,offset,distance,round_transition)
            return
        self.poll_id = None
        self.window.configure(cursor='')
        for card in self.cards:
            card.delete('view')
            card.addtag_withtag('view','incoming')
            card.dtag('incoming','incoming')
            card.configure(cursor='hand2')
        self.photos = self.incoming_photos
        self.ready = True
        self.progress.configure(value=POPULATION_SIZE)
        self.status.set(f'Round {self.round} · View {self.view+1} / 4 · Scroll to change view · Click to select')

    def select(self, index):
        if not self.ready:
            return
        previous = self.selected
        self.selected = self.population[index].copy()
        self.ready = False
        for i, card in enumerate(self.cards):
            card.configure(highlightbackground='#ff8b25' if i == index else '#405169')
        self.cards[index].itemconfigure('title', text=f'Selected · Round {self.round}', fill='#ff8b25')
        self.use.configure(state='normal')
        if previous is None or previous == self.selected:
            others = [candidate for i,candidate in enumerate(self.population) if i!=index]
            previous = others[int(self.rng.integers(len(others)))]
        self.start_round(self.selected, previous)

    def commit(self):
        if self.selected is None:
            return
        try:
            self.apply_settings(self.selected)
        except Exception as error:
            messagebox.showerror('Cannot apply settings', str(error), parent=self.window)
            return
        self.close()

    def close(self):
        self.cancelled.set()
        if self.poll_id is not None:
            self.window.after_cancel(self.poll_id)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.window.destroy()
