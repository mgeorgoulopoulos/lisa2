# Distinct colorful entities

The second visual experiment changes only input images and run parameters.
All application/optimizer/renderer source remains exactly at commit [local snapshot].
The mesh still has 768 triangles, and uses the same four tetrahedral perspective
cameras, 640x480 software rasterization and additive blending over black.

The user rejected the first proposed colorful set because all four objects were
radial abstract sculptures. Those drafts were not evolved. The replacement set
contains a woman's portrait, a diagonal spacecraft, a dragon's head, and a
floating mountain island with a waterfall. Images were generated with built-in
imagegen, then reframed with that same tool to add black margins. The final
assets and exact generation/framing prompts are in assets/distinct/ and
assets/distinct/imagegen-prompts.json. No extra mesh detail or post-processing
was introduced.

Three independent run folders preserve the progression: distinct128,
distinct320 and distinct640. Each used six rounds, twelve generations per
triangle block, population sixteen, seed 23. Higher resolutions warm-started
from the preceding mesh. The completed final result and a local preview
shortcut are in runs/distinct640/. The original monochrome run is preserved.

Independent validation:

```json
{
  "source_code_unchanged": true,
  "targets": [
    {
      "path": "assets/distinct/1_portrait.png",
      "sha256": "2c8cba4d9bdc270ac5e200178acf5dc01074c237edca5e1ed194397f27e3addc"
    },
    {
      "path": "assets/distinct/2_spacecraft.png",
      "sha256": "044a3b1de9b6d435c5ac77457e84ccc00e588e56d3b7dd1f0d5304960c41b0c0"
    },
    {
      "path": "assets/distinct/3_dragon.png",
      "sha256": "a61ec7de73ce37d2496c294a845c6886f1068de1d23ba5dcfb8f80206f695476"
    },
    {
      "path": "assets/distinct/4_island.png",
      "sha256": "7699624fdc3829933637f88e0bfbafdc1752b4d0d62638c8eac93e7532eb738f"
    }
  ],
  "fitness_independently_verified": 0.9668453255276779,
  "triangle_count": 768,
  "resolution": [
    640,
    480
  ]
}
```

Fitness is a reduction in weighted squared RGB error from an all-black
baseline, not a perceptual similarity percentage. All four subjects are
recognizable, but there are still stray additive triangles and some blurred
features. The actual comparison and animation are the relevant visual evidence:
runs/distinct640/comparison.png and runs/distinct640/orbit.gif.

The preview shortcut selects this run without changing the default launcher or
any source. Keys 1-4 retain smooth transitions. The saved OBJ/MTL use exactly the
same evolved mesh; conventional opaque viewers will not reproduce the blend.
