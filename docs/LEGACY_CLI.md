# Lisa2 — four-image tetrahedral proof of concept

## Fresh checkout

Create the Python environment and launch the Studio:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\Lisa2.cmd
```

Choose four images and start a new project. Local images, generated models,
experiment runs, saved projects and virtual environments are excluded from Git.
The experiment reports describe local measurements; their `assets/` and `runs/`
paths refer to optional local artifacts, not bundled downloads. Preview shortcuts
for those experiments require the corresponding local checkpoints.

## Lisa2 Studio desktop application

Double-click **Lisa2.cmd** for the project authoring application: four drag/drop
target slots, four live best-so-far render tiles, Start/Stop, persistent
fitness/proposal history, JSON projects, Save As, a separate live 3D preview,
configurable evolution/color/refinement modes, automatic plateau stop,
statistics CSV, vertex-color OBJ and camera-dive GIF export.
Triangle count and target resolution are configurable; defaults remain 768
triangles and 640x480, with fixed 4:3 aspect ratio. Changing dimensions after
training creates a separate project instead of overwriting model/history.
The selected inherited position/RGB refinement is enabled by default. See
[STUDIO.md](../STUDIO.md) for the workflow, settings, project files and checks.
The existing Preview launchers below still open their preserved experiment runs.

Python implementation from scratch. One shared, two-sided flat-colored triangle
mesh is projected from four cameras at the vertices of a regular tetrahedron.
All contributions are additive on black: no textures, lighting, depth buffer,
backface culling, per-view colors or hidden view-specific images.

## Open the existing experiment

Double-click **Preview.cmd**. It opens a native **640×480 software-rendered**
image with a separate control/fitness panel. No GPU rasterization is used.

- **1–4:** smooth 1.6-second camera transitions, including interruptions.
- **Space:** pause/resume a running optimization; after completion, continue
  for one additional refinement round from the checkpoint.
- **E:** export the current mesh as OBJ + MTL into the current run directory.
- **Escape / close:** close the preview. A training child started by the preview
  is asked to checkpoint and stop; a separately started trainer is not killed.
- Drop four image files into the window to start a separate custom experiment.
  Images are collected in arrival order, contained without aspect distortion
  on black. This prototype begins once the fourth file arrives and never
  overwrites the supplied proof-of-concept run. Use one custom job at a time.

This is the requested experimental prototype, not a polished final asset editor.
The custom drop workflow has not yet been manually tested end-to-end. Better
slot management, validation feedback and run selection belong to the next step.

## Environment and commands

The supplied local environment is `.venv/`; dependencies are in requirements.txt
and the exact versions used in requirements-lock.txt. For a new checkout:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m lisa2.train
.venv\Scripts\python.exe -m lisa2.preview
```

Generate the same progressive experiment from scratch, without overwriting a run:

```powershell
.venv\Scripts\python.exe -m lisa2.train --objective rgb --output runs/repeat128 --width 128 --rounds 3 --generations 8
.venv\Scripts\python.exe -m lisa2.train --objective rgb --output runs/repeat320 --width 320 --rounds 4 --generations 10 --warm-start runs/repeat128/best.npz
.venv\Scripts\python.exe -m lisa2.train --objective rgb --output runs/repeat640 --width 640 --rounds 4 --generations 10 --warm-start runs/repeat320/best.npz
.venv\Scripts\python.exe -m lisa2.preview --run runs/repeat640 --export
```

For checkpoint continuation use the **same images, width, seed, population,
triangle count and generations** and append `--resume`. Increase `--rounds` to
extend a completed run. Ctrl+C checkpoints and exports. If using command-line
continuation after a previous stop/pause, set the run's control.txt to `run`.
The preview Space control and Train.cmd handle that for the default run.

## Geometry and optimizer

768 triangles / 2,304 unshared vertices; every vertex is constrained to the unit
ball. Camera directions are normalized `(1,1,1)`, `(1,-1,-1)`, `(-1,1,-1)` and
`(-1,-1,1)`, with pairwise dot product -1/3. All cameras are at radius 3.2 and
look at the origin. Vertical FOV **42°**, horizontal approximately **54.2°**,
aspect 4:3. The sphere's vertical angular diameter is approximately 36.4°,
leaving a framing margin and avoiding near-plane crossings.

The ready-made evolutionary framework is **DEAP**, using its **CMA-ES Strategy**.
This is an evolution strategy, rather than a conventional crossover GA.
The mesh is optimized block by block: DEAP evolves nine geometry coordinates
for one triangle while the others are fixed. The RGB color for each candidate
has an exact nonnegative weighted least-squares solution across all four views.
This reduces the search dimension and lets the framework own covariance
adaptation, population sampling and selection. No custom GA is implemented.

