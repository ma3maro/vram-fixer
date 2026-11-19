"""Deterministic Cycles CPU comparison on a disposable test scene."""
import sys
import json
from array import array
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_integration import bpy, fixture, check, vram_fixer, analysis, operations, Vector, ROOT

vram_fixer.register()
scene, hero, small, plane, image, material, node = fixture()
scene.render.resolution_x = scene.render.resolution_y = 512
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = False
scene.cycles.seed = 17
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.world = bpy.data.worlds.new('Test world')
scene.world.color = (.25, .25, .25)
pixels = array('f')
for y in range(1024):
    for x in range(1024):
        checker = ((x // 32) + (y // 32)) % 2
        pixels.extend((.15 + checker*.6, .3 + checker*.3, .1, 1))
image.pixels.foreach_set(pixels)
del pixels
bpy.ops.object.light_add(type='AREA', location=(0, 3, 7))
light = bpy.context.object
light.data.energy = 1500
light.data.shape = 'DISK'
light.data.size = 5
light.rotation_euler = (-light.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -2))
bpy.context.object.name = 'Large backdrop'
for poly in small.data.polygons:
    poly.use_smooth = True
out = ROOT / 'verification'
out.mkdir(exist_ok=True)


def render(name):
    path = out / (name + '.png')
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    loaded = bpy.data.images.load(str(path), check_existing=False)
    data = array('f', [0]) * len(loaded.pixels)
    loaded.pixels.foreach_get(data)
    bpy.data.images.remove(loaded)
    return data


baseline = render('before')
plan = analysis.analyze(bpy.context)
textures, meshes = operations.apply(bpy.context, plan)
check(textures > 0 and meshes > 0, 'Comparison must exercise both optimizations')
optimized = render('after')
checks = [{'name': r.object.name, 'sampled_error_px': r.error_pixels, 'samples': r.samples,
           'retention': r.object.modifiers[-1].ratio} for r in scene.vram_fixer.mesh_changes]
operations.write_report(plan, applied=True)
(out / 'report.txt').write_text(plan['report'], encoding='utf-8')
operations.restore(bpy.context)
restored = render('restored')
differences = sorted(abs(a-b) for i, (a, b) in enumerate(zip(baseline, optimized)) if i % 4 != 3)
mae = sum(differences) / len(differences)
restore_max = max(abs(a-b) for a, b in zip(baseline, restored))
results = {'blender': bpy.app.version_string, 'renderer': 'Cycles CPU', 'resolution': [512, 512], 'samples': 32,
           'textures_reduced': textures, 'meshes_decimated': meshes,
           'estimated_texture_mib_saved': plan['saved']/1048576,
           'display_referred_rgb_mae': mae,
           'display_referred_rgb_p99_error': differences[int(len(differences)*.99)],
           'restore_max_channel_error': restore_max, 'mesh_checks': checks,
           'note': 'Synthetic fixture, not the user\'s avocado scene; not a GPU VRAM benchmark.'}
(out / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
check(mae < .01, f'Unexpected render drift: {mae}')
check(restore_max < .001, f'Restore render differs: {restore_max}')
print('VRAM_FIXER_RENDER_PASS', json.dumps(results))
vram_fixer.unregister()
