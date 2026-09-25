"""Mesh editing, inspection and conversion.

The edits are deterministic geometry operations applied in the order they are given; the
input file is never modified. Inspection reuses the implementation ported from
CyTools_Trellis2Texture (same engine, same trimesh version) rather than describing
materials a second time.
"""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, serve  # noqa: E402
from pbr_config import MAX_FACES, MAX_MESH_BYTES, MESH_SUFFIXES  # noqa: E402

EXPORT_SUFFIX = {'glb': '.glb', 'gltf': '.gltf', 'obj': '.obj', 'ply': '.ply', 'stl': '.stl', 'off': '.off'}
AXIS_INDEX = {'x': 0, 'y': 1, 'z': 2}


def _load(path, keep_materials=True):
    import trimesh
    source = Path(path)
    if not source.is_file():
        raise WorkerError('MissingInput', f'File not found: {source}', recoverable=True)
    if source.suffix.lower() not in MESH_SUFFIXES:
        raise WorkerError('InvalidParameters',
                          f'Unsupported extension {source.suffix}; expected one of {", ".join(MESH_SUFFIXES)}')
    if source.stat().st_size > MAX_MESH_BYTES:
        raise WorkerError('InvalidParameters', f'File larger than {MAX_MESH_BYTES // 1024 ** 2} MiB')
    loaded = trimesh.load(source, process=False, skip_materials=not keep_materials)
    if isinstance(loaded, trimesh.Scene):
        geometries = [item for item in loaded.geometry.values() if isinstance(item, trimesh.Trimesh)]
        if not geometries:
            raise WorkerError('InvalidMesh', 'The file contains no triangle mesh')
        mesh = loaded.to_mesh() if len(geometries) > 1 else geometries[0]
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        raise WorkerError('InvalidMesh', f'Unsupported geometry type: {type(loaded).__name__}')
    if len(mesh.faces) == 0:
        raise WorkerError('InvalidMesh', 'The mesh has no face')
    if len(mesh.faces) > MAX_FACES:
        raise WorkerError('InvalidMesh', f'The mesh has {len(mesh.faces)} faces; the limit is {MAX_FACES}')
    return mesh


