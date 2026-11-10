# Lisa2 experiment log

## Automatic source-checkout launchers

Added Lisa2.bat and Lisa2.sh for clone-and-run source use; Lisa2.cmd forwards to
the same Windows path. With Python 3.12/Tk/venv available, the stdlib bootstrap
creates a local environment, checks pinned dependency versions, installs only
when needed, and launches Studio. --prepare-only supports setup/CI checks without
opening a window. No system Python or apt packages are installed automatically.
The release workflow tests source bootstrap on both operating systems.
The Windows bootstrap was exercised in a fresh path containing spaces: automatic
venv/dependency setup and a full Studio/worker/resume/export/preview check passed.
Repeated setup reused the environment. A separate Python without Tk correctly
failed with an actionable prerequisite message. Linux shell syntax was checked;
native Linux execution remains gated by the first GitHub workflow run.

## Standalone distribution and automatic releases

Added a common frozen/source launcher for Studio, worker and preview; writable
user-data logs/Numba cache; PyInstaller native bundles; a per-user Inno Setup
installer; Linux tar.gz/start.sh and Windows portable ZIP. The GitHub workflow
builds on master pushes, tests real packaged worker/resume/global-fit/render/
OBJ/GIF/preview paths, then publishes complete releases with checksums only
after both operating systems pass. No personal token or signing secret is
required. The local Windows executable and installer passed the full check,
including silent install/uninstall and execution with no Python on PATH. Linux
archive checks are configured for Ubuntu 22.04 and 24.04 and await the first
GitHub run. Local checks use withdrawn Tk windows and SDL dummy preview, without desktop input.
Default dimensions, optimizer behavior and existing project histories remain
unchanged. Source runtime diagnostics now live in runs/runtime/.

## Camera metadata in OBJ comments

Vertex-RGB OBJ headers now list all four fixed tetrahedral cameras as JSON
comments with center (eye), lookAt, orthonormal up, vertical FOV in degrees,
aspect ratio and target image reference. Studio passes checkpoint image paths;
standalone exports without image metadata explicitly use null. Mesh records and
vertex colors are unchanged. check_obj_cameras verifies all four projections
against the renderer, Unicode filenames and mesh record preservation.

## Native file-drop crash mitigation

After a reported crash dropping the first target, removed Tk calls from the
Windows window procedure. WM_DROPFILES now copies paths and screen coordinates
into a queue, releases HDROP immediately, and delivers through a regular Tk
timer. Closing cancels the timer and clears pending drops. Added a real Unicode
WM_DROPFILES regression on a withdrawn window that forbids after_idle calls
inside the native handler; the hidden full Studio regression also passes.
The original Explorer crash has not been reproduced, so the change addresses
unsafe reentry rather than claiming a confirmed crash stack. Studio now records
native fatal stacks and Tk callback exceptions in the runtime data directory for diagnosis.

## Bounded replacement pilot and configurable project dimensions

Tested only residual-driven triangle replacement, as requested: current best
stopped memetic checkpoint, 64 low-marginal-contribution triangles, two CMA
generations/population eight, seeds 23/47, four matched arms of 1,024 proposals.
Both arms retain exact RGB fitting and the selected local refinement. Half the
replacement populations receive new unit-ball triangles seeded from four-view
residual point support; all candidates use the unchanged physical loss. The
same capped global RGB refit is attempted in every arm.

No externally seeded candidate was a final winner. Controls beat replacement
arms in both seeds; losses differ only by tiny amounts and actual renders show
no material visual improvement. Combined arm runtime was about 181 seconds.
Kept artifacts/report and source checkpoint intact; did not add a Studio
checkbox because this bounded pilot did not establish value. It is not a proof
against every replacement or globally color-coupled search mechanism. See
REPLACEMENT_EXPERIMENT.md; no further replacement run remains pending.

Added configurable triangle count and 4:3 target width, retaining defaults 768
and 640x480. Height is inferred; width must be a positive multiple of four.
Updated project manifests, initialization, worker cycles/stats, global bounded
RGB design matrices, checkpoint-derived views, project 3D preview and native
GIF/OBJ metadata to respect dimensions. Trained dimension changes create fresh
projects via Save/Start/Save As; worker/API guards prevent splicing incompatible
models or fitness histories. Legacy manifests infer original settings from
rendering metadata. No trained model/history is silently resized or truncated.

