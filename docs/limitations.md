# Known limitations

This is a camera/frame-specific reduction tool. It does not add VRAM, guarantee an OOM recovery, guarantee faster renders, or prove zero visual loss.

- Restore before changing camera, frame, resolution, exclusions or preset and optimizing again. Transform animation being accepted at the current frame is not animation-wide safety.
- Full-size pixel copies, float staging and retained original images can require substantial **system RAM**. The 16K stress test hit a 20.5 GiB process-RAM safety guard during application, before rendering. Originals can also increase `.blend` size.
- Cycles may retain GPU caches. Fresh render processes were used in the supplied tests. Windows/Cycles can spill allocations to system RAM instead of producing a hard GPU OOM.
- Explicitly protected resources and images shared with them are preserved. Off-camera consumers, instances, foreign-scene dependencies, linked libraries and unresolved coordinates can intentionally prevent a reduction.
- Texture routing supports UV maps, static affine Mapping nodes, reroutes and nested group interfaces. Arbitrary nonlinear coordinate math, generated/object/triplanar projection, linked trees, UDIMs, image sequences and movies are not automatically reduced.
- UV scans above 100,000 evaluated triangles fail closed. Texture analysis uses the viewport-evaluated surface, not an exact renderer-only geometry simulation.
- Geometry checks are sampled nearest-surface tests. They do not bound every silhouette feature, UV interpolation change, reflection or normal-map highlight. Unsupported topology-sensitive stacks, displacement, viewport/render mismatches, constraints/weights, shape keys and very large evaluated meshes remain excluded.
- Coverage-weighted UV percentiles can soften small details in the excluded tail. Protect labels and critical small features.
- Restore needs the original image datablocks and non-applied owned modifiers. Deleting originals or manually applying a modifier can make exact restoration impossible.

See the native log excerpts and [benchmark report](../benchmarks/README.md). The tests use intentionally oversized assets to demonstrate a controlled memory-pressure case, not typical results for every project.
