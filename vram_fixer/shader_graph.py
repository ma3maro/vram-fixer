"""Instance-aware material traversal and UV routing across nested shader groups."""
from mathutils import Matrix, Vector, Euler


def image_usages(tree, path=(), ancestors=frozenset()):
    """Do not globally deduplicate groups: each instance can have different inputs."""
    if tree is None or tree.as_pointer() in ancestors:
        return
    ancestors = ancestors | {tree.as_pointer()}
    for node in tree.nodes:
        if node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'} and node.image:
            yield tree, node, path
        elif node.type == 'GROUP' and node.node_tree:
            yield from image_usages(node.node_tree, path + (node,), ancestors)


def matching(sockets, socket):
    return next((s for s in sockets if s.identifier == socket.identifier), None)


def group_output(node, socket):
    output = next((n for n in node.node_tree.nodes if n.type == 'GROUP_OUTPUT' and n.is_active_output), None)
    return matching(output.inputs, socket) if output else None


def active_image_usages(tree):
    """Follow all linked inputs, not just a direct Image -> Principled connection."""
    found = {}
    visited = set()
    def trace_input(socket, path):
        for link in socket.links:
            trace_output(link.from_socket, path)
    def trace_output(socket, path):
        key = (socket.as_pointer(), tuple(n.as_pointer() for n in path))
        if key in visited:
            return
        visited.add(key)
        node = socket.node
        if node.type == 'GROUP' and node.node_tree:
            inner = group_output(node, socket)
            if inner:
                trace_input(inner, path + (node,))
        elif node.type == 'GROUP_INPUT' and path:
            parent = matching(path[-1].inputs, socket)
            if parent:
                trace_input(parent, path[:-1])
        else:
            if node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'} and node.image:
                found[(node.as_pointer(), tuple(n.as_pointer() for n in path))] = (node.id_data, node, path)
            for inp in node.inputs:
                trace_input(inp, path)
    for output in tree.nodes:
        if output.type == 'OUTPUT_MATERIAL' and output.is_active_output and output.target in {'ALL', 'CYCLES'}:
            for socket in output.inputs:
                trace_input(socket, ())
    yield from found.values()


def socket_value(socket, path, seen=frozenset()):
    """Only evaluate known constants; never guess values from arbitrary node math."""
    if not socket.is_linked:
        return getattr(socket, 'default_value', None)
    source = socket.links[0].from_socket
    node = source.node
    key = (source.as_pointer(), tuple(n.as_pointer() for n in path))
    if key in seen:
        return None
    seen = seen | {key}
    if node.type in {'VALUE', 'RGB'}:
        return source.default_value
    if node.type == 'REROUTE':
        return socket_value(node.inputs[0], path, seen)
    if node.type == 'GROUP_INPUT' and path:
        parent_socket = matching(path[-1].inputs, source)
        return socket_value(parent_socket, path[:-1], seen) if parent_socket else None
    if node.type == 'GROUP' and node.node_tree:
        inner = group_output(node, source)
        return socket_value(inner, path + (node,), seen) if inner else None
    return None


def uv_mapping(node, mesh, path=()):
    if node.type != 'TEX_IMAGE' or node.projection != 'FLAT' or not mesh.uv_layers.active:
        return None
    active = mesh.uv_layers.active.name

    def resolve(socket, context, seen):
        if not socket or not socket.is_linked:
            return None
        source = socket.links[0].from_socket
        source_node = source.node
        key = (source.as_pointer(), tuple(n.as_pointer() for n in context))
        if key in seen:
            return None
        seen = seen | {key}
        if source_node.type == 'UVMAP':
            name = source_node.uv_map or active
            return (name, Matrix.Identity(4)) if name in mesh.uv_layers else None
        if source_node.type == 'TEX_COORD' and source.name == 'UV':
            return active, Matrix.Identity(4)
        if source_node.type == 'REROUTE':
            return resolve(source_node.inputs[0], context, seen)
        if source_node.type == 'GROUP_INPUT' and context:
            return resolve(matching(context[-1].inputs, source), context[:-1], seen)
        if source_node.type == 'GROUP' and source_node.node_tree:
            return resolve(group_output(source_node, source), context + (source_node,), seen)
        if source_node.type != 'MAPPING' or source_node.vector_type not in {'POINT', 'TEXTURE', 'VECTOR'}:
            return None
        previous = resolve(source_node.inputs['Vector'], context, seen)
        if previous is None:
            return None
        values = [socket_value(source_node.inputs[name], context) for name in ('Location', 'Rotation', 'Scale')]
        if any(value is None for value in values):
            return None
        location, rotation, scale = values
        transform = Euler(rotation).to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1))
        if source_node.vector_type != 'VECTOR':
            transform = Matrix.Translation(Vector(location)) @ transform
        if source_node.vector_type == 'TEXTURE':
            if abs(transform.determinant()) < 1e-12:
                return None
            transform.invert()
        return previous[0], transform @ previous[1]

    vector = node.inputs['Vector']
    return resolve(vector, path, frozenset()) if vector.is_linked else (active, Matrix.Identity(4))
