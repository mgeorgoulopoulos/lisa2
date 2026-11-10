# Short residual-driven triangle replacement pilot

## Fixed scope

The user requested a short test of triangle replacement only, and an optional
Studio checkbox only if it proved worthwhile. No other proposed research
method, objective change or convergence training was launched.

Started every arm from the same current best stopped memetic mesh, loss
0.05243470181974199, checkpoint SHA256
`a231d514ad4acd97f607aa03845e8f2d91c84eb30e6e14e2de6bb87e7caf07a3`.
The source checkpoint is unchanged. All 768 triangles, 640x480, four cameras,
shared vertex RGB [0,0.4], unit-ball bounds, two-sided additive rendering,
no depth test and the existing two physical loss terms were retained.

Selected the 64 weakest triangles by the exact loss increase caused by
removing each triangle with other colors fixed. For current image I, target T,
triangle contribution A and weights W, this is

    L(I - A) - L(I) = 2 <T - I, A>_W + ||A||_W^2.

Ranking is therefore an existing-objective marginal cost, not a silhouette
gate, edge reward or new fitness term.

## Matched trial

Two seeds, 23 and 47. Each arm updates the same 64 selected indices in the same
seeded order, using two CMA generations of population eight: **1,024 proposals
per arm**, four arms total. Every proposal receives the same exact local RGB
fit and existing three-step position/RGB refinement (radius 4 px, differences
2 px). Old geometry and colors remain fallbacks.

Control samples local CMA proposals at sigma 0.005. The replacement arm replaces
half of each population with independently seeded new triangles. Their centers
come from uniform unit-ball points weighted by a point-support quadratic RGB
gain estimate across the four residual images; their world sizes range from
0.006 to 0.12. Actual candidates are scored by the unchanged hard-render gain,
not the point-support estimate. All refined positions enter the CMA update.

Each arm ends with the same global RGB refit attempt, capped at eight outer
iterations to keep this pilot short. A global result is retained only if its
actual loss does not rise. This cap is not a claim of global RGB convergence.
The reported values are independently reconstructed physical renders, with
monotonic history, bounds and winding checked. A unit check independently
confirms the marginal-removal formula and proposal constraints.

## Results and decision

| Seed | Local control loss | Replacement-arm loss | New-triangle final winners |
|---|---:|---:|---:|
| 23 | 0.0524258101293 | 0.0524288305174 | 0 / 64 |
| 47 | 0.0524287534954 | 0.0524296290009 | 0 / 64 |

Loss improvements relative to the common start are only 0.01696% / 0.01134%
for controls and 0.01120% / 0.00967% for replacement arms. The control wins
both seeds. No externally seeded candidate was selected as a final winner;
the tiny gains came from parent RGB refits and local proposals. Maximum world
movement in the replacement arms was 0.02124 / 0.04019, with no visually useful
structural change. Actual comparison images show no material visual difference.

The four arms took about **181 seconds combined**, excluding shared setup.
No long run remains active. The specific cheap replacement proposal mechanism
did not establish value, so **no Studio checkbox was added**. This is a negative
bounded pilot, not proof that all budget-reallocation, dictionary or globally
color-coupled replacement methods fail. More search or a different proposal
mechanism could change the outcome, but neither was run silently.

Artifacts: `runs/replacement-pilot/protocol.json`, `results.json`, per-arm
checkpoints/OBJ/progress/global fits, `comparison.png`, and native-size
`compare-portrait.png`, `compare-spacecraft.png`, `compare-dragon.png`,
`compare-island.png`. Those last pairs show the numerical best arm (a control),
with explicit captions; the five-row comparison shows every arm.

Reproduce in a new folder:

```powershell
.venv\Scripts\python.exe -m lisa2.replacement_trial --output runs/new-replacement-pilot
.venv\Scripts\python.exe -m tests.check_replacement
```
