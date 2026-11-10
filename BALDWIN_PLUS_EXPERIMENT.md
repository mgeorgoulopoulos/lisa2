# Inherited local position/RGB refinement

## Fixed starting point and accepted constraints

The user calls this inherited plasticity **Baldwinian+**. In conventional
evolutionary-computation terminology it is Lamarckian local search: repaired
geometry is passed to CMA-ES, rather than attaching its score to the unrepaired
sample. The current best hybrid checkpoint remains untouched in
`runs/hybrid-gouraud/best.npz`. A byte-identical frozen experiment copy is
`runs/baldwin-plus/baseline.npz`, SHA256
`07264dfe60a84691030ed072383754f89843d3e71bf20a647b1a863921896064`.

Its independently recomputed loss is 0.06062731601407705: interior RGB error
0.04961679153177318 and black spill 0.011010524482303871. All experiments retain
768 triangles, independent RGB at each vertex, affine Gouraud interpolation,
the same four perspective views and full-detail 640x480 targets. Vertices stay
inside the unit ball and colors inside [0,0.4]. Rendering remains additive,
two-sided and without depth tests. The objective is unchanged: interior RGB
squared error plus 0.15-weight squared spill, normalized by foreground area.

## Two separate optimization passes per candidate

1. DEAP CMA-ES proposes one triangle's nine geometry coordinates.
2. The existing exact bounded local RGB solver optimizes all nine color
   parameters on that fixed geometry, against the other triangles' residual.
3. A separate finite-difference joint position/RGB linearization proposes a
   bounded local correction. SciPy `lsq_linear(method='bvls')` solves this small
   18-variable problem. Color increments are bounded by available RGB headroom.
   Geometry variables are scaled to pixel displacement across the four views.
4. Refit RGB exactly at each proposed geometry and evaluate the physical gain.
   Try step fractions 1, 1/2 and 1/4; retain only strict improvements over step 2.
   The exact refit dominates the linearized color prediction. Old geometry and
   colors remain feasible fallbacks.
5. Pass the selected, refined coordinates and their fitness to CMA-ES update.
   Only a candidate beating the current triangle replaces it. The existing
   global sparse RGB solve still runs after each full mesh pass.

Central differences use the hard renderer, including the union of pixels
covered by positive and negative geometry probes. This includes edge-coverage
changes; it does not assume an unchanged footprint or use a soft rasterizer.
The linear model is a proposal mechanism, not the acceptance criterion. It can
be inaccurate around discrete coverage changes. Exact physical scoring and
fallback protect loss monotonicity, not global optimality.

The radius is the maximum projected vertex displacement in any training view
**per local step**. Multiple steps can accumulate a larger displacement.
Finite-difference scale and maximum accepted-step radius are separate settings.
All candidates receive the same refinement budget in a given run. This changes
the search operator and effective evaluation, not the physical loss definition.

## Parameter screening and full-mesh comparisons

Screen 12 settings on 128 baseline triangles/proposals for each seed 73, 97,
131: 384 proposal cases, 4,608 candidate refinements. Each case starts from
the same frozen-baseline residual and a Gaussian geometry proposal with world
sigma 0.005, followed by the exact local RGB fit. Settings cover radii 1, 2, 4,
8 pixels, difference scales 0.5, 1, 2, 4 pixels and one to three local steps.
The case lists and all settings are saved in `screen-73.json`, `screen-97.json`,
`screen-131.json`. These sampled gains are diagnostic sums over independent
residuals; they are not final mesh loss reductions or convergence guarantees.

Full-mesh trials use one pass, population 8, three CMA generations per triangle,
sigma 0.005, and identical starting checkpoints. A matched control disables
refinement. Additional controls use the prior population 12 / six generations
per triangle, including five- and ten-pass continuations to assess extra
ordinary evolution. Global RGB fitting remains enabled for all full-mesh runs.
The three shortlisted settings are repeated with seeds 23 and 47. Inheritance
changes subsequent CMA distributions, so matching seeds and budgets does not
mean all later generated coordinates are identical. Two seeds give a useful
replication check, not a broad statistical study of arbitrary target sets.

The user explicitly selected **loss per CMA geometry proposal**, rather than
wall-clock time, as the comparison criterion. One refinement trial has 18,432
CMA proposals; the original one-, five- and ten-pass controls have 55,296,
276,480 and 552,960. Finite-difference geometry probes and backtracking trials
are additional internal work and are not counted as CMA proposals. Thus this
comparison does not claim fewer total renderer evaluations. Actual timings
remain recorded for reproduction but do not determine parameter selection.

These are fixed-budget comparisons, **not convergence-to-plateau runs**. No
method is declared converged. Progress per proposal and the final loss at a
specified budget are the measured outcomes. A possible future operational
plateau rule discussed with the user is less than 0.1% relative loss reduction
per full pass for three consecutive passes, measured after global RGB fitting;
that rule has not been applied retroactively to these trials.