Fitness is `1 - weighted squared RGB error / error of an all-black image`.
Every view has equal aggregate weight; foreground receives extra emphasis,
but light leaking onto black is still penalized. The objective uses unclipped
additive sums, preventing saturation from concealing excess energy. Display
clamps to byte RGB. Fitness is **not a perceptual similarity percentage**.

The four original procedural targets (orbit, eye, sun, lotus) share a warm
chromaticity and mostly black backgrounds. No external artwork was downloaded.
They are regenerated by targets.py. A new arbitrary set of images may be much
harder or impossible to fit well with positive additive contributions.

## Artifacts and export

The completed 640×480 experiment is in `runs/dos640/`:

- best.npz: full precision mesh, colors, configuration, checkpoint and history.
- model.obj / model.mtl: actual shared triangle geometry and per-face RGB.
- comparison.png: targets above, evolved projections below.
- orbit.gif: four smooth transitions (12 samples/sec; the live preview is not
  limited to that GIF frame rate).
- fitness.png, progress.json, summary.json, validation.json: actual run data.

**OBJ/MTL does not encode additive blending.** A normal opaque OBJ viewer will
show a different result. A DOS importer must disable culling/depth and add the
flat RGB contributions over black. The float32 positions plus RGB8 colors need
about 30 KB, excluding any runtime-specific indices/structures.

Generated assets, run outputs and .venv are gitignored, and remain present on
this machine. The initial experiment's saved meshes are also copied to
`assets/checkpoints/` so the warm-start references can be reconstructed locally.

## DOS performance scope

Target: **Pentium II 333 MHz / Riva TNT, software rendering, 640×480**.
The TNT is not used for geometry or rasterization. The Python/Numba rasterizer
is an experimental reference, not the final DOS span renderer. Modern host
timings are **not** a Pentium II performance prediction. Measure the actual
optimized DOS renderer before fixing a frame-rate budget. The saved validation
report includes pixel-blend counts for the four fixed views; intermediate views
can have different overdraw.

## Verification

```powershell
.venv\Scripts\python.exe -m tests.check_experiment
```

Checks tetrahedral angles, camera orthonormality, the sphere staying in all
perspective frusta, smooth orientation endpoints, incremental fitness against
an independently recomputed full image, and correct upscaling of small targets.
Final fitness was independently recomputed from the entire mesh. OBJ counts,
finite values, sphere bounds, monotonic accepted-update fitness and byte-color
quantization were verified. A live optimizer pause/resume was exercised.
The preview window launched without errors. Computer Use found the window,
but its capture approval timed out, so automated physical key/drop tests were
not completed. No manual interaction is claimed.

Optimizer reference: https://deap.readthedocs.io/en/stable/examples/cmaes.html

## Previous silhouette-first experiment (retained for reproduction)

The original objective remains available as --objective rgb. The new
--objective structure compares actual rendered silhouettes and RGB gradients,
preserves interior colors, and separately penalizes light in the background.
Correct black contributes zero error and earns no positive reward. An all-black
render scores exactly zero against the fixed black-reference baseline.

Defaults: color 4, edge 1.5, background 6, background-linear factor 0.08,
silhouette 3, edge normalization area. The target foreground threshold is
max-RGB > 0.025. Rendered soft visibility saturates at max-RGB 0.12. Foreground,
background and contour bands are normalized separately per camera.

There is no masking in the rasterizer, preview or OBJ export. The actual mesh
must produce the silhouettes. Color candidates include an analytic quadratic
proposal, intensity variants, the existing color and a visibility-floor
candidate. Every candidate is scored against the real combined nonlinear loss.
This is not an exact global color optimizer. DEAP still optimizes geometry.

--edge-norm energy is an optional tested alternative, not the selected default.
Resume must use the same objective, coefficients and normalization; changing
these requires a new output plus --warm-start. Old preview runs missing objective
metadata are treated as RGB. The legacy Train.cmd explicitly selects RGB.

Checkpoint readers close their Windows file handles immediately, and both
readers and atomic writers retry transient file-sharing errors. See
STRUCTURE_EXPERIMENT.md for actual results and the remaining artistic limit.

## Current default: two-term color fitness + uniform mutation

New runs default to --objective color --black-penalty 0.15 --mutation uniform
--mutation-space pixel. Only interior color and small black-spill error are
scored. No edges or silhouette preservation term is active. When explicitly selected, adaptive silhouettes only
control the per-vertex mutation gate (90% / 3x outside any view; 25% / 1x inside
all views). All-black score is zero and black padding cannot dilute spill.
See COLOR_MUTATION_EXPERIMENT.md for the actual equal-budget comparison.
The adaptive and control runs are selectable through their local Preview.lnk.
Resume requires identical objective, penalty, mutation rule and step space.


## Independent pyramid and joint-color experiments

