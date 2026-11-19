"""Read-only camera-space analysis. Ambiguous dependencies are preserved, not guessed."""
import math
from collections import defaultdict

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from .shader_graph import image_usages, active_image_usages, uv_mapping
from .policy import importance, texture_demand, texture_size, mesh_ratio, image_bytes, coverage_demand

EDGES = ((0, 1), (0, 3), (0, 4), (1, 2), (1, 5), (2, 3),
         (2, 6), (3, 7), (4, 5), (4, 7), (5, 6), (6, 7))
MAX_UV_TRIANGLES = 100000


def image_nodes(tree, seen=None):
    """Yield each actual node once even when a group has multiple instances."""
    seen = set() if seen is None else seen
    if tree is None or tree.as_pointer() in seen:
        return
    seen.add(tree.as_pointer())
    for node in tree.nodes:
        if node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'} and node.image:
            yield tree, node
        elif node.type == 'GROUP' and node.node_tree:
            yield from image_nodes(node.node_tree, seen)


def object_materials(obj):
    return [s.material for s in obj.material_slots if s.material and s.material.use_nodes]


def animated(obj):
    return bool(obj.animation_data or (obj.data and getattr(obj.data, 'animation_data', None)))


def ancestors(obj):
    parent = obj.parent
    while parent:
        yield parent
        parent = parent.parent


def projection(scene, camera, obj, matrix=None):
    matrix = obj.matrix_world if matrix is None else matrix
    corners = [matrix @ Vector(c) for c in obj.bound_box]
    inv = camera.matrix_world.inverted()
    near = max(camera.data.clip_start, 1e-5)
    depths = [-(inv @ p).z for p in corners]
    points = [p for p, z in zip(corners, depths) if z >= near]
    crossing = any(z < near for z in depths)
    for a, b in EDGES:
        za, zb = depths[a], depths[b]
        if (za < near) != (zb < near):
            t = (near - za) / (zb - za)
            points.append(corners[a].lerp(corners[b], t))
    if not points:
        return {'visible': False, 'width': 0, 'height': 0, 'near': crossing}
    ndc = [world_to_camera_view(scene, camera, p) for p in points]
    x0, x1 = min(p.x for p in ndc), max(p.x for p in ndc)
    y0, y1 = min(p.y for p in ndc), max(p.y for p in ndc)
    r = scene.render
    bx0, by0, bx1, by1 = (r.border_min_x, r.border_min_y, r.border_max_x, r.border_max_y) if r.use_border else (0, 0, 1, 1)
    # Unclipped footprint prevents crop-edge objects being mistaken for tiny objects.
    width = (x1 - x0) * r.resolution_x * r.resolution_percentage / 100
    height = (y1 - y0) * r.resolution_y * r.resolution_percentage / 100
    return {'visible': x1 > bx0 and x0 < bx1 and y1 > by0 and y0 < by1,
            'width': width, 'height': height, 'near': crossing}


def singular_value(a, b, c, d):
    trace = a*a + b*b + c*c + d*d
    det = (a*d - b*c) ** 2
    return math.sqrt(max(0, (trace + math.sqrt(max(0, trace*trace - 4*det))) / 2))


