# Independent pyramid and joint-color experiments

These are warm-start experiments from the accepted uniform
checkpoint, not independent cold-start replications or a statistical study.
All four original colored targets, tetrahedral perspective cameras, 640x480
physical evaluator and 768 triangles are unchanged. Every accepted triangle
renders from both sides, with additive blending and no depth test or culling.

## User idea: exact detail decomposition and curriculum

For Gaussian scales 16, 8, 4, 2, 0 pixels, use bands
`B16, B8-B16, B4-B8, B2-B4, T-B2`. Signed details are intentional; the sum is
exactly T (maximum measured reconstruction error 1.1102230246251565e-16).
Targets are cumulative band sums, not sums of blurred copies. A stage advances
after at least two passes when the last gain divided by its all-black reference
loss is below 0.002. This is an operational plateau threshold, not proof of a
global optimum. Explicit stage caps guard runtime and are separately logged.

The initial pilot capped every stage after four passes and is retained as a
pilot. The primary convergence-driven run took 5, 3, 3, 3, 2 passes through the
five levels, without hitting its eight-pass stage cap. Eight additional
full-detail passes made 24 passes total. The ordinary uniform control uses the
same source, seed 23, population 12, six CMA generations per triangle and 24
passes: 1,327,104 population evaluations each. Analytic flat RGB fits are the
same in both. No adaptive mutation or edge fitness was enabled.

## Own ideas and limitations

A simultaneous pooled RGB objective (factors 1, 4, 16; weights .25, .35, .40)
was first tried with ordinary uniform CMA. The ten-pass pilot did not improve
the frozen baseline and was stopped. It is not an equal-budget winner.

The optional joint Adam trial uses the same flat-color geometry and pooled
objective, with soft coverage solely for derivatives. Actual hard 640x480
renders are independently evaluated every 50 steps. A small soft loss is not
evidence of good physical output. The separate GPU environment is not a DOS
runtime requirement. Its planned 1200-step budget is not comparable to the CMA
population budget. Stopped after the saved step-900 checkpoint (128px: 600 steps; 256px: 300).
The planned final 320px phase was not run. Last actual hard loss was
0.1926267206; the best evaluated trained snapshot was step 1, loss
0.0934528888, both worse than the frozen 0.0713367752. The soft/hard
surrogate gap did not establish a useful improvement. This is a stopped
negative pilot, not a completed 1200-step comparison or evidence that Adam
cannot work. Full optimizer states remain resumable.

The archived LisaGA had per-vertex colors. A separate bounded global least
squares solve fits all four views at once on the frozen geometry, with standard
affine Gouraud colors. This increases RGB parameters from 2304 to 6912 but
keeps 768 triangles and no view-specific attributes. It solves a convex color
subproblem, not the geometry search. The sparse linear design was independently
checked against the two-sided software renderer. Additional refits on Adam step-800 and step-900 geometry scored worse
(losses 0.1529242474 and 0.1247344423) and are retained as failed trials.

A speculative coherent mesh using culling was rejected by the user and removed
from active source. Its artifacts are excluded from every accepted comparison.
Winding reversal with corresponding vertex colors is tested to render the same
image. No culling, texture projection, per-camera model or hidden face trick is
used in any candidate below.

## Common physical results

Only interior squared RGB error plus 0.15-weight squared light on black is used.
Correct black earns no reward. Lower loss is better; the normalized fitness is
not a perceptual similarity percentage. The independent recomputation is saved
in `runs/pyramid-comparison/metrics.json`.

| Trial | Actual loss | Change against frozen baseline |
|---|---:|---:|
| Frozen uniform baseline | 0.0713367752 | reference |
| Uniform, 24 further passes | 0.0672379911 | 5.75% lower |
| User curriculum + cleanup | 0.0801641270 | 12.37% higher |
| Own global Gouraud colors, frozen geometry | 0.0642658103 | 9.91% lower |

The Gouraud solve reduces error by only 4.42% versus the extended uniform
control, with more color parameters. These numbers do not establish an artistic
breakthrough. The comparison still contains stray triangles and degraded
outlines. We have not met the user's request for an unambiguously excellent
result. Keep the accepted baseline intact; do not promote a new visual winner
based solely on a small numerical improvement.

## Artifacts and reproduction

- Frozen: `runs/uniform-fine640`, SHA256 of best.npz:
  `e54745271986f35e19db0f1dbe8942b74a8a32db8e31596cc99b7fec5553d7c7`.
- Primary curriculum: `runs/curriculum-converged`; signed bands in
  `pyramid/decomposition.npz`, cumulative target PNGs and stage events preserved.
- Matched control: `runs/pyramid-control`.
- Simultaneous CMA pilot: `runs/pyramid-multiscale`.
- Joint Adam: `runs/joint-multiscale`; optimizer states and hard evaluations.
- Vertex RGB: `runs/joint-gouraud`; OBJ vertex-RGB extension and color sidecar.
- Failed Adam-geometry refit: `runs/gouraud-joint-refit`.
- Contact sheet: `runs/pyramid-comparison/comparison.png`.

Reproduce the primary pair with:
```
python -m lisa2.experiments --method curriculum --output runs/new-curriculum --max-stage-rounds 8
python -m lisa2.experiments --resume --output runs/new-curriculum --extra-rounds 8
python -m lisa2.experiments --method control --output runs/new-control --passes 24
```
The eight cleanup passes are an explicitly reported extension after the
measured curriculum; subsequent machines may reach the plateau after different
roundoff-level histories. Full checkpoints, configs and events are authoritative.

The normal preview uses the software renderer and 1-4 smooth camera changes.
Space continues each run with its own optimizer. Fixed-geometry color fitting
is already solved and is not restarted as a flat-color GA. Frozen checkpoints
have a frozen.flag; viewer continuation forks into a new run. Baseline assets
and run artifacts remain ignored by Git. Historical commits were not amended.
No Pentium-II performance claim has been measured.

## Sources

- [OpenCV image pyramids](https://docs.opencv.org/3.4.19/dc/dff/tutorial_py_pyramids.html)
- [SciPy bounded least squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.lsq_linear.html)
- [PyTorch prior versions and CUDA wheels](https://docs.pytorch.org/get-started/previous-versions/)
- [PyTorch checkpointing](https://docs.pytorch.org/docs/stable/checkpoint)


## Geometric diagnostic, not another fitness term

A separate sampled ray probe asks whether a foreground point could have any
3D support inside the unit ball that also projects inside the other three
silhouettes. It uses every fourth screen sample, 512 ray-depth samples, and
relaxes the other masks by two pixels. Supported sample fractions were 89.7%,
84.7%, 75.5%, 94.4% for portrait, spacecraft, dragon and island. The horn region
is particularly incompatible with black in the other views.

This is a discretized diagnostic, not a rigorous impossibility bound, optimizer
score, or an additional objective. It ignores color compatibility; green points
are only potentially feasible. Red points lacked a sampled zero-spill location.
It suggests part of the outline/spill tradeoff is in the chosen silhouettes and
camera arrangement, rather than something an optimizer alone will remove.
Targets and accepted constraints were not changed in response to this finding.
The probe script, JSON and visualization are saved with the comparison artifacts.
