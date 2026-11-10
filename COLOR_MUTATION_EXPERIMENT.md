# Interior color + small black penalty / adaptive mutation

Replaces the rejected edge/silhouette fitness for new runs.

## Exactly two loss terms

For each camera, foreground is target max-RGB > 0.025. Near-black target pixels
are treated as zero. With N equal to that view's foreground-pixel count:

    L = sum_views((sum_foreground RGB_squared_error
                  + 0.15 * sum_background rendered_RGB_squared) / N)

No edge, gradient, silhouette-coverage, visibility-floor or linear-background
term is active. A correct black pixel contributes zero, not a reward. The fixed
black-reference baseline gives an all-black render fitness zero. Normalization
by foreground size also prevents added black padding from diluting spill.
Triangle RGB fitting is again the exact bounded nonnegative quadratic solution.
The renderer, geometry budget, targets and four perspective cameras are unchanged.

## Requested adaptive operator

At each CMA-ES generation, project each parent vertex into all four target masks.
If any view is outside its foreground (or outside the viewport), that vertex has
a 90% chance of accepting its sampled mutation offset, scaled by 3. Vertices
inside all four masks use 25% and scale 1. The gate acts on the xyz triplet.
The actual modified offspring are passed to DEAP's strategy update.

This changes exploration, not fitness. It neither snaps vertices into masks nor
adds a hidden silhouette penalty. The base step is resolution-scaled: warm mesh
sigma = 0.025 * 128 / image_width, approximately a pixel near the object's center.
Old runs retain their world-space settings when opened/continued from preview.

## Completed equal-budget comparison

Both final runs started from runs/distinct640/best.npz, seed 23, 768 triangles,
640x480, three rounds, eight generations per block, population twelve, and the
same two-term objective. Each evaluated 221184 population candidates, plus the
same parent evaluations. One uses the requested adaptive gate; the control uses
ordinary CMA-ES offsets. The random trajectories differ, as expected.

| Final loss | Adaptive | Ordinary CMA-ES control |
|---|---:|---:|
| Total | 0.078134561 | 0.071336775 |
| Interior color | 0.066851021 | 0.059830217 |
| Black spill | 0.011283540 | 0.011506559 |

The control's total error is 8.70% lower in this single matched-budget
trial. The requested adaptive rule is implemented and tested, but has not shown
a convergence advantage here. Do not claim it improves artistic quality.

The adaptive result is the requested experiment, in runs/adaptive-fine640/.
The control is retained separately in runs/uniform-fine640/. Both contain actual
renders, camera animation, OBJ/MTL and checkpoint. Earlier coarse-step trials
(adaptive320, adaptive640, color-control320) are preserved. They motivated
resolution-scaled steps and starting warm optimization at the existing triangle
rather than throwing it away for a random seed during the first pass.

## Verification

Tests check exactly two terms, the 0.15 pixel-penalty ratio, all-black zero score,
black-padding invariance, exact incremental/full loss agreement, the any-view
trigger, observed 25%/90% mutation probabilities and the larger offset variance.
Final errors were recomputed independently from the complete 640x480 mesh.
Existing camera/raster checks passed. See tests/check_color_mutation.py.
The large background and internal triangle artifacts remain a visual limitation;
this is an experiment, not a claim of finished demo artwork.
