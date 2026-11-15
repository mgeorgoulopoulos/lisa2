"""Compare CMA-ES and deterministic multiscale direct search with shared RGB fit."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from deap import cma
from PIL import Image, ImageDraw

from lisa2.checkpoint import read_checkpoint
from lisa2.geometry import BASES, constrain
from lisa2.gouraud import render_gouraud
from lisa2.hybrid_gouraud import add, local_fit
from lisa2.local_refine import refine
from lisa2.objective import ColorObjective, contour_options
from lisa2.project import image_paths, read_project, run_directory
from lisa2.targets import load
from lisa2.train import creator, seed_triangle

source = Path('manualTests/Test3.json').resolve()
p = read_project(source)
s = p['settings']
w, h = s['width'], s['width'] * 3 // 4
target = load(image_paths(source, p), w, h)
obj = ColorObjective(target, .15, **contour_options(s))
root = Path(__file__).resolve().parent


def polish(v, c, g, residual):
    return refine(v, c, g, residual, obj.weights, s['refine_radius'],
                  s['refine_difference'], s['refine_steps'])[:3]


def evaluate(v, residual):
    v = constrain(v)
    c, g = local_fit(v, residual, obj.weights)
    return v, c, g


def cma_search(old, residual, best, step, polish_all=True):
    np.random.seed((s['seed'] + 31 * step) % 2**32)
    strategy = cma.Strategy(old.ravel(), s['sigma'], lambda_=s['population'])
    for _ in range(s['generations']):
        population = strategy.generate(creator.LisaIndividual)
        for ind in population:
            v, c, g = evaluate(ind, residual)
            if polish_all:
                v, c, g = polish(v, c, g, residual)
            ind[:] = v.ravel()
            ind.fitness.values = (-g,)
            if g > best[2] + 1e-14:
                best = v, c, g
        strategy.update(population)
    return best


def direct_search(old, residual, best, step):
    # Rotate the order deterministically so each vertex and axis is visited first
    # equally often. Probe both signs and accept only an exact four-view gain.
    for scale in (4, 2, 1):
        for axis in np.roll(np.arange(9), step % 9):
            center = best[0]
            for sign in (-1, 1):
                sample = center.copy()
                sample.flat[axis] += sign * s['sigma'] * scale
                trial = evaluate(sample, residual)
                if trial[2] > best[2] + 1e-14:
                    best = trial
    return polish(*best, residual)


def run(method, start, seconds):
    folder = root / f'{start}-{method}'
    folder.mkdir(exist_ok=False)
    checkpoint = run_directory(source, p) / 'best.npz'
    checksum = hashlib.sha256(checkpoint.read_bytes()).digest()
    if start == 'warm':
        data = read_checkpoint(checkpoint)
        vertices, colors = data['vertices'].copy(), data['colors'].copy()
        state = json.loads(str(data['config']))['project_state']
        offset, cycle, within = state['step'], state['cycle'], state['within_pass']
    else:
        rng = np.random.default_rng(s['seed'])
        vertices = np.asarray([seed_triangle(target, rng) for _ in range(s['triangles'])])
        colors = np.zeros_like(vertices)
        offset, cycle, within = 0, 0, 0
    image = render_gouraud(vertices, colors, w, h, BASES)
    # Warm the shared kernels before timing.
    residual = np.ascontiguousarray(target - image)
    sample = evaluate(vertices[0], residual)
    polish(*sample, residual)
    began = time.perf_counter()
    update = 0
    search = cma_search if method != 'direct' else direct_search
    if method == 'cma-once':
        search = lambda old, residual, best, step: polish(*cma_search(old, residual, best, step, False), residual)
    milestones = [0, 32, 64, 128, 256, 384, 512, 701, 768, 1024, 1536, 2048]

    def snapshot(label):
        reconstructed = render_gouraud(vertices, colors, w, h, BASES)
        for k, pixels in enumerate(reconstructed):
            Image.fromarray(np.uint8(np.clip(pixels, 0, 1) * 255)).save(folder / f'{label}-{k}.png')
        np.savez_compressed(folder / f'{label}.npz', vertices=vertices, colors=colors)
        return obj.terms(reconstructed)['total']

    snapshot('start')
    with (folder / 'curve.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['updates', 'seconds', 'loss', 'fitness'])
        writer.writerow([0, 0, obj.terms(image)['total'], 1 - obj.terms(image)['total'] / obj.baseline])
        while time.perf_counter() - began < seconds:
            order = np.random.default_rng(s['seed'] + cycle).permutation(len(vertices))
            for i in order[within:]:
                old = vertices[i].copy()
                add(image, old, colors[i], -1.)
                residual = np.ascontiguousarray(target - image)
                best = search(old, residual, evaluate(old, residual), offset + update)
                vertices[i], colors[i] = best[:2]
                add(image, *best[:2])
                update += 1
                elapsed = time.perf_counter() - began
                if update % 16 == 0 or update in milestones:
                    loss = obj.terms(image)['total']
                    writer.writerow([update, elapsed, loss, 1 - loss / obj.baseline])
                    stream.flush()
                if update in milestones:
                    snapshot(str(update))
                if elapsed >= seconds:
                    break
            within = 0
            cycle += 1
        loss = snapshot('final')
        writer.writerow([update, time.perf_counter() - began, loss, 1 - loss / obj.baseline])
    assert hashlib.sha256(checkpoint.read_bytes()).digest() == checksum
    print(start, method, update, loss, 1 - loss / obj.baseline, flush=True)


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2], float(sys.argv[3]))

