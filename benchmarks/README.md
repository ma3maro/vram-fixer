# What the comparisons measure

These are two different scenes. Their pictures and figures must not be mixed.

## Burning-room demo

The original, downloadable room uses intentionally oversized 8K/4K procedural bakes and detailed small props. Strong changed 10 images and added 22 non-applied Decimate modifiers. Camera, lights, exposure, seed, resolution and render settings were checked identical. All 262 protected objects were unchanged. Reopening AFTER and restoring matched the BEFORE state.

Blender 5.3.0, RTX 4060 Ti 8GB, OptiX GPU only, 1920×1280, 192 max samples, adaptive threshold .018, denoising and identical optical-glow postprocess. Two fresh processes per version.

| Metric | Before | After |
|---|---:|---:|
| Native Cycles image allocation | 2048.00 MiB | 807.25 MiB |
| Native Cycles reported peak allocation | 2712.94 MiB | 1455.91 MiB |
| Evaluated mesh triangles, curves/text excluded | 663,364 | 384,224 |
| Render call average | 39.20s | 37.81s |
| Core preparation | — | 13.32s |

Texture allocation fell 60.58%; mesh triangle count fell 42.08%. These are not equivalent to 60.58% less total VRAM. The sampled global GPU peak averaged 5219 → 3953 MiB, but includes Windows/apps, changing desktop use and sampling uncertainty. The small 3.54% timing difference over two runs is not a general speedup claim.

The complete optimization subprocess took 16.52s, including startup/load/checks/save/shutdown. Packed file size grew from about 377 to 405 MiB because original images remain for Restore.

[JSON and individual runs](burning-room.json) · [CSV](burning-room.csv) · [Full definitions](burning-room.md) · [Native excerpts](raw/)

## 8 GB GPU / 12K texture pressure test

A separate copy of the author's avocado scene had ten actively rendered textures enlarged to 12K. No unused image nodes or invisible dummy allocation were counted. Camera, shading links and object count remained in place.

Blender 5.3.0, RTX 4060 Ti 8GB, OptiX GPU only, 1080×1920, 32 fixed samples, denoising on, persistent data/compositor/sequencer off in both variants. These are not the burning-room render settings.

Repeat-run figures shown in the promo:

| Metric | Before | After |
|---|---:|---:|
| Cycles-reported peak allocation | 13.59 GiB | 4.21 GiB |
| Render call | 19.86s | 7.47s |
| Analysis + application | — | 53.37s |

The first pair was similar: 19.81s → 7.74s. The allocation reduction was about 69%. Saving and reopening the optimized scene rendered in 7.78s with substantially lower process RAM than during preparation.

**BEFORE was already renderable using system RAM.** Cycles allocation can include mapped host RAM; it is not a claim that an 8 GB card physically held 13.59 GiB of dedicated VRAM. GPU-only rendering was selected; using host memory for GPU allocations is not the same as CPU rendering fallback.

At 16K, the unoptimized render exceeded a 20.5 GiB process-RAM safety guard. The optimized path exceeded the same guard during application, before rendering. Neither produced a native GPU-OOM error before the watchdog stopped it. **Hard-OOM rescue was not proven.** The test found a genuine host-RAM limitation in the current full-size-copy workflow.

[Pressure-test JSON](pressure-test.json) · [Native excerpts](raw/pressure-before.txt) · [After excerpts](raw/pressure-after.txt)

## Measurement boundaries

- `render_seconds` measures synchronization, rendering, denoising and image output. It excludes analysis/application and file loading.
- Native Cycles allocation reports do not include every driver/compositor allocation and can include mapped host data. They are not physical per-process VRAM counters.
- nvidia-smi was sampled; global totals include the desktop and other apps. WDDM did not provide reliable per-process dedicated-VRAM readings.
- Watchdog aborts are not native OOM errors. No driver fallback policy or device-memory cap was altered to manufacture a failure.
- The two sides were not selectively recolored, blurred or sharpened. Small nonzero image differences exist; these tests do not establish zero quality loss.
- Source scene/third-party libraries for the avocado test are not redistributed. The original authored burning-room files are in Releases.