Tests passed for a complete 8-triangle, 64x48 memetic cycle and global RGB fit,
resume/history, native image/GIF sizes, OBJ vertex counts, invalid dimensions,
old metadata and protection against in-place changes. Hidden Studio checks
confirm new-project creation preserves the old checkpoint. Existing default
project, derived render, Gouraud and camera checks pass. All testing ran in the
background without desktop input or window activation.

## Derived UI renders, GIF camera export and research review

Added four best-so-far render tiles directly below the target slots. A background
worker reads one checkpoint, renders all four native 640x480 hard views and
hands RGB images to Tk on the main thread. Refresh is throttled; epoch checks
discard stale results after New/Load. Derived images remain in memory and are
never written into project JSON, NPZ or image caches. Added vertical scrolling
so smaller screens retain access to the graph and settings.

Restored GIF to File → Export at the user's request. It uses the established
CameraMove/clipping/software renderer on one fixed model snapshot: four views,
1.4s rests, 3.6s transitions, radius 3.2 → 0.95 → 3.2 and existing banking.
Native output is a 640x480, 20fps, seamless 20-second loop. A shared 256-color
palette avoids changing palettes between frames. Export runs separately from
training with progress and atomic destination replacement; closing waits for
completion. No FFmpeg dependency was added. OBJ remains available; no 3DS.

Hidden-window tests cover live previews during training/load, absence of derived
serialization and GIF menu routing. Renderer/GIF tests verify native view pixels,
camera endpoints and mid-dive radius, exact duration/loop and unchanged input.
A real stopped-model export was generated and decoded: 640x480, 20,000ms,
289 stored frames after duplicate merging, matching first/last images. All
verification stayed in the background without activating desktop windows.

Reviewed primary literature on hard-forward rasterization gradients, residual
matching pursuit, visual-hull compatibility and LPIPS evaluation. Documented
actionable Lisa2 adaptations and their limitations in RESEARCH_DIRECTIONS.md.
The first proposed bounded optimizer trial is residual-driven replacement of
unhelpful triangles within the same fixed budget; it was not launched here.
No optimizer, loss, targets, cameras, culling or triangle-budget constraint was
changed. The prior incomplete soft-raster/Adam pilot remains a negative pilot,
not evidence against all differentiable-rendering methods.

## Consolidated and stopped the runtime experiment

The user confirmed pure Evolution only as the GA comparison and defined common
quality retrospectively as the weaker best attained fitness, rewinding the
stronger run's actual clock history. Discarded the initial timing batch after
the user reported an overlapping build; retained it marked INVALIDATED.
Restarted serial, single-thread, below-normal-priority workers in
`runs/timing-convergence-clean` after the user confirmed no heavy job was active.
Only seed 23 began. GA-only reached the configured plateau in 374.5065 seconds
launch-to-exit, with no fitness improvement from the shared optimized start.

At the user's request to consolidate rather than keep waiting, safely stopped
the memetic run after 11 full cycles plus 384 triangles: 8,856.7556 seconds wall,
8,753.1719 CPU seconds, 211,968 CMA proposals. Fitness 0.9786057480687784; loss
0.05243470181974199, 13.5131% below start. It had not converged: last completed
cycle gain 0.226087%, above the 0.1% criterion. Report this as a censored run,
not an estimated convergence time. The shared-fitness target equals the common
input fitness 0.9752630218594932, so optimization time to it is zero for both;
this warm-start yields no meaningful equal-quality speedup ratio.

The coordinator and workers exited; four prepared seed-47/71 runs never
started. Preserved checkpoint/history, actual wall/CPU traces, per-cycle global
fits and immutable snapshots; generated consolidated JSON, clock-history CSV,
before/after renders and independent physical validation. All bounds, winding,
monotonic histories and recorded losses verified. Studio can Load/Save As/Resume
the stopped project. No background benchmark remains pending. See
TIMING_EXPERIMENT.md for measured results, limitations and artifact paths.

## Lisa2 Studio project application

Built a Windows Tk desktop application, launched with Lisa2.cmd. Four explicit
image slots accept native Windows file drops or file-picker input. Start saves
a small JSON manifest and managed target PNGs, then launches a hidden worker.
Stop/close requests a checkpoint at a triangle boundary; global RGB fitting
finishes before stopping. Load and Save As preserve mesh, cycle position,
complete fitness history and lifetime proposal coordinates. Projects use
relative paths and can be relocated together with their data folders.

