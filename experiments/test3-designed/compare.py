"""Compare fresh Test3 starts at the same CMA-ES proposal budget."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

import numpy as np
from PIL import Image, ImageDraw

from lisa2.checkpoint import read_checkpoint
from lisa2.geometry import ASPECT, BASES, RADIUS, TAN_HALF, constrain, project
from lisa2.gouraud import render_gouraud
from lisa2.objective import ColorObjective, contour_options
from lisa2.project import image_paths, read_project, run_directory
from lisa2.project_worker import run
from lisa2.targets import load
from lisa2.train import atomic_json, save

source = Path('manualTests/Test3.json').resolve()
root = Path(__file__).resolve().parent
original = read_project(source)
settings = original['settings']
width = settings['width']
height = width * 3 // 4
images = image_paths(source, original)
target = load(images, width, height)
contours = contour_options(settings)
objective = ColorObjective(target, .15, **contours)


def designed_mesh():
    rng = np.random.default_rng(settings['seed'])
    vertices, colors = [], []
    for view, count in enumerate(np.bincount(np.arange(settings['triangles']) % 4)):
        image = target[view]
        signal = image.max(axis=2)
        weights = signal ** 2
        samples = rng.choice(weights.size, size=count, replace=False,
                             p=(weights / weights.sum()).ravel())
        radius = np.sqrt(np.count_nonzero(signal > .1) / (count * 3 * np.sqrt(3) / 4))
        for sample in samples:
            y, x = divmod(sample, width)
            angle = rng.uniform(0, 2 * np.pi) + np.arange(3) * (2 * np.pi / 3)
            pixels = [x + .5, y + .5] + radius * np.column_stack((np.cos(angle), np.sin(angle)))
            depth = rng.uniform(-.65, .65)
            rays = np.column_stack(((2 * pixels[:, 0] / width - 1) * ASPECT * TAN_HALF,
                                    (1 - 2 * pixels[:, 1] / height) * TAN_HALF))
            local = np.column_stack((rays * (RADIUS - depth), np.full(3, depth)))
            triangle = constrain(local @ BASES[view])
            xy = np.floor(project(triangle, BASES[view], width, height)).astype(int)
            rgb = image[xy[:, 1].clip(0, height - 1), xy[:, 0].clip(0, width - 1)]
            vertices.append(triangle)
            colors.append(rgb.clip(0, .4))
    return np.asarray(vertices), np.asarray(colors)


def montage(rows):
    size = (320, 240)
    sheet = Image.new('RGB', (4 * size[0], len(rows) * (size[1] + 24)), '#222222')
    draw = ImageDraw.Draw(sheet)
    for row, (label, views) in enumerate(rows):
        y = row * (size[1] + 24)
        draw.text((8, y + 5), label, fill='white')
        for view, pixels in enumerate(views):
            im = Image.fromarray(np.uint8(np.clip(pixels, 0, 1) * 255))
            sheet.paste(im.resize(size, Image.Resampling.LANCZOS), (view * size[0], y + 24))
    sheet.save(root / 'comparison.png')


def experiment(budget):
    original_paths = [source, *Path(images[0]).parent.parent.glob('*.*'), *map(Path, images)]
    protected = [p for p in original_paths if p.is_file() and p.name != 'worker.lock']
    before = {p: hashlib.sha256(p.read_bytes()).digest() for p in protected}
    rows = [('Targets', target)]
    results = {}
    for name in ('designed', 'baseline'):
        path = root / f'{name}.json'
        project = copy.deepcopy(original)
        project.update(id=uuid.uuid4().hex, name=f'Test3 {name}', images=images,
                       data_directory=f'{name}.data', state={'status': 'ready'})
        folder = run_directory(path, project)
        folder.mkdir(exist_ok=False)
        atomic_json(path, project)
        checkpoint = folder / 'best.npz'
        if name == 'designed':
            started = time.perf_counter()
            vertices, colors = designed_mesh()
            current = render_gouraud(vertices, colors, width, height, BASES)
            loss = objective.terms(current)['total']
            state = dict(cycle=0, within_pass=0, step=0, proposals=0, accepted=0,
                         plateau_streak=0, cycle_start_loss=loss, elapsed=0., global_solves=0,
                         refined_candidates=0, refine_steps_accepted=0)
            save(checkpoint, vertices, colors, 0, [[0, 1 - loss / objective.baseline]],
                 dict(project_state=state, project_id=project['id'], project_settings=settings,
                      width=width, contours=contours))
            init_seconds = time.perf_counter() - started
        else:
            current = np.zeros_like(target)
            init_seconds = None
        rows.append((f'{name} at start', current))
        def observe(progress, event):
            if event in ('start', 'resume', 'budget') or (event == 'triangle' and progress['step'] % 32 == 0):
                print(name, event, progress['step'], progress['fitness'], flush=True)
        initial = objective.terms(current)
        run(path, max_triangles=budget, observer=observe)
        data = read_checkpoint(checkpoint)
        current = render_gouraud(data['vertices'], data['colors'], width, height, BASES)
        final = json.loads((folder / 'progress.json').read_text())
        rows.append((f'{name} after {budget} triangle updates', current))
        results[name] = dict(initial=initial, init_seconds=init_seconds,
                             final={key: final[key] for key in ('step', 'proposals', 'fitness',
                                                                'loss_terms', 'seconds', 'baseline')})
        atomic_json(root / 'results.json', results)
        montage(rows)
    assert all(hashlib.sha256(p.read_bytes()).digest() == digest for p, digest in before.items())
    print('Verified original project and files by SHA-256.', flush=True)


if __name__ == '__main__':
    experiment(int(sys.argv[1]))
