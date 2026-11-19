"""Run in factory-startup Blender; never touches an existing user scene."""
import bpy
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import vram_fixer
from vram_fixer import analysis, operations


def check(value, message):
    if not value:
        raise AssertionError(message)


def fixture():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    bpy.ops.object.camera_add(location=(0, 0, 10))
    scene.camera = bpy.context.object
    scene.camera.data.type = 'ORTHO'
    scene.camera.data.ortho_scale = 10
    bpy.ops.mesh.primitive_cube_add(size=3, location=(-2, 0, 0))
    hero = bpy.context.object
    hero.name = 'Reference'
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=.2, location=(1, 0, 0))
    small = bpy.context.object
    small.name = 'Small dense sphere'
    bpy.ops.mesh.primitive_plane_add(size=.5, location=(2, 0, 0))
    plane = bpy.context.object
    plane.name = 'Small textured plane'
    image = bpy.data.images.new('Original texture', width=1024, height=1024)
    image.generated_color = (.2, .4, .7, 1)
    # Force generation before copy; checks later detect black copied buffers.
    image.pixels[0:4] = (.2, .4, .7, 1)
    material = bpy.data.materials.new('Shared test material')
    material.use_nodes = True
    node = material.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = image
    material.node_tree.links.new(node.outputs['Color'], material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    plane.data.materials.append(material)
    scene.vram_fixer.reference = hero
    bpy.context.view_layer.update()
    return scene, hero, small, plane, image, material, node


def run():
    vram_fixer.register()
    scene, hero, small, plane, image, mat, node = fixture()
    plan = analysis.analyze(bpy.context)
    check(any(x['object'] == small for x in plan['meshes']), 'Dense small object must be decimated')
    check(any(x['image'] == image for x in plan['images']), 'Small UV texture must be reduced')
    check(not any(x['object'] == hero for x in plan['meshes']), 'Reference must be protected')
    check(tuple(image.size) == (1024, 1024), 'Analyze must be read-only')
    operations.apply(bpy.context, plan)
    check(node.image != image, 'Optimized copy must replace node image')
    check(max(node.image.size) < 1024, 'Texture copy must shrink')
    check(abs(node.image.pixels[0] - .2) < .03, 'Copy must retain actual pixels')
    check(tuple(image.size) == (1024, 1024), 'Original must remain intact')
    check(len(small.modifiers) == 1 and small.modifiers[0].type == 'DECIMATE', 'Non-applied decimate required')
    check(scene.vram_fixer.mesh_changes[0].error_pixels <= .75, 'Careful preset must validate sampled surface error below .75 pixels')
    check(scene.vram_fixer.mesh_changes[0].samples > 0, 'Geometric error must be measured, not just estimated')
    check(len(small.data.polygons) > 7000, 'Original geometry must remain intact')
    try:
        operations.apply(bpy.context, plan)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Repeated apply must be rejected')
    # Disabling/re-enabling must not silently discard the persisted session.
    vram_fixer.unregister()
    vram_fixer.register()
    check(scene.vram_fixer.active_session and len(scene.vram_fixer.image_changes) == 1,
          'Session must survive disabling and re-enabling the add-on')
    # Persistent restore, not a module-global cache.
    save = ROOT / 'tests' / 'session.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(save))
    bpy.ops.wm.open_mainfile(filepath=str(save))
    scene = bpy.context.scene
    small = bpy.data.objects['Small dense sphere']
    image = bpy.data.images['Original texture']
    mat = bpy.data.materials['Shared test material']
    node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
    operations.restore(bpy.context)
    check(node.image == image, 'Restore must work after save/reload')
    check(not small.modifiers, 'Restore must remove only owned modifier')
    # Protected shared image must never be changed through an unprotected consumer.
    scene.vram_fixer.protected.add().object = bpy.data.objects['Reference']
    bpy.data.objects['Reference'].data.materials.append(mat)
    plan = analysis.analyze(bpy.context)
    check(not plan['images'], 'Protected shared texture must be skipped globally')
    # Off-camera objects can appear in reflections: do not optimize them.
    small.location.x = 30
    bpy.context.view_layer.update()
    plan = analysis.analyze(bpy.context)
    check(not any(x['object'] == small for x in plan['meshes']), 'Off-camera mesh must remain intact')
    # No camera must fail before modifying anything.
    scene.camera = None
    try:
        analysis.analyze(bpy.context)
    except ValueError:
        pass
    else:
        raise AssertionError('Missing camera must fail closed')
    vram_fixer.unregister()
    vram_fixer.register()
    vram_fixer.unregister()
    print('VRAM_FIXER_INTEGRATION_PASS')


if __name__ == '__main__':
    run()