`python -m lisa2.experiments --method curriculum --output runs/new-curriculum
--max-stage-rounds 8` uses signed, exactly reconstructible Gaussian/Laplacian
bands. Cumulative targets add detail at measured plateaus. `--method control`
keeps the ordinary full-resolution uniform CMA objective; `--method multiscale`
fits simultaneous pooled RGB scales. All use the same shared two-sided mesh.
See PYRAMID_EXPERIMENT.md for measured outcomes and limitations.

Optional offline joint-gradient training uses a separate environment:
`python -m venv .venv-gradient`, then its pip with
`-r requirements-gradient.txt --extra-index-url https://download.pytorch.org/whl/cu118`.
Run its Python with `-m lisa2.gradient_trial --run runs/new-gradient`.
Torch is not needed for preview, OBJ export, or ordinary GA training.
Soft derivatives are only a training surrogate; selection uses the actual
640x480 software rasterizer and the unchanged two-term physical objective.

`python -m lisa2.gouraud --source runs/uniform-fine640/best.npz
--output runs/new-gouraud` jointly fits bounded per-vertex RGB on fixed geometry.
This changes color degrees of freedom (three RGB values per triangle), not
triangle count or visibility. CPU preview uses affine Gouraud interpolation.
OBJ export includes the common vertex-RGB extension and an explicit NumPy
color sidecar; consumers without vertex-color support need their own importer.

Backface culling is forbidden in accepted experiments. Both windings render
identically, all surfaces remain additive and two-sided at intermediate angles.
The speculative culling experiment was rejected and its builder removed.
`PreviewUniform.cmd` opens the frozen uniform baseline. Its `frozen.flag` makes Space
fork a new run rather than alter the reference checkpoint. New runs can be opened with
`python -m lisa2.preview --run runs/RUN`. Space routes continuation to the
checkpoint's own optimizer; a completed fixed-geometry Gouraud solve is final.


## Current experiment: profiled Gouraud geometry

`Preview.cmd` and `PreviewHybrid.cmd` open `runs/hybrid-gouraud`. The source is the last comparison
row, `runs/joint-gouraud`, kept unchanged. Run a new independent trial with:
```
python -m lisa2.hybrid_gouraud --output runs/new-hybrid --passes 4
```
DEAP CMA-ES changes only a triangle's nine geometry coordinates. Every candidate
gets a bounded three-vertex RGB fit against the residual of all other triangles,
using all four physical views. The tiny local convex problems use enumerated
active bounds, tested against SciPy. After each mesh pass, SciPy jointly refits
all vertex colors on the updated geometry. Local and global updates retain the
previous solution if an improvement cannot be established. The same full-detail
targets and two-term fitness are used throughout: no detail curriculum, pooled
surrogate, culling or depth test. The software renderer stays two-sided/additive.
Space pauses/continues the hybrid optimizer. A pause during the global color
solve takes effect when that solve returns. New trials have their own output;
viewer continuation of a frozen comparison forks rather than overwrites it.


## Orbit with a brief perspective dive

The preview's 1-4 camera moves now take 3.6 seconds. They orbit while briefly
dollying from radius 3.2 to 0.95 and back, using a smooth envelope and a restrained
five-degree bank. The eye never reaches the origin. Both exact training poses
are retained unchanged at the ends; model geometry, colors and fitness do not
change. A near plane at 0.12 clips crossing triangles before perspective division.
Clipped polygons remain two-sided and interpolate RGB; a deterministic fan
keeps winding reversal invariant. New key presses retarget from the current
camera pose and distance without a positional jump.

A toggles autoplay (1.4-second rests between moves). D toggles the dive for
subsequent moves, allowing direct comparison with an orbit-only camera. Space
still controls training; the camera controls never retrain the model.

`runs/hybrid-gouraud/camera-dive.mp4` is a 20-second 640x480/24fps export of the
same path, with a GIF, contact sheet and frame/time index beside it. Re-export:
`python -m lisa2.export_camera --ffmpeg PATH_TO_FFMPEG`.

## Optional inherited local refinement (Baldwinian+)

The hybrid optimizer can add a separate minor joint position/RGB refinement
after its existing exact local RGB fit, for every CMA geometry proposal.
`--refine-radius` enables it (zero remains the default),
`--refine-difference` sets the hard-raster finite-difference scale in pixels,
and `--refine-steps` limits local linearized steps. Radius bounds the projected
vertex movement in every training view per local step. Exact physical gain
checks and bounded RGB refits accept improvements only. CMA-ES receives the
actual refined coordinates together with their fitness; selected colors and
positions are inherited by the mesh. The global RGB pass remains unchanged.

See BALDWIN_PLUS_EXPERIMENT.md for frozen-baseline parameter screening,
replicated fixed-budget comparisons and limitations. Current preview defaults
and historical checkpoints remain unchanged. The final optimizer is required
to add automatic plateau detection and checkpoint/stop; that stopping rule is
not implemented or used in this fixed-budget experiment.
