"""User-reported no-op: nested material graphs, ordinary animation and oversized textures."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_integration import bpy, fixture, check, vram_fixer, analysis, operations


def nested_fixture():
    scene, hero, small, plane, image, mat, node = fixture()
    mat.node_tree.nodes.remove(node)
    inner = bpy.data.node_groups.new('Inner texture group', 'ShaderNodeTree')
    inner.interface.new_socket(name='UV', in_out='INPUT', socket_type='NodeSocketVector')
    inner.interface.new_socket(name='Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    inp = inner.nodes.new('NodeGroupInput')
    out = inner.nodes.new('NodeGroupOutput')
    tex = inner.nodes.new('ShaderNodeTexImage')
    tex.image = image
    inner.links.new(inp.outputs['UV'], tex.inputs['Vector'])
    ramp = inner.nodes.new('ShaderNodeValToRGB')
    inner.links.new(tex.outputs['Color'], ramp.inputs['Fac'])
    inner.links.new(ramp.outputs['Color'], out.inputs['Color'])
    outer = bpy.data.node_groups.new('Outer shared group', 'ShaderNodeTree')
    outer.interface.new_socket(name='Vector', in_out='INPUT', socket_type='NodeSocketVector')
    outer.interface.new_socket(name='Result', in_out='OUTPUT', socket_type='NodeSocketColor')
    gi = outer.nodes.new('NodeGroupInput')
    go = outer.nodes.new('NodeGroupOutput')
    child = outer.nodes.new('ShaderNodeGroup')
    child.node_tree = inner
    outer.links.new(gi.outputs['Vector'], child.inputs['UV'])
    outer.links.new(child.outputs['Color'], go.inputs['Result'])
    group = mat.node_tree.nodes.new('ShaderNodeGroup')
    group.node_tree = outer
    coords = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    mapping = mat.node_tree.nodes.new('ShaderNodeMapping')
    mat.node_tree.links.new(coords.outputs['UV'], mapping.inputs['Vector'])
    mat.node_tree.links.new(mapping.outputs['Vector'], group.inputs['Vector'])
    mat.node_tree.links.new(group.outputs['Result'], mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    return scene, hero, small, plane, image, mat, tex, group, mapping


def run():
    vram_fixer.register()
    scene, hero, small, plane, image, mat, node, group, mapping = nested_fixture()
    plan = analysis.analyze(bpy.context)
    check(any(i['image'] == image for i in plan['images']), 'Nested group + color ramp must not produce zero texture changes')
    operations.apply(bpy.context, plan)
    check(node.image != image, 'Image buried two groups deep must be replaced')
    save = Path(__file__).resolve().parent / 'group_session.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(save))
    bpy.ops.wm.open_mainfile(filepath=str(save))
    node = next(n for n in bpy.data.node_groups['Inner texture group'].nodes if n.type == 'TEX_IMAGE')
    operations.restore(bpy.context)
    check(node.image == bpy.data.images['Original texture'], 'Nested group image must restore after saving/reopening')
    print('PASS nested groups through color ramp')

    scene, hero, small, plane, image, mat, node, group, mapping = nested_fixture()
    mapping.inputs['Scale'].default_value = (.01, .01, 1)
    check(not analysis.analyze(bpy.context)['images'], 'Mapping outside nested group must retain tiny UV island detail')
    print('PASS group-input UV context')

    scene, hero, small, plane, image, mat, node, group, mapping = nested_fixture()
    # A second instance of the SAME group uses a different coordinate scale.
    group2 = mat.node_tree.nodes.new('ShaderNodeGroup')
    group2.node_tree = group.node_tree
    coords = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    map2 = mat.node_tree.nodes.new('ShaderNodeMapping')
    map2.inputs['Scale'].default_value = (.01, .01, 1)
    mat.node_tree.links.new(coords.outputs['UV'], map2.inputs['Vector'])
    mat.node_tree.links.new(map2.outputs['Vector'], group2.inputs['Vector'])
    mix = mat.node_tree.nodes.new('ShaderNodeMixRGB')
    mat.node_tree.links.new(group.outputs['Result'], mix.inputs[1])
    mat.node_tree.links.new(group2.outputs['Result'], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs[0], mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    check(not analysis.analyze(bpy.context)['images'], 'Shared group instances must use maximum demand, not first context')
    print('PASS repeated-group context demand')

    scene, hero, small, plane, image, mat, node, group, mapping = nested_fixture()
    hero.data.materials.append(mat)
    check(not analysis.analyze(bpy.context)['images'], 'Protected object sharing a nested group must remain safe')
    print('PASS protected shared groups')

    scene, hero, small, plane, image, mat, node = fixture()
    plane.keyframe_insert('location', frame=1)
    check(analysis.analyze(bpy.context)['images'], 'A transform keyframe must not disable current-frame texture optimization')
    print('PASS transform animation at current frame')

    scene, hero, small, plane, image, mat, node = fixture()
    plane.scale = (6, 6, 6)
    image.scale(4096, 4096)
    bpy.context.view_layer.update()
    check(analysis.analyze(bpy.context)['images'], 'Reference-sized unprotected object can still have oversized textures')
    print('PASS oversized texture on reference-sized object')

    scene, hero, small, plane, image, mat, node = fixture()
    mod = plane.modifiers.new('Render-only subdivision', 'SUBSURF')
    mod.levels = 0
    mod.render_levels = 2
    mod.show_viewport = False
    check(analysis.analyze(bpy.context)['images'], 'Render-only subdivision must not block ordinary texture resizing')
    print('PASS render-only subdivision texture analysis')

    scene, hero, small, plane, image, mat, node = fixture()
    normal = mat.node_tree.nodes.new('ShaderNodeNormalMap')
    mat.node_tree.links.new(node.outputs['Color'], normal.inputs['Color'])
    mat.node_tree.links.new(normal.outputs['Normal'], mat.node_tree.nodes.get('Principled BSDF').inputs['Normal'])
    image.colorspace_settings.name = 'Non-Color'
    small.data.materials.append(mat)
    check(analysis.analyze(bpy.context)['meshes'], 'A normal-map material is not a reason to skip all decimation')
    print('PASS normal-map mesh support')
    scene, hero, small, plane, image, mat, node = fixture()
    unused = bpy.data.images.new('Disconnected image', width=1024, height=1024)
    extra = mat.node_tree.nodes.new('ShaderNodeTexImage')
    extra.image = unused
    plan = analysis.analyze(bpy.context)
    check(any(i['image'] == image for i in plan['images']), 'Connected texture must still be optimized')
    check(not any(i['image'] == unused for i in plan['images']), 'Disconnected image must not count as VRAM savings')
    print('PASS disconnected nodes excluded')
    vram_fixer.unregister()
    print('VRAM_FIXER_REGRESSIONS_PASS')


run()
