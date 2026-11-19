# Pressure-test title

8 GB GPU, 13.59 → 4.21 GiB of Cycles allocation. I made the optimizer free, with real before/after tests.

# Upload

Use `media/pressure-comparison.mp4`, or `media/03-8gb-pressure-test.png` for an image post.

# Post body

The images are the actual before/after renders, not a fake crash screen.

I pushed a copy of my scene with ten render-used textures enlarged to 12K. On an **8 GB RTX 4060 Ti**, Cycles reported **13.59 GiB** of allocation before optimization and **4.21 GiB** afterward. The before render was using system RAM. This figure includes host allocation; it's not a claim that an 8 GB card physically held 13.59 GiB in VRAM.

Repeat render calls: **19.86s before, 7.47s after**, with **53.37s of analysis/application first**. So a single optimize-and-render run was slower overall; repeated renders benefited in this test.

The tool is **VRAM Fixer**. It uses the active camera and a reference object to budget textures and meshes, lets you protect objects, follows nested materials, and keeps originals for Restore.

**Completely free. Download + source + demo scenes:**
https://github.com/ma3maro/vram-fixer

I also tried 16K. Both the original render and optimization hit the same system-RAM safety guard, so I haven't proved a hard-OOM rescue. This reduces the scene's demand; it doesn't make every scene fit every GPU. Blender 5.3 / OptiX, 1080×1920, 32 fixed samples for this pressure test. Full figures are in the repo.
