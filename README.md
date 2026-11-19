# VRAM Fixer

A **free Blender 5.3 add-on for Cycles** that reduces oversized textures and small, dense meshes while protecting the objects you care about.

## [Download the add-on](https://github.com/ma3maro/vram-fixer/releases/latest/download/vram_fixer-1.1.0.zip)

## Install and use

1. Download `vram_fixer-1.1.0.zip` above. Use **Preferences → Add-ons → Install from Disk** in Blender.
2. Open **3D View → N → VRAM Fixer**.
3. Select a medium-sized/focal mesh and click **Use Active Object as Reference**.
4. Add anything that must stay untouched to **Never Touch**.
5. Choose **Textures**, **Meshes**, or both. Start with **Careful**, preview with **Analyze**, then click **Fix VRAM**.
6. Use **Restore Originals** to undo the optimization, including after saving and reopening.

Textures can be inside ramps, mixes and nested shader groups. Mesh reduction uses non-applied Decimate modifiers with sampled geometric checks. Source textures and meshes remain available for restoration.

**Keep a backup and compare a render.** Optimization is specific to the current camera/frame. It can require extra system RAM; faster renders and OOM recovery are not guaranteed. Restore before changing the camera, frame or resolution and optimizing again.

Free and open source under [GPL-3.0-or-later](vram_fixer/LICENSE). No signup, API keys or cloud service.