def _component_count(mesh):
    """Connected pieces, counted on the face adjacency alone.

    ``mesh.split`` builds every piece as a new mesh and tries to close its holes to tell whether
    it is watertight: on a 240 000-face LocalMesh result that is slow, and it is what first
    required networkx here. Counting only needs the graph.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    count = len(mesh.faces)
    if count == 0:
        return 0
    pairs = mesh.face_adjacency
    graph = coo_matrix(([1] * len(pairs), (pairs[:, 0], pairs[:, 1])), shape=(count, count))
    return int(connected_components(graph, directed=False)[0])


def _stats(mesh):
    import numpy as np
    visual = getattr(mesh, 'visual', None)
    uv = getattr(visual, 'uv', None)
    colors = getattr(visual, 'vertex_colors', None)
    return {
        'vertices': int(len(mesh.vertices)),
        'faces': int(len(mesh.faces)),
        'components': _component_count(mesh),
        'bounds': [float(value) for value in np.asarray(mesh.bounds).ravel()],
        'extents': [float(value) for value in np.asarray(mesh.extents).ravel()],
        'isWatertight': bool(mesh.is_watertight),
        'hasUv': uv is not None and len(uv) == len(mesh.vertices),
        'hasVertexColors': colors is not None and len(colors) == len(mesh.vertices),
        'materialCount': 1 if getattr(visual, 'material', None) is not None else 0,
    }


# --------------------------------------------------------------------------- edit steps

def _apply(mesh, step, warnings):
    """Apply one edit and return the resulting mesh."""
    import numpy as np
    import trimesh

    action = step['action']
    value = float(step.get('value', 1.0))
    axis = str(step.get('axis', 'y')).lower()
    vector = step.get('vector')
    iterations = int(step.get('iterations', 1))
    threshold = float(step.get('threshold', 0.0))

    if action == 'center':
        mesh.apply_translation(-mesh.bounding_box.centroid)
    elif action == 'recenter_base':
        centroid = mesh.bounding_box.centroid
        offset = -centroid
        index = AXIS_INDEX.get(axis, 1)
        offset[index] = -mesh.bounds[0][index]
        mesh.apply_translation(offset)
    elif action == 'scale':
        if vector:
            mesh.apply_transform(trimesh.transformations.scale_matrix(1.0).astype(np.float64)
                                 @ np.diag([float(vector[0]), float(vector[1]), float(vector[2]), 1.0]))
        else:
            if value <= 0:
                raise WorkerError('InvalidParameters', 'scale needs a strictly positive value')
            mesh.apply_scale(value)
    elif action == 'scale_to_size':
        if value <= 0:
            raise WorkerError('InvalidParameters', 'scale_to_size needs a strictly positive value')
        extents = np.asarray(mesh.extents, dtype=float)
        current = float(extents.max()) if axis == 'all' else float(extents[AXIS_INDEX.get(axis, 1)])
        if current <= 0:
            raise WorkerError('InvalidMesh', 'The mesh has a zero extent on that axis')
        mesh.apply_scale(value / current)
    elif action == 'rotate':
        if vector:
            for index, angle in enumerate(vector):
                if float(angle):
                    direction = [0.0, 0.0, 0.0]
                    direction[index] = 1.0
                    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.radians(float(angle)), direction))
        else:
            direction = [0.0, 0.0, 0.0]
            direction[AXIS_INDEX.get(axis, 1)] = 1.0
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.radians(value), direction))
    elif action == 'translate':
        if vector:
            mesh.apply_translation([float(vector[0]), float(vector[1]), float(vector[2])])
        else:
            offset = [0.0, 0.0, 0.0]
            offset[AXIS_INDEX.get(axis, 1)] = value
            mesh.apply_translation(offset)
    elif action == 'flip_axis':
        scale = [1.0, 1.0, 1.0]
        scale[AXIS_INDEX.get(axis, 1)] = -1.0
        mesh.apply_transform(np.diag(scale + [1.0]))
        mesh.invert()
    elif action == 'swap_up_axis':
        # y-up <-> z-up, the conversion glTF and most DCC tools disagree about.
        angle = -90.0 if axis in ('z', 'all') else 90.0
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.radians(angle), [1.0, 0.0, 0.0]))
    elif action == 'decimate':
        target = int(step.get('targetFaces', 0)) or int(len(mesh.faces) * max(0.001, min(1.0, value)))
        target = max(4, min(target, len(mesh.faces)))
        if target >= len(mesh.faces):
            warnings.append('decimate: the target is not below the current face count, mesh left untouched.')
        else:
            mesh = _decimate(mesh, target, warnings)
    elif action == 'subdivide':
        for _ in range(max(1, min(iterations, 4))):
            if len(mesh.faces) * 4 > MAX_FACES:
                warnings.append('subdivide stopped: the next pass would exceed the face limit.')
                break
            mesh = mesh.subdivide()
    elif action == 'smooth':
        try:
            import trimesh.smoothing as smoothing
            smoothing.filter_taubin(mesh, iterations=max(1, min(iterations, 50)))
        except Exception as exc:
            warnings.append(f'smooth could not run: {exc}')
    elif action == 'weld_vertices':
        before = len(mesh.vertices)
        mesh.merge_vertices(merge_tex=True, merge_norm=True)
        warnings.append(f'weld_vertices merged {before - len(mesh.vertices)} vertices.')
    elif action == 'remove_floaters':
        mesh = _remove_floaters(mesh, threshold or 0.02, warnings)
    elif action == 'fill_holes':
        filled = mesh.fill_holes()
        if not filled:
            warnings.append('fill_holes: trimesh could not close every boundary.')
    elif action == 'fix_normals':
        mesh.fix_normals()
    elif action == 'triangulate':
        warnings.append('triangulate: trimesh already stores triangles only; nothing to do.')
    elif action == 'split_components':
        parts = mesh.split(only_watertight=False)
        warnings.append(f'split_components found {len(parts)} components; they are reported, the mesh is unchanged.')
    elif action == 'merge_components':
        mesh.merge_vertices()
    elif action == 'keep_largest':
        parts = mesh.split(only_watertight=False)
        if len(parts) > 1:
            mesh = max(parts, key=lambda part: len(part.faces))
            warnings.append(f'keep_largest dropped {len(parts) - 1} smaller components.')
    elif action == 'strip_materials':
        import trimesh as _trimesh
        mesh.visual = _trimesh.visual.ColorVisuals(mesh=mesh)
    elif action == 'strip_uv':
        visual = getattr(mesh, 'visual', None)
        if getattr(visual, 'uv', None) is not None:
            visual.uv = None
    else:
        raise WorkerError('InvalidParameters', f'Unknown edit action "{action}"')
    return mesh


def _decimate(mesh, target, warnings):
    """Quadric decimation, with the fast path first and a documented fallback."""
    try:
        return mesh.simplify_quadric_decimation(face_count=target)
    except Exception as exc:
        warnings.append(f'Quadric decimation is unavailable ({exc}); falling back to vertex clustering.')
    import numpy as np
    ratio = max(0.02, min(0.9, (target / max(1, len(mesh.faces))) ** (1 / 3)))
    pitch = float(np.asarray(mesh.extents).max()) * (1.0 - ratio) / 64.0
    if pitch <= 0:
        return mesh
    try:
        import trimesh
        return trimesh.voxel.ops.points_to_marching_cubes(mesh.vertices, pitch=pitch)
    except Exception as exc:
        warnings.append(f'The fallback could not decimate either ({exc}); the mesh is unchanged.')
        return mesh


def _remove_floaters(mesh, ratio, warnings):
    parts = mesh.split(only_watertight=False)
    if len(parts) <= 1:
        return mesh
    import numpy as np
    import trimesh
    biggest = max(len(part.faces) for part in parts)
    kept = [part for part in parts if len(part.faces) >= max(1, biggest * ratio)]
    if len(kept) == len(parts):
        return mesh
    warnings.append(f'remove_floaters dropped {len(parts) - len(kept)} components smaller than '
                    f'{ratio:.1%} of the largest one.')
    return trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]


def _export(mesh, path, embed_textures=True):
    import trimesh
    path = Path(path)
    if path.suffix.lower() in ('.glb', '.gltf'):
        scene = trimesh.Scene(mesh)
        data = scene.export(file_type=path.suffix.lstrip('.'))
        if isinstance(data, dict):  # gltf returns a set of files
            for name, payload in data.items():
                target = path.parent / name if name != 'model.gltf' else path
                target.write_bytes(payload if isinstance(payload, bytes) else payload.encode('utf-8'))
        else:
            path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))
    else:
        mesh.export(path)
    return path


# ----------------------------------------------------------------------------- handlers

def edit(request, reporter):
    parameters = request.get('parameters') or {}
    workspace = Path(request['workspace'])
    steps = parameters.get('steps') or []
    if not steps:
        raise WorkerError('InvalidParameters', 'At least one edit step is required')

    started = time.monotonic()
    reporter.progress(4, 'Loading', 'Reading the mesh')
    mesh = _load(parameters['mesh_file'], keep_materials=parameters.get('keep_materials', True))
    before = _stats(mesh)
    warnings, applied = [], []

    for index, step in enumerate(steps):
        if not step.get('enabled', True):
            continue
        percent = 8 + (index / max(1, len(steps))) * 80
        reporter.progress(percent, step['action'], f'Step {index + 1} of {len(steps)}')
        step_started = time.monotonic()
        step_warnings = []
        mesh = _apply(mesh, step, step_warnings)
        warnings.extend(step_warnings)
        applied.append({'index': index, 'action': step['action'],
                        'seconds': round(time.monotonic() - step_started, 3),
                        'vertices': int(len(mesh.vertices)), 'faces': int(len(mesh.faces)),
                        'warnings': step_warnings})

    reporter.progress(92, 'Exporting', 'Writing the edited mesh')
    suffix = EXPORT_SUFFIX.get(parameters.get('output_format', 'glb'), '.glb')
    output = inside(workspace, 'outputs/edited' + suffix)
    _export(mesh, output)
    after = _stats(mesh)

    preview = output
    if suffix not in ('.glb', '.gltf'):
        preview = inside(workspace, 'outputs/preview.glb')
        _export(mesh, preview)

    result = {'mesh_file': str(output), 'preview_file': str(preview), 'before': before, 'after': after,
              'appliedSteps': applied, 'warnings': warnings}
    if parameters.get('report', True):
        report = inside(workspace, 'outputs/report.json')
        report.write_text(json.dumps({**result, 'seconds': round(time.monotonic() - started, 2),
                                      'parameters': parameters}, indent=2), encoding='utf-8')
        result['report_file'] = str(report)
    reporter.progress(100, 'Done', f'{after["faces"]} faces')
    return result


def convert(request, reporter):
    parameters = request.get('parameters') or {}
    workspace = Path(request['workspace'])
    reporter.progress(10, 'Loading', 'Reading the mesh')
    mesh = _load(parameters['mesh_file'])
    warnings = []
    scale = float(parameters.get('scale', 1.0))
    if scale != 1.0:
        mesh.apply_scale(scale)
    target_format = parameters.get('output_format', 'glb')
    suffix = EXPORT_SUFFIX.get(target_format, '.glb')
    if target_format in ('obj', 'ply', 'stl', 'off') and getattr(mesh.visual, 'material', None) is not None:
        warnings.append(f'{target_format.upper()} cannot carry a glTF material; textures are written beside the mesh.')
    reporter.progress(60, 'Exporting', f'Writing {suffix}')
    output = inside(workspace, 'outputs/converted' + suffix)
    _export(mesh, output, embed_textures=parameters.get('embed_textures', True))
    textures = [str(item) for item in sorted(output.parent.glob('*.png'))]
    reporter.progress(100, 'Done', output.name)
    return {'mesh_file': str(output), 'textures': textures, 'vertices': int(len(mesh.vertices)),
            'faces': int(len(mesh.faces)), 'warnings': warnings}


def inspect(request, reporter):
    """Delegates to the inspection ported from CyTools_Trellis2Texture (same engine)."""
    import pbr_worker
    if pbr_worker.MISSING_MODULE is not None:
        raise WorkerError('MissingDependency', f'Missing Python module: {pbr_worker.MISSING_MODULE}',
                          recoverable=True)
    return pbr_worker.inspect(dict(request.get('parameters') or {}))


def diagnose(request, reporter):
    from importlib.metadata import version
    report = {'python': sys.version.split()[0], 'dependencies': {}, 'status': 'Ready',
              'supportedFormats': list(MESH_SUFFIXES), 'maxFaces': MAX_FACES}
    for package in ('trimesh', 'numpy', 'scipy', 'pillow', 'xatlas'):
        try:
            report['dependencies'][package] = version(package)
        except Exception:
            report['dependencies'][package] = ''
            report['status'] = 'Incomplete'
    return report


if __name__ == '__main__':
    raise SystemExit(serve({'edit': edit, 'convert': convert, 'inspect': inspect, 'diagnose': diagnose}))
