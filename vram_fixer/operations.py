"""Reversible changes. Restore records are Blender datablocks, not Python session state."""
import uuid
from array import array
import bpy
from . import mesh_quality

TOKEN = 'vram_fixer_node_token'


def apply(context, plan):
    scene = context.scene
    settings = scene.vram_fixer
    if settings.active_session or settings.image_changes or settings.mesh_changes:
        raise RuntimeError('Restore the current session before applying another optimization')
    if scene != plan['scene'] or scene.frame_current != plan['frame'] or scene.camera != plan['camera']:
        raise RuntimeError('Scene, camera or frame changed; analyze again')
    if not plan['images'] and not plan['meshes']:
        return 0, 0
    settings.active_session = uuid.uuid4().hex
    try:
        for item in plan['images']:
            original = item['image']
            rec = settings.image_changes.add()
            rec.original = original
            # Blender does not serialize edited GENERATED pixel buffers unless
            # packed. Preserve those edits for Restore after saving the blend.
            if original.source == 'GENERATED' and not original.packed_file:
                original.pack()
            reduced = original.copy()
            rec.optimized = reduced
            reduced.name = f'VRF | {original.name} | {item["size"][0]}'
            # Image.copy() can regenerate a GENERATED image instead of copying its
            # edited buffer. Copy linear pixel values explicitly, then free the
            # staging allocation before Blender's native filtered downsampling.
            pixels = array('f', [0.0]) * len(original.pixels)
            original.pixels.foreach_get(pixels)
            reduced.pixels.foreach_set(pixels)
            del pixels
            reduced.scale(*item['size'])
            extension = 'exr' if original.is_float else 'png'
            reduced.filepath_raw = f'//vram_fixer/{settings.active_session}/{uuid.uuid4().hex}.{extension}'
            reduced.file_format = 'OPEN_EXR' if original.is_float else 'PNG'
            # Packed reduced copies and original pointers survive saving/reopening.
            reduced.pack()
            for tree, node in item['nodes']:
                change = rec.nodes.add()
                material = next((mat for mat in bpy.data.materials if mat.node_tree == tree), None)
                if material:
                    change.material = material
                else:
                    change.tree = tree
                change.node_name = node.name
                change.token = uuid.uuid4().hex
                node[TOKEN] = change.token
                node.image = reduced
        for item in plan['meshes']:
            obj = item['object']
            original_surface = mesh_quality.snapshot(obj, context.evaluated_depsgraph_get())
            rec = settings.mesh_changes.add()
            rec.object = obj
            modifier = obj.modifiers.new(f'VRF Decimate {settings.active_session[:8]}', 'DECIMATE')
            rec.modifier_name = modifier.name
            rec.uid = getattr(modifier, 'persistent_uid', 0)
            modifier.decimate_type = 'COLLAPSE'
            modifier.ratio = item['ratio']
            modifier.use_collapse_triangulate = True
            modifier.show_expanded = False
            accepted, error, samples = mesh_quality.tune(context, obj, modifier, original_surface)
            rec.error_pixels = error
            rec.samples = samples
            if not accepted or modifier.ratio >= .95:
                obj.modifiers.remove(modifier)
                settings.mesh_changes.remove(len(settings.mesh_changes)-1)
                plan['report'] += f'\nVALIDATION KEPT {obj.name}: no useful reduction within pixel-error limit.'
            else:
                plan['report'] += (f'\nVALIDATED {obj.name}: retain {modifier.ratio:.1%}, '
                                   f'{error:.3f}px sampled surface error ({samples:,} points).')
        context.view_layer.update()
    except Exception:
        restore(context)
        raise
    if not settings.image_changes and not settings.mesh_changes:
        settings.active_session = ''
    return len(settings.image_changes), len(settings.mesh_changes)


def restore(context):
    settings = context.scene.vram_fixer
    warnings = []
    for rec in settings.image_changes:
        reduced, original = rec.optimized, rec.original
        for change in rec.nodes:
            tree = change.tree or (change.material.node_tree if change.material else None)
            if not tree:
                continue
            node = next((n for n in tree.nodes if n.get(TOKEN) == change.token), None)
            if node is None:
                node = tree.nodes.get(change.node_name)
                if node and getattr(node, 'image', None) != reduced:
                    node = None
            if node is None:
                continue
            if getattr(node, 'image', None) == reduced:
                if original:
                    node.image = original
                else:
                    warnings.append('Original image was deleted: ' + change.node_name)
            if node.get(TOKEN) == change.token:
                del node[TOKEN]
        # Never unlink new consumers the user added after optimization.
        rec.optimized = None
        if reduced and reduced.users == 0:
            bpy.data.images.remove(reduced)
        elif reduced:
            warnings.append('Kept optimized image still used elsewhere: ' + reduced.name)
    for rec in settings.mesh_changes:
        obj = rec.object
        if not obj:
            continue
        modifier = None
        if rec.uid:
            modifier = next((m for m in obj.modifiers if getattr(m, 'persistent_uid', 0) == rec.uid), None)
        else:
            modifier = obj.modifiers.get(rec.modifier_name)
        if modifier and modifier.type == 'DECIMATE':
            obj.modifiers.remove(modifier)
    settings.image_changes.clear()
    settings.mesh_changes.clear()
    settings.active_session = ''
    context.view_layer.update()
    return warnings


def write_report(plan, applied=False):
    text = bpy.data.texts.get('VRAM Fixer Report') or bpy.data.texts.new('VRAM Fixer Report')
    text.clear()
    text.write(('APPLIED\n' if applied else 'PREVIEW — NO CHANGES MADE\n') + plan['report'])
    return text
