"""xatlas backend: UV unwrapping and repacking.

Ported from CyTools_Xatlas. The native library exposes no progress of its own, so the
stages around it are reported. Unlike the original one-shot worker, this one stays alive
between jobs, so the progress file it used is replaced by protocol events.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, serve  # noqa: E402

MAX_BYTES = 256 * 1024 ** 2
MAX_TRIANGLES = 2_000_000
SUFFIXES = ('.obj', '.ply', '.stl', '.glb', '.gltf', '.off')


def _load(source):
    import numpy as np
    import trimesh
    if source.suffix.lower() not in SUFFIXES:
        raise WorkerError('InvalidParameters', f'Unsupported extension {source.suffix}; expected one of {", ".join(SUFFIXES)}')
    if not source.is_file():
        raise WorkerError('MissingInput', f'File not found: {source}', recoverable=True)
    if source.stat().st_size > MAX_BYTES:
        raise WorkerError('InvalidParameters', f'File larger than {MAX_BYTES // 1024 ** 2} MiB')
    mesh = trimesh.load(source, force='mesh', process=False, skip_materials=True)
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint32)
    if len(vertices) < 3 or len(faces) == 0 or len(faces) > MAX_TRIANGLES or not np.isfinite(vertices).all():
        raise WorkerError('InvalidMesh',
                          f'Empty, non finite or oversized mesh ({MAX_TRIANGLES} triangles maximum)')
    if faces.max() >= len(vertices):
        raise WorkerError('InvalidMesh', 'Face indices point outside the vertex array')
    areas = np.linalg.norm(np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]],
                                    vertices[faces[:, 2]] - vertices[faces[:, 0]]), axis=1)
    if np.any(areas < 1e-15):
        raise WorkerError('InvalidMesh', 'Degenerate triangles: clean the mesh before unwrapping')
    return mesh, vertices, faces


def _atlas(operation, mesh, vertices, faces, parameters):
    import numpy as np
    import xatlas
    atlas = xatlas.Atlas()
    if operation == 'repack':
        uv = getattr(mesh.visual, 'uv', None)
        if uv is None or len(uv) != len(vertices) or not np.isfinite(uv).all():
            raise WorkerError('InvalidMesh', 'Repacking needs per-vertex UV (an OBJ with vt entries)')
        atlas.add_uv_mesh(np.asarray(uv, dtype=np.float32), faces)
    else:
        atlas.add_mesh(vertices, faces)
    chart = xatlas.ChartOptions()
    chart.max_iterations = parameters['iterations']
    chart.max_cost = parameters['maxCost']
    chart.fix_winding = parameters['fixWinding']
    pack = xatlas.PackOptions()
    pack.resolution = parameters['resolution']
    pack.padding = parameters['padding']
    pack.bruteForce = parameters['bruteForce']
    pack.rotate_charts = parameters['rotateCharts']
    pack.blockAlign = parameters['blockAlign']
    pack.bilinear = True
    atlas.generate(chart_options=chart, pack_options=pack, verbose=False)
    if atlas.atlas_count != 1:
        raise WorkerError('InvalidOutput', 'Several atlases were generated: raise the resolution')
    return atlas


def unwrap(request, reporter):
    import numpy as np
    from PIL import Image, ImageDraw

    parameters = request.get('parameters') or {}
    operation = request.get('mode', 'unwrap')
    workspace = Path(request['workspace'])
    source = Path(parameters['input'])

    reporter.progress(5, 'Loading', f'Reading {source.name}')
    mesh, vertices, faces = _load(source)
    reporter.log(f'Input: {len(vertices)} vertices, {len(faces)} triangles')

    reporter.progress(25, 'Packing', 'xatlas is running (it exposes no internal progress)')
    atlas = _atlas(operation, mesh, vertices, faces, parameters)
    mapping, atlas_faces, uv = atlas[0]
    if not np.isfinite(uv).all() or np.any(uv < 0) or np.any(uv > 1):
        raise WorkerError('InvalidOutput', 'xatlas returned UV outside the unit square')

    reporter.progress(80, 'Exporting', 'Writing the mesh, the mapping and the atlas preview')
    output = inside(workspace, 'outputs/mesh.obj')
    normals = np.asarray(mesh.vertex_normals, dtype=np.float32)[mapping]
    with output.open('w', encoding='utf-8') as stream:
        stream.write('# CyTools_MeshStudio - geometry and UV; materials are not transferred\n')
        for row in vertices[mapping]:
            stream.write('v ' + ' '.join(map(str, row)) + '\n')
        for row in uv:
            stream.write('vt ' + ' '.join(map(str, row)) + '\n')
        for row in normals:
            stream.write('vn ' + ' '.join(map(str, row)) + '\n')
        for row in atlas_faces + 1:
            stream.write('f ' + ' '.join(f'{index}/{index}/{index}' for index in row) + '\n')

    mapping_path = inside(workspace, 'outputs/mapping.npz')
    np.savez_compressed(mapping_path, vertex_mapping=mapping, faces=atlas_faces, uv=uv)

    scale = min(1.0, 2048 / max(atlas.width, atlas.height))
    width = max(1, int(atlas.width * scale))
    height = max(1, int(atlas.height * scale))
    image = Image.new('RGB', (width, height), '#121d2c')
    draw = ImageDraw.Draw(image)
    for triangle in uv[atlas_faces]:
        points = [(float(x) * (width - 1), (1 - float(y)) * (height - 1)) for x, y in triangle]
        draw.polygon(points, fill='#244d62', outline='#57dec3')
    preview = inside(workspace, 'outputs/atlas.png')
    image.save(preview)

    result = {'mesh': str(output), 'preview': str(preview), 'mapping': str(mapping_path),
              'report': str(inside(workspace, 'outputs/report.json')),
              'vertices': int(len(mapping)), 'triangles': int(len(atlas_faces)),
              'charts': int(atlas.get_mesh_chart_count(0)), 'width': int(atlas.width),
              'height': int(atlas.height), 'utilization': float(atlas.utilization)}
    Path(result['report']).write_text(json.dumps({**result, 'operation': operation,
                                                  'parameters': parameters}, indent=2), encoding='utf-8')
    reporter.progress(100, 'Done', f'{result["charts"]} charts, {result["utilization"]:.1%} of the atlas used')
    return result


def repack(request, reporter):
    return unwrap({**request, 'mode': 'repack'}, reporter)


def diagnose(request, reporter):
    from importlib.metadata import version
    report = {'engine': 'xatlas', 'python': sys.version.split()[0], 'modelsRequired': False,
              'status': 'Ready', 'dependencies': {}}
    for package in ('xatlas', 'trimesh', 'numpy', 'pillow', 'scipy'):
        try:
            report['dependencies'][package] = version(package)
        except Exception:
            report['dependencies'][package] = ''
            report['status'] = 'Incomplete'
    report['version'] = report['dependencies'].get('xatlas', '')
    return report


if __name__ == '__main__':
    raise SystemExit(serve({'unwrap': unwrap, 'repack': repack, 'diagnose': diagnose}))