Added a dedicated resumable project worker with three modes: pure CMA-ES over
all 18 position/RGB coordinates; CMA geometry plus exact local/global RGB fits;
and the selected inherited joint refinement after local RGB fitting. Default
is population 8, three generations, sigma 0.005, radius 4 px, differences 2 px,
three local steps. Accepted mesh/render/objective constraints remain unchanged.
Per-project process locks prevent concurrent writers. Session settings and CSV
rows retain experimental parameters, physical loss components and internal
refinement work separately from CMA proposals. Sampling resumes deterministically
at triangle boundaries when settings are unchanged.

Implemented configurable auto-plateau stop: relative physical loss improvement
below 0.1% for three consecutive eligible cycles, beginning at cycle 3 by
default. Decisions occur after the full mesh pass, global RGB fit when enabled,
and an independent full render. Auto-stop checkpoints status plateau before
exiting. It is a heuristic stopping rule, not an optimality proof. Manual Resume
or settings changes reset the patience streak. All thresholds are editable.

Studio opens the existing camera/renderer in a separate live read-only training
preview; 1-4, autoplay and dive remain available. The user withdrew 3DS and
requested only OBJ, so the app export menu provides vertex-RGB OBJ with a full
precision NumPy color sidecar and rendering metadata. No 3DS/GIF export was added.

Tests passed for interrupted/uninterrupted equality, every mode, settings changes,
proposal/history continuity, relocation, cloning, locks, OBJ RGB and actual
plateau stop. A full 768-triangle color-fit pass and global solve completed with
a permissive test threshold triggering auto-stop. Hidden-window controller tests
cover slot mapping/drop-hook registration, settings, Start/Stop, Load/history,
preview routing and exports. Existing refinement, RGB, Gouraud, camera and
objective checks passed. One initial native layout inspection preceded the
user's request to avoid desktop control; subsequent verification used background
tests only. Physical Explorer dragging/preview-key QA was not completed under
that restriction. No prior checkpoint/history was overwritten. See STUDIO.md.

## Inherited local position/RGB refinement (Baldwinian+)

Preserved the current best hybrid checkpoint byte-for-byte; copied it to
`runs/baldwin-plus/baseline.npz` (SHA256
`07264dfe60a84691030ed072383754f89843d3e71bf20a647b1a863921896064`).
Kept the existing exact local RGB fit as the first optimization pass. Added an
optional separate finite-difference joint position/RGB linearized refinement,
with bounded SciPy least squares, exact RGB refitting and hard-raster gain
acceptance/backtracking. Refined coordinates and fitness enter CMA-ES update;
selected geometry/colors are inherited. Global RGB fitting remains unchanged.

Screened 12 settings on 384 candidate cases across seeds 73/97/131, then ran
three shortlisted settings twice on the full mesh with seeds 23/47. Each
refinement trial used 18,432 CMA proposals (population 8, generations 3, one
pass, sigma 0.005). Best tested: radius 4 pixels per step, differences 2 pixels,
three local steps. Final independently recomputed losses 0.0574962948 and
0.0575825402, 5.1644% / 5.0221% below baseline 0.0606273160. One-step and
two-step variants also won in both seeds, with smaller gains. The original
optimizer's ten-pass control used 552,960 CMA proposals and reached
0.0584873967. Better loss with 30x fewer evolutionary proposals is measured;
fewer total renderer evaluations or convergence to an optimum is not claimed.

The user explicitly prioritizes proposal count over time and kept this
experiment fixed-budget. Automatic plateau detection and checkpoint/stop is a
requirement for the final optimizer, not implemented here. Its threshold and
patience remain undecided. All accepted rendering/fitness constraints remain
unchanged; no soft surrogate, edges, culling or progressive targets were added.

Validated full losses, monotonicity, bounds and winding for every completed
run, plus sampling/exact-gain tests and existing RGB, Gouraud, camera,
checkpoint and objective tests. Observed pause/resume at step 65 of a real
refinement run. Created frozen comparison artifacts, a loss-versus-proposals
CSV and optional PreviewRefined launcher. Original Preview.cmd remains on the
prior hybrid baseline. See BALDWIN_PLUS_EXPERIMENT.md for complete results,
reproduction, limitations and checkpoint hashes. No historical commit changed.

