# Recommended title

I made a free Cycles VRAM optimizer. Same burning room, 60.6% lower texture allocation. Source + demo included.

# Upload first

Use `media/room-comparison.mp4` as the main Reddit video. It is a comparison of real rendered stills, not an animated fire simulation. For a gallery, upload `01-launch.png`, `02-burning-room-before-after.png`, then `03-8gb-pressure-test.png`.

# Post body

The room can be on fire. The texture budget doesn't have to be.

I made **VRAM Fixer**, a completely free Blender add-on for Cycles. Pick a medium-sized/focal object as a size reference, protect anything you don't want touched, and let it reduce oversized textures and small, dense meshes. There's a preview and a Restore button.

The burning-room test in the clip changed:

- Cycles texture allocation: **2048 → 807 MiB**.
- Evaluated mesh triangles: **663,364 → 384,224**.
- Render average: **39.20 → 37.81 seconds**, plus **13.32 seconds** of one-time core preparation.

I also tested a deliberately oversized 12K-texture scene on my **8 GB RTX 4060 Ti**. Cycles-reported allocation fell from **13.59 to 4.21 GiB**. That before scene was still rendering through system RAM; I'm not claiming the tool recovered a failed render or magically added VRAM. That test took another 53.37s to analyze/apply, before the faster render.

**Free download, source, editable demo scenes and the actual measurements:**
https://github.com/ma3maro/vram-fixer

Tested in Blender 5.3 / OptiX. Texture allocation isn't total dedicated VRAM, and the demo assets were intentionally oversized. This is mainly about reducing memory pressure, not promising faster renders in every scene. Very large images can still exhaust system RAM during processing.

If you try it, I'd love a before/after and your GPU model. Bug reports and ugly edge cases welcome.