def uv_demands(scene, camera, evaluated, images_by_material):
    """Area-weighted UV-to-pixel demand, corrected for rectangular images.

    Examine every evaluated triangle, then select the preset's coverage percentile.
    Subpixel UV slivers must not veto an otherwise useful texture reduction.
    """
    mesh = evaluated.to_mesh()
    try:
        if not mesh.uv_layers.active:
            return {}, 'no active UV map'
        count = sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)
        if count > MAX_UV_TRIANGLES:
            return {}, f'UV safety limit ({count:,} triangles)'
        mesh.calc_loop_triangles()
        r = scene.render
        sx = r.resolution_x * r.resolution_percentage / 100
        sy = r.resolution_y * r.resolution_percentage / 100
        matrix = evaluated.matrix_world
        projected = [world_to_camera_view(scene, camera, matrix @ v.co) for v in mesh.vertices]
        samples = defaultdict(list)
        for tri in mesh.loop_triangles:
            images = images_by_material.get(tri.material_index, ())
            if not images:
                continue
            p = [projected[i] for i in tri.vertices]
            if any(v.z <= camera.data.clip_start for v in p):
                return {}, 'UV surface crosses camera near plane'
            x1, y1 = (p[1].x-p[0].x)*sx, (p[1].y-p[0].y)*sy
            x2, y2 = (p[2].x-p[0].x)*sx, (p[2].y-p[0].y)*sy
            area = abs(x1*y2-x2*y1) / 2
            if area < 1e-9:
                continue
            for image, uv_name, transform in images:
                layer = mesh.uv_layers.get(uv_name)
                if layer is None:
                    return {}, 'missing evaluated UV layer'
                u = [transform @ Vector((*layer.data[i].uv, 0)) for i in tri.loops]
                u1, v1 = u[1].x-u[0].x, u[1].y-u[0].y
                u2, v2 = u[2].x-u[0].x, u[2].y-u[0].y
                det = u1*v2 - u2*v1
                if abs(det) < 1e-12:
                    return {}, 'degenerate UV triangle'
                a, b = (x1*v2-x2*v1)/det, (-x1*u2+x2*u1)/det
                c, d = (y1*v2-y2*v1)/det, (-y1*u2+y2*u1)/det
                w, h = image.size
                longest = max(w, h)
                if min(w, h) > 0:
                    value = singular_value(a*longest/w, b*longest/h, c*longest/w, d*longest/h)
                    # Vertex-to-vertex differences alone can undersample a strongly
                    # foreshortened perspective triangle near its closest corner.
                    if camera.data.type == 'PERSP':
                        value *= (max(v.z for v in p) / min(v.z for v in p)) ** 2
                    samples[image].append((value, area))
        return {image: coverage_demand(values, scene.vram_fixer.preset) for image, values in samples.items()}, ''
    finally:
        evaluated.to_mesh_clear()


def mesh_risk(obj, evaluated, instance_objects):
    if obj.library or obj.override_library or obj.data.library:
        return 'linked or overridden geometry'
    if obj in instance_objects or obj.is_instancer:
        return 'instanced geometry (preserved for all views)'
    if obj.data.shape_keys:
        return 'shape-key geometry'
    if obj.constraints or obj.vertex_groups:
        return 'constrained or weighted geometry'
    if any(m.type not in {'SUBSURF', 'TRIANGULATE', 'WEIGHTED_NORMAL', 'NORMAL_EDIT', 'DECIMATE', 'BEVEL'}
           for m in obj.modifiers if m.show_render):
        return 'topology-sensitive modifier stack'
    if any(m.show_render != m.show_viewport or (m.type == 'SUBSURF' and m.levels != m.render_levels)
           for m in obj.modifiers):
        return 'viewport/render modifier mismatch'
    for mat in object_materials(obj):
        if any(n.type == 'OUTPUT_MATERIAL' and n.inputs.get('Displacement') and n.inputs['Displacement'].is_linked
               for n in mat.node_tree.nodes):
            return 'material displacement'
    if len(evaluated.data.vertices) > 1000000:
        return 'mesh validation safety limit (1M evaluated vertices)'
    if len(evaluated.data.polygons) < 256:
        return 'already low-poly'
    return ''