## A new four-view experiment

Following the archive review, LisaGA was selected for a new experiment rather
than preservation work. Lisa2 is written from scratch in Python; no historical
LisaGA source was copied or changed. The objective is a single additive triangle
mesh approximating four black-background images under perspective projection
from the vertices of a regular tetrahedron.

Used the existing DEAP CMA-ES implementation instead of writing a new GA. To
avoid a huge covariance matrix, evolution is applied to nine coordinates of
one triangle at a time. RGB is fitted analytically across all four views.
The reference rasterizer is Python/Numba and entirely software based.

Created four original procedural symbols with compatible amber colors. The
initial 768-triangle experiment was evolved at 128x96, refined at 320x240, then
changed to 640x480 when the user clarified the DOS target resolution and the
Pentium II 333 MHz / Riva TNT hardware. No GPU rasterizer is used.

The first 640x480 attempt exposed a target-loading bug: thumbnail() did not
upscale the 320x240 source artwork. The run was stopped and retained separately
as runs/diagnostic-target-scaling. Switched to aspect-preserving contain()
with upscaling and added a regression check. The successful final run starts
from the previous correctly framed 320x240 mesh, not the diagnostic mesh.

Exported OBJ/MTL, actual per-camera views, a target/render comparison, an
animated camera tour, fitness histories and numerical validation. A companion
viewer provides keys 1-4, smooth perspective-camera interpolation, live
checkpoint reload, a fitness plot, pause/continue and OBJ export. Four-file
drop is a prototype entry point for a separate run, not a finished editor.

Validation covered tetrahedral angles, orthonormal frames, unit-sphere framing,
interpolation endpoints, incremental objective against a full recomputation,
image upscaling, monotonic accepted-update history, OBJ/MTL counts and an
8-bit color quantization check. Pausing and resuming an actual optimizer run
was confirmed. The live preview launched without stderr output. Computer Use
listed its window, but screenshot access approval timed out before physical
key/drop interaction; no completed manual UI test is claimed.

All 768 triangles are active. Exact result metrics and limitations are recorded
in EXPERIMENT.md. The retro machine has not been benchmarked. No history was
rewritten and no unrelated project was modified.

## Color and distinct identities, without code changes

The user requested filled colorful demoscene imagery instead of monochrome
line drawings. An initial generated set of orb/lotus/sun/torus sculptures was
rejected for shared radial symmetry. Replaced it with a portrait, spacecraft,
dragon and floating mountain island. Built-in imagegen generated these targets
and added black framing margins. Final files and exact prompts were copied to
assets/distinct/. No project source was modified.

Ran the existing optimizer at 128x96, 320x240 and 640x480, six rounds per stage,
twelve generations per block, population sixteen, seed 23 and 768 triangles.
Preserved all stages and the first monochrome experiment. Exported the actual
four views, camera animation, fitness plot, checkpoint and OBJ/MTL. Independently
recomputed final error and verified finite/bounded vertices, monotonic fitness,
and unchanged source relative to [local snapshot]. See COLOUR_EXPERIMENT.md for metrics
and visual limitations. No Pentium II performance claim was made.

## Silhouette-first fitness and honest visual comparison

The user rejected the colorful result for damaged outlines, and explicitly
prioritized artistically readable subjects over exact pixel colors. Added a
separate objective module for silhouette, gradient, interior color and black
background losses. Correct black is zero error, not a reward; a blank render
scores zero. No image masks were added to the actual renderer or export.

The first structural runs greatly reduced spill but traded away too much
interior color. Increased color weight and added a visibility-floor candidate
to avoid getting stuck with imperceptibly dim triangle colors. Tested a pair-
camera-plane geometry proposal; it did not help and was removed from source.
Tested energy-normalized gradient error; retained it as optional, while the
area-normalized outline640 run had the better measured contour/color tradeoff.
All intermediate run folders were retained. See STRUCTURE_EXPERIMENT.md.

A comparison reader exposed a Windows checkpoint-sharing failure. Replaced
persistent on-disk NumPy archive handles with in-memory snapshots, and added
bounded sharing-error retries for atomic writes and reads. A real concurrent
reader/writer test now passes, as does actual training continuation.

