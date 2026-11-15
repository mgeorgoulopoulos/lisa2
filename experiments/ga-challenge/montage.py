"""Make contact sheets from independently reconstructed renders."""
import csv
from pathlib import Path

from PIL import Image, ImageDraw

from compare import target, root
import numpy as np

for start in ('fresh', 'warm'):
    dirs = [root / f'{start}-{method}' for method in ('cma', 'cma-once', 'direct')]
    curves = [list(csv.DictReader((d / 'curve.csv').open())) for d in dirs]
    canvas = Image.new('RGB', (1280, 1320 if start == 'warm' else 1056), '#181818')
    draw = ImageDraw.Draw(canvas)
    rows = [('Targets', [Image.fromarray(np.uint8(p * 255)) for p in target])]
    if start == 'warm':
        rows.append(('Shared checkpoint', [Image.open(dirs[0] / f'start-{k}.png') for k in range(4)]))
    for label, folder, curve in zip(('CMA-ES + refinement for every candidate', 'CMA-ES + refinement of winner', 'Deterministic search + refinement of winner'), dirs, curves):
        last = curve[-1]
        rows.append((f"{label} | fitness {float(last['fitness']):.5f} | {last['updates']} updates",
                     [Image.open(folder / f'final-{k}.png') for k in range(4)]))
    for i, (label, views) in enumerate(rows):
        draw.text((8, 264*i+5), label, fill='white')
        for k, image in enumerate(views):
            canvas.paste(image.resize((320, 240), Image.Resampling.LANCZOS), (320*k, 264*i+24))
    canvas.save(root / f'{start}.png')
    print(start, [c[-1] for c in curves])
    common = set.intersection(*(set(r['updates'] for r in c) for c in curves))
    last_common = max(common, key=int)
    print('same updates', [next(r for r in c if r['updates'] == last_common) for c in curves])

