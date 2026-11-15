# Lisa2 Studio

Standalone downloads are provided for Windows and Linux. Windows users run the
installer or portable `Lisa2.exe`; Linux users extract the portable archive and
run `./Lisa2/start.sh`. Python is included. Linux image slots use click-to-select;
native Explorer drag/drop is Windows-only. See [distribution](docs/DISTRIBUTION.md)
for requirements, cache/log locations and build instructions.

## Launch and basic workflow

With Python 3.12 installed, double-click **Lisa2.bat** (or **Lisa2.cmd**) in this
folder. On Linux run `bash Lisa2.sh` with Python 3.12/Tk/venv installed. The
launcher automatically prepares and reuses a local `.venv` and installs pinned
dependencies before starting Studio; a console shows setup progress/errors.
The four target slots accept file drops from Explorer. Click a slot to choose
an image instead. A multi-file drop fills consecutive slots from the slot under
the pointer. Images are contained on black at the configured 4:3 target resolution
(default 640x480) without stretching; EXIF
orientation is applied when importing. Exactly four images are required.

1. Fill the four slots.
2. Select the search options and press **Start evolution**. Choose a project
   JSON filename when first prompted. The selected images are copied into its
   companion data directory, so originals need not remain in their old paths.
3. Watch the full fitness graph, cycle/triangle position, CMA proposal count,
   physical loss components, accepted updates and refinement statistics. Four
   **Best so far** tiles below the targets show the actual saved mesh's four
   training-camera renders. They refresh in the background, at most once every
   1.5 seconds plus rendering time. Each is rendered at the project resolution before scaling
   into its tile; the label identifies the rendered checkpoint and fitness.
   These images live only in memory and are reconstructed after Load. No
   thumbnails or image buffers are serialized into the project or checkpoint.
4. **Stop & save** requests a safe stop after the current triangle update. A
   running global RGB fit finishes before servicing the request. Every completed
   triangle is checkpointed. Closing Studio requests the same safe stop and waits.
5. Use **File → Load project** later and press **Resume evolution**. The full
   history and lifetime proposal count continue; they do not reset at startup.

Target images define the physical objective and remain fixed after saving.
To try four different images with the same options, stop the worker and choose
**File → New project with current settings…**, then fill the four empty slots.
Starting evolution creates a new project and mesh using the copied settings.
Create a new project to compare different targets. Settings can be changed
between runs; their per-session snapshots and per-measurement values are saved.
Controls are locked while a worker is running. **Save project as** clones the
mesh, images and all history for a separate experiment. Copy/move a project JSON
**together with its companion data folder** to relocate it.
The content area scrolls vertically on smaller screens so the target/result
rows, fitness graph and lower settings remain accessible.

**Triangles** and **Target width (px; 4:3)** are configurable. Defaults remain
**768 triangles and 640x480**. Width must be a multiple of four; height is
calculated automatically (for example, 320 → 320x240, 800 → 800x600).
These values propagate to initialization, training, global RGB fitting, cycle
counters, statistics, saved settings, live tiles and native GIF exports. The
3D preview renders at the project resolution and scales into its display area.

Before training, Save can update these dimensions in place. Once a checkpoint
exists, Save/Start with a different count or resolution asks for a **new project
filename**, copies the targets and starts a separate mesh/history. Save As with
changed dimensions does the same; same-dimension Save As still clones all
progress. The old mesh and fitness graph are preserved. Mixing resolutions or
triangle counts into one historical fitness curve is rejected by the worker.
Older projects without the two settings infer them from rendering metadata,
with the original defaults as fallback.

## Search options

The always-present evolutionary search is DEAP CMA-ES, a ready-made evolution
strategy. The three search configurations are:

| Controls | Behavior |
|---|---|
| **Evolution only · positions & colors** | CMA-ES evolves all 18 coordinates of a triangle: nine xyz and nine vertex RGB values. No analytic RGB fitting, local refinement or global RGB fitting runs. |
| **Exact vertex-color fitting** | CMA-ES evolves nine xyz coordinates. Every geometry proposal receives the existing exact bounded fit of all three vertices' RGB against the other triangles' residual, jointly across four views. All mesh colors are refitted globally after each cycle. |
| **Local position & color refinement** | Adds the selected Baldwinian+ step after the exact RGB fit. Refined xyz coordinates enter CMA-ES update; selected xyz and RGB are inherited. This option automatically enables color fitting. |

