# Pure evolution versus memetic time-to-plateau and time-to-quality

Requested measurements, not an inference from offspring counts.
The experiment runs only in the background and never activates desktop windows.

## Predeclared protocol

- Common warm start: `runs/baldwin-plus/baseline.npz`, physical loss
  0.06062731601407705, SHA256
  `07264dfe60a84691030ed072383754f89843d3e71bf20a647b1a863921896064`.
  Every run receives an exact copy of its positions and vertex RGB; its own
  experimental history starts at zero without modifying the original checkpoint.
- Pure evolution is the user-selected **Evolution only** mode: CMA-ES searches
  nine position plus nine RGB coordinates, with no analytic RGB fit, refinement
  or global color solve. RGB variables use the application's established scale.
- Memetic mode uses CMA geometry, exact local RGB fitting, inherited local
  joint refinement (4 px radius, 2 px differences, three steps) and global RGB
  fitting after every full mesh pass.
- Both use population 8, three generations per triangle, geometry sigma 0.005,
  768 triangles, 640x480, the same four targets/cameras, two-sided additive hard
  rendering and the unchanged two-term physical loss.
- Seeds 23, 47, 71; paired starts; alternate method order between seeds.
  Only one timed worker runs at a time. BLAS/OMP threads are fixed to one;
  Windows worker priority is below normal so foreground work has precedence.
  Before each timed child, require a 20-second window with mean aggregate CPU
  load below 5% and no sample above 10%; this wait is outside the measured run.
  During the run, record total CPU load and estimated load from other processes.
  These diagnostics cannot prove absence of all interference.
- Plateau rule: relative cycle improvement below 0.1% for three consecutive
  eligible cycles; checks begin at cycle 3. A cycle includes all 768 updates,
  the global RGB fit when enabled and an independent full mesh render. No fixed
  cycle cap is silently treated as convergence. Plateau does not prove optimality.
- **User-defined common quality:** after both runs stop, find each run's best
  attained fitness. Set the shared target to the lower of these two fitness
  values. Rewind the higher-fitness run's measured timeline to its first
  attainment of that target, with absolute fitness tolerance 1e-8. Retain first
  attainment for both runs and each run's separate time to the plateau stop.
  Do not substitute a preselected loss reduction for this comparison.
- If the common fitness was already present in the initial mesh, its
  time-to-quality is zero, not initialization time. Identify this as a trivial
  shared target rather than advertise a speedup. Auxiliary fixed loss-reduction
  milestones (0.1%, 0.5%, 1%, 2%, 5%) remain diagnostic curves only.

## Timing and interpretation

Time is measured directly, not estimated from proposal counts. Child wall and
process CPU clocks begin before importing the worker and include loading,
validation, JIT/cache loading, all fitness work, finite-difference probes,
linear/color solves, global fits, checkpoint/JSON/CSV I/O and trace publication.
The parent also records process-launch-to-exit wall time. Preparing paired
input copies is outside the worker timing. The application GUI is not running
as part of the timed work. Background foreground-user load is uncontrolled;
both wall and CPU results are retained, with repeats rather than fictitious
exclusive-machine timing. These are modern-host timings, not DOS predictions.

This is a **continuation** experiment from an already optimized color/geometry
state, not training from scratch. Pure evolution's fixed RGB mutation scale
and short per-triangle CMA budget can make escape from this state difficult.
Results apply to the application's actual configurations; they do not establish
the best attainable performance of a separately tuned general-purpose GA.
Time to a poor plateau must be reported with its plateau loss, never equated
with time to the same solution quality.

The observer hook only records committed measurements; it does not change
selection, sampled coordinates, RGB solves or stopping rules. Proposals and
internal refinement work are recorded separately. The entire trace and exact
settings are kept in `runs/timing-convergence`, including `protocol.json`,
per-run project/data folders, `timing.jsonl`, end/process timing JSON and
`results.json`. Incomplete runs remain explicitly incomplete.

The user reported that a build overlapped the initial batch in
`runs/timing-convergence`. **All timing results of that batch are invalid.**
Its coordinator/worker processes were stopped, and the retained artifacts are
marked `INVALIDATED.json`. Those times must not enter any comparison. Restart
with a fresh output directory after applying the user's fitness-based matching
rule above; the invalidation guard rejects reuse of that directory.

Reproduction:

```powershell
.venv\Scripts\python.exe -m lisa2.timing_trial --output runs/new-timing
.venv\Scripts\python.exe -m lisa2.timing_trial --output runs/new-timing --summarize
```

## Results

The user requested consolidation and termination rather than more waiting.
Stopped the clean batch safely after seed-23 pure evolution and part of seed-23
memetic evolution. No workers or coordinator remain running. Seeds 47 and 71
were prepared, but none of their four method runs started. This is one paired
trial, not a completed three-seed timing study.

