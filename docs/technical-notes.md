# How the budgets work

The reference is the larger projected render-pixel dimension of the chosen mesh's evaluated bounding box. Importance rises continuously with `(object_span / reference_span)^1.35`, capped at one. The chosen reference is protected by default; other objects have a separate exclusion list. Camera shift, pixel aspect, resolution percentage, crop boundaries and near-plane handling are included.

## Textures

The analyzer follows active Cycles outputs upstream through shader-processing nodes and nested groups. Group instances retain their own coordinate-input context. It resolves active/named UVs, reroutes and static Point/Texture/Vector Mapping chains, then examines evaluated UV triangles. A screen-to-UV derivative and its largest singular value estimate texel demand, with aspect-ratio and perspective headroom.

Demand is weighted by projected surface coverage. Careful uses the 99.9th percentile; Balanced 99%; Strong 97.5%. Base sampling factors are 2.0, 1.5 and 1.1, adjusted by importance and clamped to at least one. Data maps get 1.25× extra headroom. Each consumer contributes; the highest consumer demand wins. Targets round upward to a 256-pixel long-edge increment, preserving image aspect ratio and never enlarging an image.

Safe images are copied, resized using Blender's filtered image scaling, and packed. Actual edited pixel buffers are explicitly copied. Originals remain available for Restore. Embedded material trees use material-owner records; standalone shader groups use node-tree pointers. Persistent node tokens allow renamed nodes to restore.

## Meshes

Screen area, a perimeter floor, a 512-triangle floor and reference-relative retention produce the initial ratio. Preset minimum retention is 35% / 16% / 8%, rising with importance; reference-sized geometry is preserved.

A non-applied Collapse Decimate modifier is tested against the original evaluated mesh using bidirectional BVH nearest-surface samples: up to 4,096 vertices and 2,048 face centers per surface. World distances are converted to render-pixel units. Limits are .75 / 1.25 / 2 pixels; the ratio backs off toward one for up to five attempts. Negligible or unsuccessful reductions are removed.

These are sampled checks and quality heuristics, not mathematical maximum-error bounds. Details and deliberate exclusions are in [limitations](limitations.md).

## Reproduction

`python -m unittest discover -s tests -v` runs the dependency-free policy tests. Blender fixture tests in `tests/` cover persistence, shared resources, rollback, nested groups, instance contexts and actual operators.

To rebuild the original room, install NumPy/Pillow in your system Python, run `python demo/bake_textures.py`, then execute `demo/build_scene.py` in Blender. `demo/run_job.py` is the monitored Windows test launcher; set `BLENDER_BIN` for another Blender path. The before/after packed demo files are easier to inspect directly from Releases.
