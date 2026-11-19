# Measured before/after results

Blender 5.3.0 · RTX 4060 Ti 8GB · OptiX GPU only · 1920×1280 · 192 max samples · adaptive threshold .018 · denoising on · Strong preset.
Two fresh-process runs per version; camera, lighting, exposure, seed, resolution and render settings checked identical. No product-code modifications.

| Measurement | Before | After | Reduction |
|---|---:|---:|---:|
| Cycles image/texture allocation | 2048.00 MiB | 807.25 MiB | 60.58% |
| Cycles reported peak allocation | 2712.94 MiB | 1455.91 MiB | 46.33% |
| Sampled global GPU peak, mean of two runs | 5219.00 MiB | 3953.00 MiB | 24.26% |
| Evaluated mesh triangles | 663,364 | 384,224 | 42.08% |
| Cycles geometry memory report | 13.99 MiB | 9.47 MiB | 32.34% |
| Render call, mean of two fresh-process runs | 39.20 seconds | 37.81 seconds | 3.54% |
| Sampled process RSS peak, mean of two runs | 6107.83 MiB | 5043.69 MiB | 17.42% |
| Packed Blender file size | 376.75 MiB | 404.86 MiB | -7.46% |

## Time overhead
- Analysis: 3.99s.
- Apply + mesh validation/counting + save: 9.33s.
- Combined measured core preparation: 13.32s.
- Complete optimization subprocess including startup/load/checks/shutdown: 16.52s.
- The before/after render timings exclude preparation. A single optimize-and-render workflow takes longer overall in this demo.
- Render-time difference is small (~3.5% over two runs), not strong evidence of a general performance improvement. Memory reduction is the primary demonstrated benefit.

## Definitions and limitations
- **Cycles image/texture allocation:** Native Cycles image allocation report; not total dedicated GPU VRAM.
- **Cycles reported peak allocation:** Native Cycles allocation report; can include mapped host memory and excludes driver/compositor overhead.
- **Sampled global GPU peak, mean of two runs:** nvidia-smi sampled global total, including Windows/apps; not isolated per-process VRAM. Desktop usage varied between runs.
- **Evaluated mesh triangles:** Meshes only. Native curves/text are excluded. Source geometry remains intact; modifiers are reversible.
- **Cycles geometry memory report:** Native Cycles geometry statistics, not total scene/driver memory.
- **Render call, mean of two fresh-process runs:** Includes synchronization, rendering, denoising, identical optical-glow compositor and PNG output. Excludes optimization; only two runs, small timing difference.
- **Sampled process RSS peak, mean of two runs:** Freshly opened before/after scenes; does not include the separate optimization-process peak.
- **Packed Blender file size:** Negative reduction means growth. After retains originals for Restore; do not claim smaller files.

- Normalized display-RGB mean absolute pixel difference: 0.00027809; small, nonzero differences exist. Do not claim zero quality loss.
- Oversized source bakes and dense small props are deliberate demo choices. No guarantee every customer scene achieves these percentages.
- Protected mascot, cup, flames and smoke: 262 objects checked unchanged. AFTER Restore was tested after reopening; it matched BEFORE object transforms, source meshes, lights, image dimensions/colorspaces and settings.
- Scene is a fully editable still composition. Flames are sculpted 3D emission/transparency geometry; smoke uses real volume shading. It is not a baked Mantaflow simulation or an animation package.
- The AFTER .blend is larger because it preserves originals for Restore. No file-size reduction is advertised.
