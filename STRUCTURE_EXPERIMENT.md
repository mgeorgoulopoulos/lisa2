# Silhouette-first experiment

The user's criterion is an artistically readable subject with a clean outline,
not faithful pixel reproduction. Correct black must not earn fitness points.

## Implemented objective

Positive losses for soft silhouette mismatch (including contour-band emphasis),
RGB gradient mismatch, interior color error, squared background error and linear
background light leakage. The displayed fitness is 1 - loss / fixed black-render
loss. Correct black adds zero; an entirely black result scores exactly zero.
Foreground/background/contour regions are normalized separately in every view.

Selected coefficients: color 4, silhouette 3, RGB edge 1.5, background 6 and
background linear factor 0.08. The silhouette foreground threshold is 0.025;
rendered visibility saturates at max-RGB 0.12. These thresholds are diagnostic
and fitness choices, not an output mask. Preview and OBJ still use only the
real 768-triangle two-sided additive mesh, the same cameras and 640x480.

## Results at identical resolution and thresholds

| Diagnostic (mean of four views) | Previous RGB | Selected structure |
|---|---:|---:|
| Silhouette intersection-over-union | 0.500 | 0.826 |
| Contour F1 (two-pixel tolerance) | 0.029 | 0.346 |
| Fraction of background visibly lit | 15.606% | 3.175% |
| Mean background light | 0.007861 | 0.001591 |
| Foreground RGB MSE | 0.005896 | 0.034045 |

For the dragon, silhouette IoU rises from 0.489 to
0.865. Background spill falls from
16.929% to 2.499%.
These are silhouette diagnostics, not artistic-quality percentages.

The outline/background improvement is real. **The artistic goal has not yet
been met:** interior color error increased, and the subject is still visibly
fragmented. Do not label this final demoscene artwork. The actual comparison
and animation are the relevant review evidence, not the normalized fitness.

## Attempts retained locally

- structure128: initial structural objective, six rounds; stronger contours.
- structure320: four rounds, exposing low-resolution silhouette overfitting.
- structure640: stopped after a Windows checkpoint collision; its last good
  snapshot was retained and used for continuation in a new run.
- outline640: color weight raised to 4; three rounds, six generations per
  block, population 12. Continued after improving the color-candidate proposal.
  This is the selected high-resolution result.
- planes128: triangles proposed on planes through pairs of camera centers.
  Did not improve the artwork; that experimental source was removed.
- edges128 / edges640: edge error normalized by target gradient energy.
  Two final high-resolution rounds did not beat outline640's contour/color
  tradeoff. Energy normalization remains optional; area is the selected default.

All use seed 23 and the same four original colorful target assets. No geometry
budget increase, renderer masking, texturing or view-specific materials.

## Numerical and concurrency checks

Incremental candidate gains match a complete combined-loss recomputation,
including nonlinear max-channel visibility and saturation. Tests cover halos,
displaced outlines, introducing visibility with no quadratic RGB proposal,
all-black score zero, both edge normalizations, existing camera/raster
invariants and concurrent checkpoint reading/writing. The final selected loss
was independently recomputed from its entire mesh. Resume was exercised on
an actual interrupted training run.

Windows readers now load snapshots into memory and immediately close disk
handles. Atomic writers and readers retry transient sharing races. Existing
RGB runs remain supported, including preview continuation with old metadata.

Artifacts: runs/outline640/best.npz, model.obj, model.mtl, comparison.png,
dragon-before-after.png, orbit.gif and ab-comparison.json. Preview.lnk opens
this selected run. The earlier RGB run remains untouched.