The user explicitly confirmed that the current experiment should remain
fixed-budget. The final optimizer must support automatic plateau detection and
automatic checkpoint/stop. Its threshold and patience are not finalized; the
0.1% / three-pass example above is a proposal, not an accepted default.

Reproduction (PowerShell; one BLAS thread avoids oversubscription):

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
.venv\Scripts\python.exe -m lisa2.refine_experiment --seed 73 --count 128
.venv\Scripts\python.exe -m lisa2.hybrid_gouraud --source runs/baldwin-plus/baseline.npz --output runs/new-refine --passes 1 --population 8 --generations 3 --seed 23 --refine-radius 2 --refine-difference 2 --refine-steps 2
.venv\Scripts\python.exe -m lisa2.refine_report
```

The report script independently reconstructs every completed run, verifies
reported loss, monotonic history, RGB/sphere bounds and winding invariance,
exports vertex-color OBJ files and generates actual-render comparisons.
`tests.check_local_refine` additionally verifies the sampled raster against
the full raster and checks exact gain and projected-step bounds. A real
refinement run was paused at triangle step 65 and resumed; the observation is
saved in `runs/baldwin-plus/pause-resume-observed.json`.

## Results

All runs completed. Losses below are independently recomputed full physical
losses after the final global RGB solve. Each row starts from the same baseline.

| Method | CMA proposals | Seed 23 loss | Seed 47 loss |
|---|---:|---:|---:|
| Frozen baseline | 0 | 0.0606273160 | same checkpoint |
| Matched control, no refinement | 18,432 | 0.0605514047 | 0.0605617340 |
| Radius 2, differences 2, one step | 18,432 | 0.0592826921 | 0.0593830048 |
| Radius 2, differences 2, two steps | 18,432 | 0.0581522451 | 0.0581188344 |
| **Radius 4, differences 2, three steps** | **18,432** | **0.0574962948** | **0.0575825402** |
| Original-budget control, one pass | 55,296 | 0.0603008561 | not repeated |
| Original-budget control, five passes | 276,480 | 0.0593619780 | not repeated |
| Original-budget control, ten passes | 552,960 | 0.0584873967 | not repeated |

The best tested setting wins in both full-mesh seeds: **5.1644% and 5.0221%**
lower loss than the frozen baseline, mean 5.0932%. The one-step settings improve
by 2.2179% / 2.0524%; two steps improve by 4.0824% / 4.1375%. The original
optimizer's ten-pass control improves by 3.5296%, despite **30 times more CMA
geometry proposals**. This establishes better progress per evolutionary
proposal within these budgets, not an exact 30x speedup to a common converged
solution or superiority in total physical evaluations. No run is declared
converged; auto-plateau detection remains a final-version requirement.

Select radius 4 pixels, difference scale 2 pixels and at most three local steps
as the best **tested** refinement parameters. These are not claimed globally
optimal. All full-mesh refinement trials used population 8, three CMA
generations, sigma 0.005 and one pass. A larger hyperparameter or target-set
study was not performed. The screening winner agreed with the full-mesh result.

Best numerical checkpoint: `runs/baldwin-plus/r4-h2-n3-s23/best.npz`, SHA256
`3d47b0e174dd6bc12cf5a2d2b4609dfa3349c53f065f95d31d1d4777c44ca60f`.
Its interior error is 0.046762924136400284 and spill is 0.010733370698489843;
both improve over baseline. Vertices in 630 triangles changed. Overall mesh
movement, including CMA proposals as well as refinement, has RMS 0.01105894
world units, maximum 0.09260834, maximum projected movement 24.6287 pixels.
1,316 vertices moved more than one projected pixel in at least one view.
These aggregate movements are not the per-step refinement radius.

Of its 18,432 candidates, 18,169 gained additional exact loss reduction after
the initial RGB fit; 46,617 local steps were accepted. Summed candidate gains
include unselected population members and must not be interpreted as mesh loss
reduction. The recorded 78,010 backtracking trials are additional to CMA
geometry proposals and finite-difference probes.

Independent verification passed for every final checkpoint: reported/full loss,
monotonic accepted-update history, finite values, bounds and two-sided winding
invariance. Tests also passed for local linearization sampling and exact gain,
the original local RGB solver, global Gouraud design, camera clipping/endpoints,
checkpoint concurrency and the unchanged two-term objective. The checkpoint
concurrency test needed a workspace-local TEMP directory because the sandbox
denied its initial default temporary-file location; it passed there.

Artifacts in `runs/baldwin-plus`: `results.json`, `loss-vs-proposals.csv`,
the three screening JSON files, per-run checkpoints/configuration/validation,
vertex-color OBJ files, `comparison.png`, full-resolution
`best-comparison.png` and `best-view-1.png` through `best-view-4.png`.
`PreviewRefined.cmd` opens the experimental numerical winner. All completed
comparison runs are frozen so viewer continuation forks a new run.

Actual renders show modest local changes; stray triangles and outline/background
artifacts remain. No artistic winner is selected solely from the numerical
objective. Baseline preview selection and all historical checkpoints are
preserved byte-for-byte. No old Git history was rewritten.