def analyze(context):
    scene = context.scene
    settings = scene.vram_fixer
    if settings.active_session:
        raise ValueError('Restore the current optimization before analyzing again')
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode first')
    camera = scene.camera
    reference = settings.reference
    if not camera or camera.type != 'CAMERA':
        raise ValueError('Set an active render camera first')
    if camera.data.type not in {'PERSP', 'ORTHO'}:
        raise ValueError('Panoramic cameras need ray-based analysis and are not supported')
    if not reference or reference.type != 'MESH' or reference.name not in scene.objects:
        raise ValueError('Choose a mesh in this scene as the size reference')
    if reference.hide_render:
        raise ValueError('The reference is hidden from rendering')
    if not settings.textures and not settings.meshes:
        raise ValueError('Enable Textures, Meshes, or both')
    deps = context.evaluated_depsgraph_get()
    deps.update()
    ref_projection = projection(scene, camera, reference.evaluated_get(deps))
    if not ref_projection['visible'] or ref_projection['near']:
        raise ValueError('The reference must be in the camera frame and clear of its near plane')
    ref_span = max(ref_projection['width'], ref_projection['height'])
    if ref_span < 2:
        raise ValueError('The reference is too small: choose an object at least 2 render pixels across')
    protected = {x.object for x in settings.protected if x.object}
    if settings.protect_reference:
        protected.add(reference)
    instance_objects = {i.object.original for i in deps.object_instances if i.is_instance}
    instance_objects |= {i.parent.original for i in deps.object_instances if i.is_instance and i.parent}
    stats = {}
    lines = [f'VRAM FIXER | {scene.name} | frame {scene.frame_current}',
             f'Camera: {camera.name} | Reference: {reference.name} ({ref_span:.1f}px)',
             f'Quality: {settings.preset} | Current camera/frame only. No occlusion or reflection tracing.',
             'Texture estimates are render working-set estimates, NOT measured GPU VRAM.', '']
    meshes = []
    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(deps)
        p = projection(scene, camera, evaluated)
        span = max(p['width'], p['height'])
        reason = ''
        if obj in protected:
            reason = 'protected'
        elif obj.hide_render or not obj.visible_get(view_layer=context.view_layer):
            reason = 'hidden/excluded; not safely evaluated'
        elif obj.library or obj.override_library:
            reason = 'linked/override object'
        elif any(other != scene and obj.name in other.objects for other in bpy.data.scenes):
            reason = 'object shared with another scene'
        elif not p['visible']:
            reason = 'off-camera (reflection/shadow safeguard)'
        elif p['near']:
            reason = 'crosses near plane'
        elif obj in instance_objects or obj.is_instancer:
            reason = 'instance dependency'
        stats[obj] = {'projection': p, 'span': span, 'reason': reason, 'evaluated': evaluated}
        if settings.meshes:
            risk = reason or mesh_risk(obj, evaluated, instance_objects)
            tris = 0 if risk else sum(max(0, len(poly.vertices)-2) for poly in evaluated.data.polygons)
            ratio = 1 if risk else mesh_ratio(tris, p['width'], p['height'], ref_span, settings.preset)
            if ratio < .95:
                meshes.append({'object': obj, 'ratio': ratio, 'triangles': tris})
                lines.append(f'MESH {obj.name}: {tris:,} -> ~{int(tris*ratio):,} triangles | retain {ratio:.1%} | {span:.1f}px')
            else:
                lines.append(f'KEEP MESH {obj.name}: {risk or "already within pixel budget"}')
    images = []
    if settings.textures:
        consumers = defaultdict(set)
        nodes = defaultdict(dict)
        blockers = defaultdict(set)
        # Scan ALL datablock consumers, not just selected objects or the active scene.
        material_objects = defaultdict(set)
        for obj in bpy.data.objects:
            for mat in object_materials(obj):
                material_objects[mat].add(obj)
        for mat in bpy.data.materials:
            if not mat.use_nodes:
                continue
            for tree, node, path in image_usages(mat.node_tree):
                image = node.image
                nodes[image][node.as_pointer()] = (tree, node)
                owners = material_objects.get(mat, set())
                consumers[image].update(owners)
                if not owners:
                    blockers[image].add('material without a tracked object consumer')
                if mat.library or tree.library:
                    blockers[image].add('linked material or node tree')
        for world in bpy.data.worlds:
            for _, node in image_nodes(world.node_tree):
                blockers[node.image].add('world/environment consumer')
        for tree in bpy.data.node_groups:
            if tree.bl_idname != 'ShaderNodeTree':
                for _, node in image_nodes(tree):
                    blockers[node.image].add('geometry/compositor node consumer')
        for other_scene in bpy.data.scenes:
            for _, node in image_nodes(getattr(other_scene, 'node_tree', None)):
                blockers[node.image].add('compositor consumer')
        for texture in bpy.data.textures:
            if getattr(texture, 'image', None):
                blockers[texture.image].add('legacy texture/displacement consumer')
        # Unknown ID users (brushes, image empties, modifiers) must not be ignored.
        user_map = bpy.data.user_map()
        for image in nodes:
            allowed = {tree for tree, _ in nodes[image].values()}
            allowed.update(mat for mat in bpy.data.materials if mat.use_nodes and mat.node_tree in allowed)
            if any(user not in allowed for user in user_map.get(image, set())):
                blockers[image].add('additional image datablock consumer')
        object_demands = {}
        for obj, info in stats.items():
            if info['reason']:
                continue
            per_material = {}
            for index, slot in enumerate(obj.material_slots):
                mat = slot.material
                if not mat or not mat.use_nodes:
                    continue
                acceptable = []
                for tree, node, path in active_image_usages(mat.node_tree):
                    image = node.image
                    mapping = uv_mapping(node, info['evaluated'].data, path)
                    if mapping is not None:
                        acceptable.append((image, *mapping))
                    else:
                        blockers[image].add('unresolved UV mapping/projection')
                per_material[index] = acceptable
            if any(per_material.values()):
                try:
                    object_demands[obj] = uv_demands(scene, camera, info['evaluated'], per_material)
                except (RuntimeError, ValueError, ZeroDivisionError) as exc:
                    object_demands[obj] = ({}, f'UV evaluation failed: {exc}')
        for image in sorted(nodes, key=lambda im: im.name):
            reasons = set(blockers[image])
            if image.library or image.source not in {'FILE', 'GENERATED'} or image.type not in {'IMAGE', 'UV_TEST'}:
                reasons.add('linked, tiled, movie, sequence or unsupported image')
            if min(image.size) <= 0 or not image.has_data:
                reasons.add('unloaded/missing image pixels')
            if image.is_dirty and image.source == 'FILE':
                reasons.add('unsaved painted image (save edits first)')
            demand = 0
            for obj in consumers[image]:
                if obj not in stats:
                    reasons.add('consumer outside analyzed scene/view layer')
                    continue
                info = stats[obj]
                if info['reason']:
                    reasons.add(f'{obj.name}: {info["reason"]}')
                    continue
                uv_values, uv_reason = object_demands.get(obj, ({}, 'no safe UV usage'))
                if uv_reason or image not in uv_values:
                    reasons.add(uv_reason or f'{obj.name}: unmeasured UV demand')
                    continue
                # Non-color maps retain extra bandwidth for shading derivatives.
                detail = image.colorspace_settings.name in {'Non-Color', 'Raw'}
                demand = max(demand, texture_demand(info['span'], info['span'] / max(uv_values[image], 1e-9), ref_span, detail, settings.preset),
                             texture_demand(info['span'], 1, ref_span, detail, settings.preset))
            if not consumers[image]:
                reasons.add('no object consumers')
            size = tuple(image.size) if reasons else texture_size(*image.size, demand)
            if size != tuple(image.size):
                before = image_bytes(*image.size, image.channels, image.is_float)
                after = image_bytes(*size, image.channels, image.is_float)
                images.append({'image': image, 'size': size, 'nodes': list(nodes[image].values()),
                               'before': before, 'after': after})
                lines.append(f'TEXTURE {image.name}: {image.size[0]}x{image.size[1]} -> {size[0]}x{size[1]} | ~{(before-after)/1048576:.1f} MiB less')
            else:
                lines.append(f'KEEP TEXTURE {image.name}: {"; ".join(sorted(reasons)) or f"within texel budget (required long edge ~{demand:.0f}px)"}')
    saved = sum(i['before']-i['after'] for i in images)
    triangles = sum(int(m['triangles']*(1-m['ratio'])) for m in meshes)
    lines.extend(['', f'PLAN: {len(images)} unique textures, {len(meshes)} meshes.',
                  f'Estimated texture working-set reduction: {saved/1048576:.1f} MiB (backend dependent).',
                  f'Estimated triangle reduction: {triangles:,}. Mesh VRAM is not inferred from triangle count.',
                  'Originals remain in the blend for Restore; host RAM / blend size can grow.',
                  'Decimation can alter silhouettes, UV interpolation, reflections and shadows. Compare a test render.'])
    return {'images': images, 'meshes': meshes, 'report': '\n'.join(lines), 'saved': saved,
            'scene': scene, 'frame': scene.frame_current, 'camera': camera}
