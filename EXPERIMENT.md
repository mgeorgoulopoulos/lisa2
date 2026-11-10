# Completed proof of concept

Target hardware: Pentium II 333 MHz, Riva TNT; software rasterization at 640x480.

Four procedural targets: orbit, eye, sun, lotus. Shared amber chromaticity,
black backgrounds. One 768-triangle mesh, 2304 vertices. Four tetrahedral
perspective cameras, 42-degree vertical FOV. No view-dependent materials.

DEAP CMA-ES optimized geometry one triangle at a time with an analytical
nonnegative RGB fit. The successful stages were:

- 128x96: 3 rounds, 8 generations per block, population 16.
- 320x240: warm-start from stage 1, 4 rounds, 10 generations, population 16.
- 640x480: warm-start from stage 2, 4 rounds, 10 generations, population 16.

All use seed 23 and 768 triangles. Run configs and histories are in the
respective checkpoints; do not compare numerical fitness across resolutions.
The final stage took approximately 68 seconds on the current host, including
checkpointing and plotting preparation overhead, not on the target retro PC.

Final independently recomputed results:

```json
{
  "resolution": [
    640,
    480
  ],
  "verified_fitness": 0.9765784870889969,
  "rgb8_fitness": 0.9765039325020967,
  "pixel_blends_per_key_view": [
    240188,
    221540,
    184719,
    215043
  ],
  "max_overlap_per_key_view": [
    16,
    16,
    17,
    18
  ],
  "geometry_rgb8_bytes": 29952,
  "monotonic_history": true,
  "cpu_only": true,
  "retro_machine_benchmarked": false
}
```

The score means a 97.66% reduction of the specified weighted squared error
relative to drawing nothing. It does not mean 97.66% perceptual similarity.
8-bit flat-color quantization changes that score only slightly (see above).
There are still faint stray triangles and noise around the desired symbols.
The actual images and transitions should decide whether to continue.

Measured reference raster time on the current host was approximately 12.8 ms
per key view at 640x480. This includes the Python/Numba reference path and image
conversion. It is not a Pentium II benchmark or a DOS frame-rate promise.
The four key views require roughly 185kâ€“240k triangle-pixel additive updates;
intermediate views have not been exhaustively profiled.

Files to inspect locally: runs/dos640/comparison.png, orbit.gif, fitness.png,
model.obj, model.mtl and best.npz. The preview window uses exactly this mesh
and the same software rasterization, with spherical orientation interpolation.

Full editing-app work is deferred until this visual proof is accepted. The
current prototype already includes a small fitness/control panel and a basic
four-file drop path, but that input workflow has not had manual UI acceptance.