Default: color fitting + local refinement, population 8, three generations per
triangle, sigma 0.005, seed 23. Refinement uses radius 4 projected pixels per
local step, finite-difference scale 2 pixels and at most three steps. Open
**Advanced settings** to change these parameters. Disabling color fitting also
disables refinement; selecting Evolution only disables both optimization passes.
All modes preserve the same physical objective and rendering constraints.

## Preserve contours

**Preserve contours** adds distance-based weights to the RGB error.
**Max radius** (20 px) is the distance outside the silhouette at which
the weight reaches 4. **Internal radius** (6 px) sets the inner band, where
the weight rises to 1.25 at the edge. Both radii are specified at 640 × 480
and scale with target width. Turning the option off disables both fields.
**Preserve thin features** uses local foreground thickness to increase the
RGB error weight by up to 2.25× on thin forms. Both options start on in new
projects. Existing projects keep saved settings and treat missing options as off.
**Balance separate regions** is optional and starts off. It erodes the mask to
find separate cores, then assigns pixels back within the original mask. The
largest regions split the selected foreground weight share equally. Defaults
are two regions and 20%. Views with fewer than two eligible regions retain
their existing weights.
Changing the objective on resume recalculates the plateau reference and records
an objective-change event. Fitness on either side of that event uses different weights.

## Evolve settings

Stop evolution after a checkpoint exists and click **Evolve settings…**.
Each round shuffles sixteen options in a 4 × 4 grid. The grid shows the same
camera view for every option. Scroll to switch cameras while keeping the
options in the same positions. A progress bar tracks completed trials.
Trials start from the same saved mesh and use the same triangle order, seed
and proposal budget. They run at up to 240 × 180, with a short global color
fit when enabled and eight geometry proposals per triangle for up to eight
triangles.

One click selects a card and starts the next round. An orange border marks
the selected card while the next previews render. New cards scroll into view,
and the cursor turns into a hand when selection opens. The winner returns
among the shuffled cards. Children combine settings from two candidates and mutate
individual values. The search includes contour radii, separate contour and
shell weights, thin-feature strength, and region balance.

**Use selected settings** saves the last selection to the project. Resume
continues from the saved mesh with those settings. **Cancel** or closing the
dialog discards the session.

## Automatic plateau stop

**Stop automatically at plateau** is enabled by default. A cycle means a full
pass over all project triangles, followed by the global RGB fit when color fitting
is enabled. The mesh is rendered independently at the cycle boundary. Define

    relative cycle gain = (previous cycle loss - current cycle loss)
                          / previous cycle loss

Defaults: gain below **0.1%**, for **three consecutive eligible cycles**, with
checks beginning at completed cycle 3. Thus the earliest automatic stop is
cycle 5. A sufficiently improving cycle resets the streak. Threshold, patience
and the first eligible cycle are editable. The project is checkpointed with
status `plateau` before stopping. Manual Resume after plateau starts a new
patience streak. Changing settings resets the streak as well.

This is an operational stop rule, not a proof of a global/local optimum.
Unchecked auto-stop allows evolution to continue until the user requests Stop.

## Files, portability and measurements

The project JSON is a small, versioned manifest containing relative paths,
settings, immutable image hashes and the latest cycle/proposal summary. It
does not embed images, vertex arrays or the history. Its companion directory has:

- `images/`: the four managed target PNGs.
- `best.npz`: full-precision geometry, colors, settings, exact cycle/triangle
  continuation state and complete fitness/proposal histories.
- `progress.json`: current status, counters and histories for Studio/preview.
- `statistics.csv`: lifetime measurements, both physical loss components,
  fitness, cycle, proposal count, elapsed time, mode, refinement work counters
  and the settings used for each row. **File → Export statistics CSV** copies it.
- `sessions.json`: complete settings snapshots and starting step/count for each
  training session, including sessions with different experimental settings.
- `global-NNNNNN/`: saved global RGB fits per completed color-fitting cycle.
- `worker.log`, and `error.json` on failure: diagnostic output.