The clean batch is `runs/timing-convergence-clean`. The user confirmed no build
or other heavy job was active at its start. Normal foreground/background system
load remained uncontrolled; both CPU and wall times and load diagnostics are
retained. The automatic low-load start gate was replaced by this explicit user
confirmation (`--user-confirmed-idle`). Do not describe this as a dedicated
exclusive-machine benchmark. The older invalid batch is excluded entirely.

| Seed 23 | Pure evolution | Memetic |
|---|---:|---:|
| Termination | Automatic plateau | Requested safe stop; no plateau |
| Completed cycles | 5 | 11 plus 384/768 triangles of cycle 12 |
| CMA proposals | 92,160 | 211,968 |
| Process launch-to-exit wall time | 374.5065 s (6m 14.5s) | 8,856.7556 s (2h 27m 36.8s) |
| Child CPU time | 366.5156 s | 8,753.1719 s |
| Best fitness | 0.9752630218594932 | 0.9786057480687784 |
| Best loss | 0.06062731601407705 | 0.05243470181974199 |
| Loss reduction from common start | 0% | 13.5131% |

The memetic time above is **observed time before requested termination**, not
time to convergence. Its last completed cycle improved loss by 0.226087%,
above the 0.1% threshold, with plateau streak zero. Its time to the automatic
plateau is right-censored: it had not reached that plateau when stopped. Do
not substitute an extrapolated stopping time or compare the two runtimes as
time to the same-quality optimum.

### Equal quality, using the user's retrospective fitness rule

The common target is **0.9752630218594932**, the pure evolution run's best
fitness. That fitness already existed in both input checkpoints. Consequently,
both have **zero optimization time to this shared target**. The memetic run's
unfinished plateau does not affect this target: its attained best is already
above the completed pure-evolution best and can only increase in future search.

This is a degenerate warm-start comparison, not a speedup. It yields no useful
positive time-to-equal-quality ratio. Pure evolution accepted no improvement
from this already optimized start under the application's default short CMA
budget and RGB mutation scale. This does not establish that a separately tuned
GA cannot improve it or that both methods would behave similarly from scratch.
Do not mix time-to-poor-plateau with time to the stronger method's quality.

### Measured memetic cycle history

| Completed cycle | Wall seconds from child timer | Fitness | Relative cycle loss gain |
|---|---:|---:|---:|
| 1 | 637.8 | 0.976540532 | 5.1644% |
| 2 | 1,281.8 | 0.977154953 | 2.6191% |
| 3 | 2,045.7 | 0.977548875 | 1.7243% |
| 4 | 2,821.7 | 0.977815092 | 1.1858% |
| 5 | 3,637.9 | 0.978032855 | 0.9816% |
| 6 | 4,430.8 | 0.978188055 | 0.7065% |
| 7 | 5,239.3 | 0.978308770 | 0.5534% |
| 8 | 6,056.0 | 0.978398995 | 0.4159% |
| 9 | 6,801.5 | 0.978466917 | 0.3144% |
| 10 | 7,641.9 | 0.978537514 | 0.3279% |
| 11 | 8,484.2 | 0.978586038 | 0.2261% |

The first full memetic cycle reproduced the previous selected trial's vertex
positions and colors byte-for-byte as NumPy arrays, confirming that timing
instrumentation did not change this optimization trajectory. Unit checks cover
best-fitness rather than final-point matching, first observed threshold hits,
initial-state zero time and invalidated-batch rejection.

### Preserved artifacts and continuation

Open `runs/timing-convergence-clean/memetic-s23.json` through Studio's File →
Load project to inspect or resume the saved mesh and complete fitness history.
The safe stop preserves the exact triangle-boundary state. `statistics.csv`,
`sessions.json`, `timing.jsonl`, checkpoint files and per-cycle global fits remain.
The root `CANCEL` file prevents the benchmark coordinator from launching more
trials. Ordinary Studio Resume writes its project control file and can continue
training; it does not silently turn the interrupted trace into a completed
timing experiment. A new uninterrupted timing run or explicit accounting for
separate timed sessions would be required for a final plateau measurement.

`results.json` consolidates completed, incomplete and unstarted runs, together
with the fitness-matched times. Source baseline and earlier experimental
checkpoints remain unchanged. There is no pending background measurement.

Independent validation reconstructed both final meshes and confirmed recorded
physical losses, RGB/sphere bounds, winding invariance and monotonic histories.
The GA history has 3,841 points; the memetic history has 8,844. See
`validation.json`. `fitness-vs-time.csv` exports both actual clock histories;
`before-after.png` shows initial versus stopped memetic renders. Immutable
checkpoint copies are retained in `snapshots/`, including the stopped memetic
checkpoint SHA256
`a231d514ad4acd97f607aa03845e8f2d91c84eb30e6e14e2de6bb87e7caf07a3`.
Use Studio's Save As before further experiments if the original timed project
files should remain unchanged.
