# Free Blender add-on + original demo files

VRAM Fixer 1.1.0 is free and open source. Tested in Blender 5.3.0 / Cycles / OptiX on an RTX 4060 Ti 8GB.

## Downloads

- **vram_fixer-1.1.0.zip:** install this ZIP through Blender Preferences → Add-ons → Install from Disk. GitHub's automatically generated source ZIP is not the installer.
- **Burning-Room-BEFORE.blend:** packed original 3D demo, ready to Analyze/Fix. About 377 MiB.
- **Burning-Room-AFTER.blend:** packed optimized demo with Restore records. About 405 MiB. Originals remain, so the file is larger even though render texture allocation is lower.
- **reddit-media-kit.zip:** before/after GIFs, MP4s, image cards, ready-to-copy Reddit drafts and measurements.
- **burning-room-renders-16bit.zip:** full-resolution clean 16-bit PNGs, detail crops, comparison and measured results for your own design/editing.

## What the evidence shows

The burning-room demo reduced Cycles texture allocation by 60.6% and evaluated mesh triangles by 42.1%, with the protected hero retained. Its render-time difference was small and core preparation took 13.32s.

A separate 12K-texture pressure test on the 8GB card reduced Cycles-reported allocation from 13.59 to 4.21 GiB, including host RAM. BEFORE already rendered via system RAM. Hard-OOM recovery is not proven or guaranteed; the 16K test hit a host-RAM guard during both paths.

See the repository's benchmark notes for raw numbers, settings, overhead and limitations. Start with Careful, preview the plan, keep a backup and compare a render. Restore before changing camera/frame/resolution and optimizing again.