The graph uses persisted **CMA-ES geometry proposal counts**, not counts inferred
from the current population/generation settings. RGB solves and refinement's
internal finite-difference probes are separate work. Their counters appear in
the CSV; they are not disguised as CMA proposals. Settings changes and Save As
preserve the earlier graph coordinates and fitness values. A per-project lock
prevents concurrent writers and detects abandoned locks from dead processes.
Random sampling resumes deterministically at triangle boundaries when settings
are unchanged. No mid-triangle CMA population is represented as completed work.

Fitness remains `1 - physical loss / all-black loss`, not a perceptual similarity
percentage. The physical objective has exactly two terms: foreground squared
RGB error and 0.15-weight squared light on black. Black padding cannot dilute
the error. Numerical progress is not automatically an artistic improvement.

## 3D preview and OBJ export

**3D preview** opens the live saved mesh in a separate software-rendered window.
It is available after the first checkpoint and reloads while evolution runs.
Keys **1–4** move smoothly to the four tetrahedron cameras, **A** toggles autoplay,
**D** toggles the established perspective dive, and **Escape** closes preview.
Training is controlled in Studio; preview cannot start a second trainer or
replace the targets. Closing preview does not stop the project worker.

**File → Export → OBJ with vertex colors** writes:

- `.obj`, with one `v x y z r g b` record per vertex and the original faces.
  The header includes four `# camera {JSON}` comments in target-slot order:
  `center` (camera position), `lookAt`, orthonormal `up`, vertical
  `fovY_degrees`, `aspect`, and the checkpoint's target `image` filename/path.
  These comments describe the exact fixed renderer cameras; OBJ viewers do not
  automatically configure cameras from comments. Unicode paths use JSON escapes.
- `.vertex-colors.npy`, preserving full-precision RGB for compatible importers.
- `.render.json`, documenting additive blending, black background, two-sided
  faces, no depth test, RGB bounds and affine Gouraud interpolation.

The model is the actual common mesh, without baked textures or per-view data.
An ordinary opaque OBJ viewer will not reproduce this effect: it must support
the vertex-RGB extension and the documented rendering configuration. There is
no 3DS item in the application's export menu.

**File → Export → GIF · orbit & camera dive** exports a frozen checkpoint
snapshot independently of subsequent evolution. It uses the same established
`CameraMove` and software renderer: views 1 → 2 → 3 → 4 → 1, 1.4-second holds,
3.6-second moves, radius 3.2 → 0.95 → 3.2, the five-degree bank and near-plane
clipping at 0.12. Output follows the project resolution (default 640x480),
20 fps, a seamless 20-second loop.
One palette is shared by all frames to avoid changing palettes over time;
GIF's 256-color limit still quantizes the exported image. Live tiles remain
ordinary RGB images.

Export runs in the background with a frame-progress indicator. It needs no
FFmpeg, GPU renderer or extra dependencies. The destination is replaced only
after a complete temporary GIF has been written. Evolution and project loading
can continue while exporting; the GIF retains its one original model snapshot.
Closing Studio waits for an active GIF export and any pending training stop.

## Verification

Run in the existing environment:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.venv\Scripts\python.exe -m tests.check_project
.venv\Scripts\python.exe -m tests.check_studio
.venv\Scripts\python.exe -m tests.check_derived
.venv\Scripts\python.exe -m tests.check_dimensions
```

Project tests cover exact interrupted/uninterrupted mesh/history equivalence,
all three modes, settings changes, proposal/history continuity, relocation,
Save As, locks, vertex-RGB OBJ and automatic stopping at a real cycle boundary.
Studio controller tests run with a withdrawn window and mocked file dialogs:
slot-drop mapping, native drop registration, settings, worker Start/Stop,
Load/history, preview routing and exports. They never activate windows or send
desktop keyboard/mouse input. A complete 768-triangle color-fit cycle plus
global RGB solve was separately completed; a deliberately permissive test
threshold triggered the real automatic stop and saved status `plateau`.

One initial native-window layout inspection was performed before the user
requested no desktop control. Subsequent verification stayed in the background.
Actual Explorer-to-window dragging and physical preview-key interaction were
not completed under that restriction. Camera endpoints/clipping, local RGB,
Gouraud/winding and physical objective regression tests also passed. The earlier
experiment checkpoints and launchers remain unchanged. No Pentium-II runtime
performance has been measured; this is the Windows authoring application.
