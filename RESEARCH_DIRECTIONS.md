# Research that can help Lisa2

The literature search establishes prior art for evolutionary/local hybrids;
it does not establish that Lisa2 has no possible research contribution. The
practical question here is which mechanisms can improve the actual four
images. A 13.51% reduction of the current squared physical loss did not produce
a comparable visual improvement. Another long continuation of the same local
operator is therefore not the first experiment to recommend.

These are research-informed proposals, not implemented improvements or claims
of demonstrated gains. The UI previews and GIF export requested alongside
this review are implemented separately. Fitness, renderer, camera geometry,
targets, triangle count and accepted constraints remain unchanged.

## 1. Reallocate the fixed triangle budget using residual-driven pursuit

Matching pursuit builds an approximation by selecting dictionary elements
against a residual. Its useful connection to Lisa2 is the additive image
representation. See Mallat and Zhang, [Matching Pursuits With Time-Frequency
Dictionaries (1993)](https://www.di.ens.fr/~mallat/papiers/MallatPursuit93.pdf).
That work does not directly solve four-view positive Gouraud mesh synthesis.

Proposed adaptation: measure a triangle's marginal contribution to the existing
four-view physical loss; propose replacing an unhelpful triangle with a new
shared 3D triangle whose fitted RGB addresses residual error. Fit its vertex
colors with the existing bounded solver, evaluate all four hard-render views,
and retain the previous triangle as fallback. Explore genuinely different
supports, not only small movements around the current placement. Periodically
refit all colors as already done.

Keep exactly 768 triangles throughout. Every retained triangle remains two-sided
and additive in every view. This is a training proposal/replacement operator,
not backface culling, an output mask or camera-specific geometry. Rank utility
by the unchanged physical loss, not silhouette membership. It differs from the
previous rejected adaptive silhouette mutation experiment. Replacement is not
guaranteed to be visually better; test it against matched controls and inspect
actual full-resolution images before promoting it.

This is my first candidate for a bounded exploratory trial because the current
local method preserves essentially the same allocation of geometry, even when
many small adjustments reduce RGB error.

## 2. Compute coverage-aware search directions with a hard forward pass

[Rasterized Edge Gradients: Handling Discontinuities Differentiably (2024)](https://arxiv.org/abs/2405.02508)
develops approximate gradients at rasterization discontinuities while preserving
the forward rendered image. This directly addresses a weakness of ordinary
geometry derivatives at moving triangle boundaries. It is not an edge-loss
term. Another relevant engineering direction is [Transforming a
Non-Differentiable Rasterizer into a Differentiable One with Stochastic Gradient
Estimation (2024)](https://arxiv.org/abs/2404.09758), which estimates gradients
through parameter perturbations and per-pixel parameter contributions.

For Lisa2, adapt coverage derivatives for each additive triangle and accumulate
their contributions across all four cameras. A single visible-primitive/depth
buffer from an opaque renderer is not sufficient: all overlapping triangles
contribute in our model. GPU implementations are references, not drop-in
replacements for the required CPU/two-sided/no-depth renderer. Continue to use
the real hard-render loss for acceptance, with the original feasible solution
as fallback. The published results do not guarantee gains in Lisa2.

The earlier soft-raster Adam pilot stopped at 900/1200 steps and failed to beat
the baseline in measured hard renders. That specific negative pilot does not
test these hard-forward boundary-gradient methods. This is a separate proposed
mechanism, not a relabeling or silent revival of that experiment.

## 3. Check geometric compatibility before promising clean silhouettes

Laurentini's visual-hull theory explains what silhouette intersections constrain
and what they cannot reconstruct. See the author's [Visual Hull project and
papers](https://cgvg.polito.it/vhull.html). The inference for our positive
additive model is that geometric support which must light a foreground region
can also spill into other views; negative light and occlusion cannot cancel it.

The previous sampled ray diagnostic suggested incompatibility near the dragon
horns, but was not an impossibility proof. The useful next step is a more
rigorous compatibility/lower-bound diagnostic, with discretization uncertainty
reported explicitly. It remains outside fitness and does not alter targets,
cameras or masks in the renderer. This can distinguish optimization limitations
from limitations of the chosen representation and target combination.

## 4. Evaluate visual improvement separately from physical fitness

[The Unreasonable Effectiveness of Deep Features as a Perceptual Metric
(2018)](https://openaccess.thecvf.com/content_cvpr_2018/html/Zhang_The_Unreasonable_Effectiveness_CVPR_2018_paper.html)
introduces the LPIPS line of perceptual evaluation, studying agreement with
human judgments beyond pixel distances. A perceptual diagnostic plus blinded
human comparisons would help identify loss reductions that do not improve
recognizability. Neither metric is a guarantee of artistic quality.

Use such scores as separate evaluation at fixed target framing, with the actual
black spill and renders still available. Do not silently replace the accepted
two-term objective or add rejected edge/silhouette rewards. A proposal to change
the training objective would be a distinct decision and experiment. No Torch
or perceptual-network dependency was added to Studio for this review.

## Recommended order

First use the new live render tiles to review actual images while training.
Then run one short, explicitly bounded residual-driven replacement trial,
with fixed constraints, matched controls and preserved checkpoints. Coverage
gradients are the next implementation study. Use compatibility analysis and
perceptual/human diagnostics to avoid interpreting lower squared RGB error as
an automatic artistic breakthrough. Do not repeat multi-hour runs solely to
accumulate another numerical percentage.
