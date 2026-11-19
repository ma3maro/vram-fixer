"""Behavioral safety cases against actual Blender datablocks and evaluated geometry."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_integration import bpy, fixture, check, vram_fixer, analysis, operations


def blocked(plan, image):
    return not any(i['image'] == image for i in plan['images'])


def run():
    vram_fixer.register()
    count = 0
    def case(name):
        nonlocal count
        count += 1
        print('PASS', name)

    scene, hero, small, plane, image, mat, node = fixture()
    # Protecting any consumer, even one with no projected surface, blocks the image.
    scene.vram_fixer.protected.add().object = plane
    plan = analysis.analyze(bpy.context)
    check(blocked(plan, image), 'Explicitly protected texture changed')
    case('explicit protection')

    scene, hero, small, plane, image, mat, node = fixture()
    world = bpy.data.worlds.new('World consumer')
    world.use_nodes = True
    env = world.node_tree.nodes.new('ShaderNodeTexEnvironment')
    env.image = image
    check(blocked(analysis.analyze(bpy.context), image), 'World image changed')
    case('world image dependency')

    scene, hero, small, plane, image, mat, node = fixture()
    mapping = mat.node_tree.nodes.new('ShaderNodeMapping')
    mat.node_tree.links.new(mapping.outputs['Vector'], node.inputs['Vector'])
    check(blocked(analysis.analyze(bpy.context), image), 'Complex UV mapping guessed')
    case('mapping fails closed')

    scene, hero, small, plane, image, mat, node = fixture()
    coords = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    mapping = mat.node_tree.nodes.new('ShaderNodeMapping')
    mat.node_tree.links.new(coords.outputs['UV'], mapping.inputs['Vector'])
    mat.node_tree.links.new(mapping.outputs['Vector'], node.inputs['Vector'])
    check(not blocked(analysis.analyze(bpy.context), image), 'Static UV mapping should be measurable')
    mapping.inputs['Scale'].default_value = (.01, .01, 1)
    check(blocked(analysis.analyze(bpy.context), image), 'UV mapping scale must change texel demand')
    case('static UV mapping derivatives')

    scene, hero, small, plane, image, mat, node = fixture()
    # A tiny UV island needs a high-resolution texture despite a tiny object.
    for loop in plane.data.uv_layers.active.data:
        loop.uv *= .01
    bpy.context.view_layer.update()
    check(blocked(analysis.analyze(bpy.context), image), 'Tiny UV island undersampled')
    case('UV island demand overrides screen size')

    scene, hero, small, plane, image, mat, node = fixture()
    scene.render.resolution_percentage = 25
    low = analysis.analyze(bpy.context)
    scene.render.resolution_percentage = 100
    high = analysis.analyze(bpy.context)
    lratio = next(m['ratio'] for m in low['meshes'] if m['object'] == small)
    hratio = next(m['ratio'] for m in high['meshes'] if m['object'] == small)
    check(hratio >= lratio, 'Higher resolution must not decimate more')
    case('render resolution drives budget')

    scene, hero, small, plane, image, mat, node = fixture()
    other = bpy.data.scenes.new('Other scene')
    other.collection.objects.link(plane)
    check(blocked(analysis.analyze(bpy.context), image), 'Other scene object changed')
    case('cross-scene consumer protection')

    scene, hero, small, plane, image, mat, node = fixture()
    small.location.x = 5
    small.scale = (30, 30, 30)
    bpy.context.view_layer.update()
    check(not any(m['object'] == small for m in analysis.analyze(bpy.context)['meshes']), 'Clipped large object treated as small')
    case('cropped large object keeps full footprint')

    scene, hero, small, plane, image, mat, node = fixture()
    small.keyframe_insert('location', frame=1)
    check(any(m['object'] == small for m in analysis.analyze(bpy.context)['meshes']), 'Transform animation must allow current-frame optimization')
    case('current-frame transform animation')

    scene, hero, small, plane, image, mat, node = fixture()
    mod = small.modifiers.new('Render-only subdivision', 'SUBSURF')
    mod.levels = 0
    mod.render_levels = 2
    check(not any(m['object'] == small for m in analysis.analyze(bpy.context)['meshes']), 'Render/viewport mismatch ignored')
    case('render-only modifier protection')

    scene, hero, small, plane, image, mat, node = fixture()
    plan = analysis.analyze(bpy.context)
    plan['meshes'].append({'object': None, 'ratio': .5})
    try:
        operations.apply(bpy.context, plan)
    except (AttributeError, ReferenceError):
        pass
    else:
        raise AssertionError('Invalid plan must trigger rollback')
    check(node.image == image and not small.modifiers, 'Rollback left partial changes')
    check(not scene.vram_fixer.active_session, 'Rollback left stale session')
    check(not any(im.name.startswith('VRF |') for im in bpy.data.images), 'Rollback leaked copied images')
    case('mid-transaction rollback')

    scene, hero, small, plane, image, mat, node = fixture()
    plan = analysis.analyze(bpy.context)
    operations.apply(bpy.context, plan)
    node.name = 'Renamed after optimization'
    small.modifiers[0].name = 'Renamed decimate'
    untouched = small.modifiers.new('User modifier', 'BEVEL')
    operations.restore(bpy.context)
    check(node.image == image, 'Renamed node not restored')
    check(len(small.modifiers) == 1 and small.modifiers[0] == untouched, 'Wrong modifier removed')
    case('renamed nodes/modifiers and user additions')

    scene, hero, small, plane, image, mat, node = fixture()
    operations.apply(bpy.context, analysis.analyze(bpy.context))
    replacement = bpy.data.images.new('User replacement', width=32, height=32)
    node.image = replacement
    operations.restore(bpy.context)
    check(node.image == replacement, 'Restore overwrote user edit')
    case('restore respects changed node image')

    scene, hero, small, plane, image, mat, node = fixture()
    # Geometry must be instancing-aware even when the original is small.
    collection = bpy.data.collections.new('Instanced collection')
    collection.objects.link(small)
    instancer = bpy.data.objects.new('Collection instance', None)
    scene.collection.objects.link(instancer)
    instancer.instance_type = 'COLLECTION'
    instancer.instance_collection = collection
    instancer.scale = (8, 8, 8)
    bpy.context.view_layer.update()
    check(not any(m['object'] == small for m in analysis.analyze(bpy.context)['meshes']), 'Instance footprint ignored')
    case('collection instance safety')

    scene, hero, small, plane, image, mat, node = fixture()
    hdr = bpy.data.images.new('HDR data', width=1024, height=1024, float_buffer=True)
    hdr.generated_color = (2.5, .5, .25, 1)
    from array import array
    hdr.pixels.foreach_set(array('f', (2.5, .5, .25, 1)) * (1024 * 1024))
    node.image = hdr
    operations.apply(bpy.context, analysis.analyze(bpy.context))
    check(node.image != hdr and abs(node.image.pixels[0]-2.5) < .02,
          f'HDR values clipped: optimized={node.image != hdr}, pixel={node.image.pixels[0]}, original={hdr.pixels[0]}')
    save = Path(__file__).resolve().parent / 'hdr_session.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(save))
    bpy.ops.wm.open_mainfile(filepath=str(save))
    mat = bpy.data.materials['Shared test material']
    node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
    check(abs(node.image.pixels[0]-2.5) < .02, 'Packed HDR changed after reopening')
    operations.restore(bpy.context)
    check(abs(node.image.pixels[0]-2.5) < .02, 'Original painted/generated HDR lost on save/restore')
    case('float image HDR preservation')

    scene, hero, small, plane, image, mat, node = fixture()
    from vram_fixer import mesh_quality
    original_surface = mesh_quality.snapshot(small, bpy.context.evaluated_depsgraph_get())
    candidate = small.modifiers.new('Deliberately excessive reduction', 'DECIMATE')
    candidate.ratio = .0001
    accepted, error, samples = mesh_quality.tune(bpy.context, small, candidate, original_surface)
    check(accepted and candidate.ratio > .0001 and error <= .75 and samples > 0,
          'Surface-error tuning must back off excessive reduction')
    case('measured decimation backoff')

    scene, hero, small, plane, image, mat, node = fixture()
    check(bpy.ops.vram_fixer.analyze() == {'FINISHED'}, 'Analyze operator failed')
    check(bpy.ops.vram_fixer.fix() == {'FINISHED'}, 'Fix operator failed')
    check(bpy.ops.vram_fixer.restore() == {'FINISHED'}, 'Restore operator failed')
    case('public operators')
    vram_fixer.unregister()
    print(f'VRAM_FIXER_SAFETY_PASS: {count} cases')


run()