Final numeric checks confirm better contours and background cleanliness, but
foreground color error increased and the interior remains fragmented. The
requested artistic quality has not yet been achieved; this is recorded as an
experimental improvement, not a successful final demo asset. Saved selected
OBJ/MTL, camera animation and unretouched before/after evidence. No history was
rewritten, no original targets were changed, and no extra triangles were added.

## Remove edge/silhouette fitness; test adaptive vertices

The user found the previous result clearly worse and requested only interior
color plus a small black penalty. Added ColorObjective and made it the default.
It contains exactly those two quadratic terms; black penalty is 0.15 per pixel
relative to interior error. Both are normalized by foreground size, so correct
black never earns points and extra black padding cannot dilute existing spill.

Implemented the requested any-view silhouette-triggered mutation rule as a
gate on DEAP CMA-ES proposals: outside vertices accept 90% of offsets at 3x;
vertices inside every mask accept 25% at 1x. Masks do not enter fitness beyond
choosing interior/background regions, and are never applied at render time.

Coarse world-space steps mainly recolored a pretrained mesh. Kept those runs,
then scaled steps to image resolution and optimized existing warm triangles
instead of random reseeding in the first pass. Completed matched-budget
adaptive and ordinary CMA-ES trials at 640x480, same source mesh/seed/budget.
The ordinary control had lower final loss; no adaptive-quality gain is claimed.
All numerical outcomes and artifacts are in COLOR_MUTATION_EXPERIMENT.md.

Tests cover the two-term contract, penalty ratio, black-zero and padding
invariance, exact quadratic color solution, any-one-camera triggering and
measured mutation rates/variance. Final losses were independently recomputed.
Old objectives/runs remain available for historical reproduction. No history
was amended and no targets, cameras, renderer or triangle count were changed.


### Independent detail curricula and joint fitting

Preserved the selected uniform-mutation baseline byte for byte. Implemented
signed full-size Laplacian bands at Gaussian sigmas 16, 8, 4, 2 and 0 pixels;
their sum reconstructs the original target numerically, rather than treating
five blurred images as additive detail. The primary curriculum advances after
at least two passes when improvement normalized by that stage's black-reference
loss drops below 0.002; stage caps are reported separately. Kept the initial
capped pilot and then ran the convergence-driven trial plus full-detail cleanup.
Ran an ordinary uniform control with the same 24-pass population budget.

Our simultaneous pooled-color CMA pilot produced no convincing gain. Added a
separate optional PyTorch/Adam experiment to optimize geometry and colors
jointly. Soft coverage is only a derivative surrogate: regular independent
hard 640x480 CPU evaluations select the retained checkpoint. Reduced GPU memory
by accumulating the equivalent objective camera by camera; verified gradient
equivalence, finite differences, and the hard-coverage limit. This GPU trial is
still running at this implementation commit, and no success is claimed.

The archived LisaGA used per-vertex colors. Added a general two-sided affine
Gouraud renderer and a SciPy bounded global color fit on fixed geometry.
Tests prove equivalence to the original renderer for constant vertex colors,
winding invariance, four-camera coverage, and sparse fit/render equivalence.
The baseline-geometry Gouraud solve modestly reduces physical error; that alone
does not establish the requested artistic improvement.

A speculative one-sided coherent mesh was explicitly rejected by the user:
backface culling weakens the intended effect. Removed its builder from active
source and all active culling paths. Retained the rejected artifacts under
runs/rejected-culling for archaeology. Accepted renderers use every triangle
from both sides at all camera angles, with no depth test or visibility tricks.

Changed new GA runs to uniform mutations, reflecting the user's selected
baseline. Preview continuation now chooses the experiment's own optimizer;
it never feeds per-vertex colors into the flat-color trainer. Historical
commits were not amended. Final outcomes will be recorded separately.


### Negative result and final two-sided comparison

Independently recomputed all actual 640x480 losses. Frozen baseline: 0.0713367752;
24 further uniform passes: 0.0672379911; converged curriculum plus cleanup:
0.0801641270; global Gouraud color solve on frozen geometry: 0.0642658103.
The curriculum loses this warm-start comparison. Gouraud improves the objective
slightly, but does not deliver the requested artistic breakthrough. Kept the
original baseline selected and unchanged; no new visual winner is claimed.

