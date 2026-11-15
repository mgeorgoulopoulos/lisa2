"""Paired continuation from the existing Test3 checkpoint."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

import numpy as np

from lisa2.checkpoint import read_checkpoint
from lisa2.geometry import ASPECT, BASES, RADIUS, TAN_HALF, constrain, project as project_pixels
from lisa2.project import image_paths, read_project, run_directory
from lisa2.project_worker import run
from lisa2.train import atomic_json

source = Path('manualTests/Test3.json').resolve()
root = Path(__file__).resolve().parent
project = read_project(source)
source_data = run_directory(source, project)
images = image_paths(source, project)
checkpoint = source_data / 'best.npz'
state = json.loads(str(read_checkpoint(checkpoint)['config']))['project_state']
protected = [source, checkpoint, *map(Path, images)]
before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}


def designs(step, generation, old, residual, weights, settings):
    if generation != 0:
        return
    rng = np.random.default_rng([settings['seed'], step, 845])
    _, h, w, _ = residual.shape
    for index in range(settings['population']):
        view = (index + step) % 4
        camera = BASES[view]
        old_xy = project_pixels(old, camera, w, h)
        if index < settings['population'] // 2:
            signal = np.maximum(residual[view], 0).sum(axis=2) ** 2 * weights[view]
            total = signal.sum()
            if total > 0:
                pixel = rng.choice(signal.size, p=signal.ravel() / total)
                y, x = divmod(pixel, w)
            else:
                x, y = old_xy.mean(axis=0)
            depth = rng.uniform(-.6, .6)
        else:
            x, y = old_xy.mean(axis=0) + rng.normal(0, 4, 2)
            depth = (old.mean(axis=0) @ camera[2]) + rng.normal(0, .06)
        radius = np.clip(np.linalg.norm(old_xy - old_xy.mean(axis=0), axis=1).mean(), 3, 28)
        angle = rng.uniform(0, 2 * np.pi) + np.arange(3) * 2 * np.pi / 3
        pixels = [x + .5, y + .5] + radius * np.column_stack((np.cos(angle), np.sin(angle)))
        local = np.column_stack(((2 * pixels[:, 0] / w - 1) * ASPECT * TAN_HALF * (RADIUS - depth),
                                 (1 - 2 * pixels[:, 1] / h) * TAN_HALF * (RADIUS - depth),
                                 np.full(3, depth)))
        yield constrain(local @ camera).ravel()


if __name__ == '__main__':
    name = sys.argv[1]
    budget = int(sys.argv[2])
    path = root / f'{name}.json'
    data = dict(project, id=uuid.uuid4().hex, name=f'Test3 {name}', images=images,
                data_directory=f'{name}.data')
    folder = run_directory(path, data)
    folder.mkdir(exist_ok=False)
    shutil.copyfile(checkpoint, folder / 'best.npz')
    atomic_json(path, data)

    def observe(progress, event):
        delta = progress['step'] - state['step']
        if event != 'triangle' or delta % 64 == 0:
            print(name, event, delta, progress['fitness'], progress['loss'], flush=True)

    run(path, budget, observe, designs if name == 'injected' else None)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in before.items())
    print('Original checkpoint and inputs verified.', flush=True)

