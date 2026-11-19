"""Seeded, original material bakes. No downloaded art or hidden ballast textures."""
from pathlib import Path
import json
import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent / 'textures'
OUT.mkdir(exist_ok=True)
RECIPES = [
    ('green_plaster', 8192, (101, 119, 83), 'plaster', 11),
    ('floor_oak', 8192, (110, 68, 39), 'wood', 21),
    ('table_oak', 8192, (156, 104, 59), 'wood', 31),
    ('shelf_walnut', 4096, (88, 53, 33), 'wood', 41),
    ('chair_weave', 4096, (155, 66, 39), 'fabric', 51),
    ('book_leather', 4096, (149, 119, 81), 'leather', 61),
    ('aged_paper', 4096, (201, 183, 139), 'paper', 71),
]
manifest = []
for name, edge, color, kind, seed in RECIPES:
    base_path = OUT / (name + '_color.png')
    rough_path = OUT / (name + '_rough.png')
    if base_path.exists() and rough_path.exists():
        print('EXISTS', name, flush=True)
        manifest.append({'name': name, 'edge': edge, 'kind': kind, 'seed': seed,
                         'base': str(base_path), 'rough': str(rough_path)})
        continue
    rng = np.random.default_rng(seed)
    rgb = np.empty((edge, edge, 3), dtype=np.uint8)
    rough = np.empty((edge, edge), dtype=np.uint8)
    small = Image.fromarray(rng.integers(0, 256, (128, 128), dtype=np.uint8))
    cloud = np.asarray(small.resize((edge, edge), Image.Resampling.BICUBIC))
    broad = np.asarray(Image.fromarray(rng.integers(0, 256, (16, 16), dtype=np.uint8)).resize((edge, edge), Image.Resampling.BICUBIC))
    x = np.linspace(0, 1, edge, dtype=np.float32)[None, :]
    for start in range(0, edge, 128):
        end = min(start + 128, edge)
        y = np.arange(start, end, dtype=np.float32)[:, None] / edge
        c = cloud[start:end].astype(np.float32) / 255
        b = broad[start:end].astype(np.float32) / 255
        fine = rng.normal(0, 1, (end-start, edge)).astype(np.float32)
        if kind == 'wood':
            bend = .035*np.sin(x*15) + .013*np.sin(x*43 + y*8)
            grain = np.sin((y + bend)*930 + c*5)
            veins = np.maximum(0, np.sin((y + bend)*220 + b*7))**12
            tone = (c-.5)*19 + (b-.5)*14 + grain*3 - veins*16 + fine*1.8
            r = 145 + c*37 + fine*3 + veins*12
        elif kind == 'plaster':
            fissure = np.maximum(0, np.sin(x*113 + np.sin(y*31)*3) * np.sin(y*161 + c*4) - .93)*90
            soot = np.clip((y-.56)*1.8 + (b-.5)*.8, 0, .78)
            tone = (c-.5)*24 + (b-.5)*20 + fine*3.5 - fissure - soot*35
            r = 192 + c*40 + fine*4
        elif kind == 'fabric':
            weave = np.sin(x*edge*1.6) * np.sin(y*edge*1.6)
            tone = (c-.5)*12 + (b-.5)*14 + fine*3 + weave*6
            r = 219 + c*24 + fine*2
        elif kind == 'leather':
            pores = np.maximum(0, fine-1)*6
            tone = (c-.5)*17 + (b-.5)*12 - pores + fine
            r = 171 + c*42 + pores
        else:
            fibers = np.sin(x*4200 + c*3)*2
            tone = (c-.5)*7 + (b-.5)*12 + fine*2 + fibers
            r = 218 + c*29 + fine*2
        for channel, value in enumerate(color):
            rgb[start:end, :, channel] = np.clip(value + tone*(1 if channel != 2 else .75), 0, 255).astype(np.uint8)
        rough[start:end] = np.clip(r, 35, 250).astype(np.uint8)
    Image.fromarray(rgb).save(base_path, compress_level=3)
    Image.fromarray(rough).save(rough_path, compress_level=3)
    manifest.append({'name': name, 'edge': edge, 'kind': kind, 'seed': seed,
                     'base': str(base_path), 'rough': str(rough_path)})
    del rgb, rough, cloud, broad
    print('BAKED', name, edge, flush=True)
(OUT.parent / 'texture_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('TEXTURES_READY', len(manifest)*2)