Stopped the gradient pilot after checkpoint 900 of its planned 1200 steps.
Its last physical loss was 0.1926267206 and its best evaluated trained snapshot
was step 1 at 0.0934528888. It never beat the starting baseline in measured hard
renders. The final 320px stage was not run; retained complete resumable states
and explicitly report this as an incomplete negative pilot. Exact vertex-color
refits on step-800 and step-900 geometry also failed to beat the baseline.

Added a sampled visual-hull feasibility diagnostic outside the optimizer.
With two-pixel-relaxed masks and 512 depth samples, approximately one quarter
of sampled dragon foreground lacked zero-spill support inside the common unit
ball. This is not a proof or a new fitness term, but it exposes a geometric
tradeoff, especially around the horns. Saved the probe and comparison images.
No target, camera, culling, depth, or blending constraint was changed to hide it.

All pyramid, color-objective, Gouraud/winding, gradient, camera, checkpoint and
compile checks passed. Baseline SHA256 remains
E54745271986F35E19DB0F1DBE8942B74A8A32DB8E31596CC99B7FEC5553D7C7.
See PYRAMID_EXPERIMENT.md for budgets, limits, reproduction and artifact paths.


### Geometry evolution with profiled Gouraud colors

The user judged the last comparison row (global Gouraud RGB fit on the original
geometry) clearly better, and selected it for further development. Corrected
the earlier overly conservative visual assessment: it is the starting point
for the new hybrid trial, not a discarded variant. Preserve that checkpoint.

Implemented DEAP CMA-ES over triangle geometry only. Every proposed triangle
gets a bounded local Gouraud RGB solve against the four-view residual. Tiny
active-bound problems are tested against SciPy, including rank-deficient cases;
the local gain is independently checked against full software image differences.
After each mesh pass, jointly refit all vertex colors with the existing SciPy
sparse solver. Keep previous feasible solutions whenever no improvement is found.
Progressive details are inactive; the prior matched test did not support them.

Completed four passes and resumed for a fifth to verify checkpoint continuation;
observed pause at step 2402 and resumed it. Total 276,480 population evaluations,
five global solves, seed 23, sigma 0.005, 768 triangles. Physical loss fell from
0.06426581029508416 to 0.06062731601407705 (5.6616% reduction). Both the interior
color error and black spill fell. Vertices in 588 triangles moved. Independent
final renders confirm the loss, monotonic history, bounds and winding invariance.
No culling, depth test or camera-dependent attributes were introduced.

Added the hybrid preview continuation route and launcher. The standard preview
now opens the hybrid result; PreviewUniform.cmd preserves access to the earlier
baseline. Completed comparisons fork new runs on viewer continuation. Exported
actual renders, before/after contact sheet, orbit animation and vertex-color OBJ.
See HYBRID_GOURAUD_EXPERIMENT.md for method, measured limits and reproduction.


### Orbit, dive and reveal camera

The user wanted perspective to expose the same triangles forming different
images, rather than a plain rotation. Added a preview-only 3.6-second camera
move: existing orientation orbit, a smooth radial dive from 3.2 to 0.95 and back,
and restrained banking of at most five degrees. Tested minimum radii 0.95,
1.15 and 1.35 on actual mesh renders. Chose the closest for its brief full-frame
triangle perspective, with no approach to the origin. The four final image
poses and their rendered pixels remain exactly unchanged.

Added true near-plane clipping before division, rather than allowing triangles
behind the eye to flip onto the screen. RGB is carried through clipping; clipped
quads use a deterministic geometric fan, fixing an initial winding-dependent
color difference caught by the test. All visible faces remain additive and
two-sided; no backface culling or depth test was introduced. Training geometry,
colors, cameras and objectives are untouched.

Retargeting takes the current pose and distance, avoiding a positional jump
when a new view key is pressed mid-dive. Added A autoplay with 1.4-second rests,
and D to compare the next move with orbit only. Exported the exact camera path
to a 20-second 640x480 H.264 movie, a GIF, six sampled poses per transition and
a frame/time index. Existing trained checkpoints were not rewritten.

Tests verify exact endpoint pixels, valid orthonormal bases and bounded camera
distance, continuous retarget position, near-plane crossings, rejection behind
the eye and clipped Gouraud winding invariance. Reviewed all four transitions
in the contact sheet. This camera is a presentation change, not a new fit.
