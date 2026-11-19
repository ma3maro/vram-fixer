"""Sampled bidirectional surface-distance checks for a candidate Decimate modifier.

This is a safety check, not a mathematical Hausdorff bound or a shading test.
"""
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

LIMITS = {'CAREFUL': .75, 'BALANCED': 1.25, 'STRONG': 2.0}
MAX_VERTICES = 1000000


def snapshot(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        if len(mesh.vertices) > MAX_VERTICES:
            raise ValueError('Mesh validation limit exceeded (1M evaluated vertices)')
        matrix = evaluated.matrix_world
        vertices = [matrix @ v.co for v in mesh.vertices]
        faces = [tuple(p.vertices) for p in mesh.polygons]
        if not faces:
            raise ValueError('No surface to validate')
        bvh = BVHTree.FromPolygons(vertices, faces, all_triangles=False)
        step = max(1, math.ceil(len(vertices) / 4096))
        samples = vertices[::step]
        step = max(1, math.ceil(len(faces) / 2048))
        for face in faces[::step]:
            center = sum((vertices[i] for i in face), Vector()) / len(face)
            samples.append(center)
        return bvh, samples
    finally:
        evaluated.to_mesh_clear()


def surface_error(scene, original, candidate):
    camera = scene.camera
    sx = scene.render.resolution_x * scene.render.resolution_percentage / 100
    sy = scene.render.resolution_y * scene.render.resolution_percentage / 100
    right = camera.matrix_world.to_quaternion() @ Vector((1, 0, 0))
    up = camera.matrix_world.to_quaternion() @ Vector((0, 1, 0))
    maximum = 0
    count = 0
    for bvh, samples in ((candidate[0], original[1]), (original[0], candidate[1])):
        for point in samples:
            nearest = bvh.find_nearest(point)
            if not nearest or nearest[0] is None:
                return float('inf'), count
            distance = nearest[3]
            p = world_to_camera_view(scene, camera, point)
            if p.z <= camera.data.clip_start:
                return float('inf'), count
            px = world_to_camera_view(scene, camera, point + right)
            py = world_to_camera_view(scene, camera, point + up)
            pixels_per_unit = max(abs(px.x-p.x)*sx, abs(py.y-p.y)*sy)
            # World distance, not just projected displacement: depth-only errors
            # can change reflections even when the direct projection is identical.
            maximum = max(maximum, distance * pixels_per_unit)
            count += 1
    return maximum, count


def tune(context, obj, modifier, original):
    deps = context.evaluated_depsgraph_get()
    limit = LIMITS[context.scene.vram_fixer.preset]
    for _ in range(5):
        context.view_layer.update()
        deps.update()
        candidate = snapshot(obj, deps)
        error, samples = surface_error(context.scene, original, candidate)
        if error <= limit:
            return True, error, samples
        modifier.ratio = 1 - (1 - modifier.ratio) * .5
    return False, error, samples
