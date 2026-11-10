# Profiled Gouraud geometry experiment

The user selected the last row of the previous comparison as
visually better: the global Gouraud color fit on the frozen uniform geometry.
This is the new starting checkpoint, kept intact in `runs/joint-gouraud`.
The previous detail curriculum did not beat its matched uniform control and is
not used here. Its implementation and historical results remain archived.

## Method

DEAP CMA-ES changes only the nine position coordinates of one triangle. Remove
that triangle from the current four-view image; for every proposed geometry,
solve its bounded three-vertex RGB least-squares problem against the remaining
image residual. Other triangles' colors are fixed during this local evaluation.
A small active-bound enumeration solves the three-variable problems per channel;
its objective agrees with independent SciPy bounded least squares, including
singular cases. The old geometry/colors always remain feasible fallbacks.

After each full mesh pass, the existing SciPy sparse bounded solver refits all
vertex colors jointly on the new geometry. Keep that result only if the actual
physical loss does not rise. Thus this is alternating coordinate geometry search
with profiled local colors and periodic global colors, not a global color solve
for every population member. It is not guaranteed to find a global optimum.

All 768 triangles, four tetrahedral perspective cameras, 640x480 output,
RGB bounds [0,0.4], interior RGB squared error and 0.15-weight black spill are
unchanged. No progressive detail targets, pooled loss, soft raster surrogate,
edge reward, adaptive mutation, culling or depth test participates. The same
model and vertex colors are used in every view and intermediate camera angle.

## Actual run and independent validation

Five passes, six generations per triangle, population 12, seed 23, geometry
sigma 0.005 in world coordinates. Total 276,480 population evaluations and five
global color solves. Four passes were completed first; the fifth was resumed
from the finished checkpoint to verify continuation. Pause was observed at
step 2402 and resumed successfully. Global solves finish before servicing a
pending pause. Checks use the physical software renderer, not displayed PNGs.

- Starting loss: 0.06426581029508416.
- Final loss: 0.06062731601407705 (**5.6616% lower**).
- Interior color error: 0.05298806053286584 -> 0.04961679153177318.
- Black-spill term: 0.011277749762218316 -> 0.011010524482303871.
- 1764 vertices moved, across 588 of 768 triangles.
- RMS vertex displacement 0.0105861; maximum 0.0762338, unit-ball radius 1.
- Physical checkpoint history is monotonic within numerical tolerance.
- Full final render agrees with recorded loss and reversing triangle winding
  with corresponding vertex colors gives the same four-view render.

This is a modest improvement, not a claim that the remaining outline and
background artifacts have disappeared. No Pentium-II frame rate was measured.
The normalized fitness is not a perceptual similarity percentage.

## Review and continue

`Preview.cmd` or `PreviewHybrid.cmd`: new result, 1-4 smooth camera transition,
Space pause/continue, E vertex-color OBJ export. The completed comparison is
frozen; continuing from the viewer forks a distinct run. `PreviewUniform.cmd`
still opens the older uniform baseline. For direct reproduction:

```
python -m lisa2.hybrid_gouraud --output runs/new-hybrid --passes 4
python -m lisa2.hybrid_gouraud --output runs/new-hybrid --resume --extra-passes 1
```

Artifacts in `runs/hybrid-gouraud`: best.npz, progress.json, validation.json,
before-after.png, full-size view PNGs, comparison.png, orbit.gif, fitness.png,
model.obj and its vertex-RGB NumPy sidecar, and per-pass global-* solves.
OBJ uses the vertex-RGB extension; additive two-sided blending is configured
by the companion renderer and is not representable by ordinary OBJ alone.
The validation script is saved beside the results for independent recomputation.

Source checkpoint SHA256:
`1dca4432c7083fce6657bf23fd213ee97e766be272c70282d9120a08094a4156`.
No prior checkpoint or historical Git commit was overwritten.
