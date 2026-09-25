"""PBR baking backend: base colour, metallic, roughness and alpha into a UV atlas.

Ported from CyTools_Trellis2Texture, keeping its derivation constants (app/workers/pbr_config.py)
and its isolated xatlas process. The one-shot stdin/stdout entry point is replaced by the
persistent JSON-lines protocol so that a bake can stream its progress and be cancelled.
"""
import contextlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import serve  # noqa: E402
from pbr_config import (CAVITY_FORMULA, MAX_FACES, MAX_MESH_BYTES, MESH_SUFFIXES, METALLIC_FORMULA,
                        ROUGHNESS_FORMULA, UNWRAP_TIMEOUT_SECONDS, WORKERS, mesh_root)

try:  # diagnose must still report which module is missing.
    import numpy as np
    import pbrmaps
    MISSING_MODULE = None
except ModuleNotFoundError as exc:
    np = pbrmaps = None
    MISSING_MODULE = exc.name

SRGB_NOTE = ('Base colour is resampled in its stored sRGB encoding; roughness, metallic and cavity '
             'derivations read those sRGB values directly and are heuristics, not measurements.')


def diagnose():
    report, available = {}, set()
    for name in ('numpy', 'trimesh', 'scipy', 'PIL', 'xatlas'):
        try:
            report[name] = str(getattr(__import__(name), '__version__', 'unknown'))
            available.add(name)
        except Exception as exc:
            report[name] = f'{type(exc).__name__}: {exc}'
    return {'python_version': platform.python_version(), 'platform': f'{platform.system()} {platform.machine()}',
            'dependencies': report, 'xatlas_available': 'xatlas' in available,
            'ready_for_generation': len(available) == len(report), 'mesh_root': str(mesh_root()),
            'supported_extensions': list(MESH_SUFFIXES), 'max_faces': MAX_FACES, 'max_mesh_bytes': MAX_MESH_BYTES,
            'note': 'Readiness checks imports and limits only; it does not prove a successful bake.'}


def load_mesh(path):
    import trimesh
    warnings = []
    loaded = trimesh.load(path, process=False)
    if isinstance(loaded, trimesh.Scene):
        geometries = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not geometries:
            raise ValueError('The file contains no triangle mesh')
        if len(geometries) > 1:
            warnings.append(f'{len(geometries)} geometries merged into one mesh and one texture atlas.')
        mesh, count = loaded.to_mesh(), len(geometries)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh, count = loaded, 1
    else:
        raise ValueError(f'Unsupported geometry type: {type(loaded).__name__}')
    if len(mesh.faces) == 0 or len(mesh.vertices) == 0:
        raise ValueError('The mesh has no triangle')
    if len(mesh.faces) > MAX_FACES:
        raise ValueError(f'The mesh has {len(mesh.faces)} faces; the limit is {MAX_FACES}')
    return mesh, count, warnings


def read_texture(image):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 67_108_864
    if image.width * image.height > Image.MAX_IMAGE_PIXELS:
        raise ValueError('The source texture exceeds 64 megapixels')
    return np.asarray(image.convert('RGBA'), np.float32) / 255.0


def scalar_factor(material, name, fallback):
    value = getattr(material, name, None) if material is not None else None
    return fallback if value is None else float(np.asarray(value).ravel()[0])


def colour_factor(material):
    """glTF stores baseColorFactor in 0..1; trimesh may hand it back as 0..255 integers."""
    value = getattr(material, 'baseColorFactor', None) if material is not None else None
    if value is None:
        return np.ones(4, np.float32)
    array = np.asarray(value)
    scale = 255.0 if array.dtype.kind in 'iu' else 1.0
    return np.clip(np.resize(array.astype(np.float32).ravel(), 4) / scale, 0.0, 1.0)


def describe_material(mesh):
    """Normalise every supported visual into one description; nothing is invented here."""
    visual = mesh.visual
    material = getattr(visual, 'material', None)
    if material is not None and not hasattr(material, 'baseColorTexture') and hasattr(material, 'to_pbr'):
        material = material.to_pbr()
    uv = getattr(visual, 'uv', None)
    uv = None if uv is None or len(uv) != len(mesh.vertices) else np.asarray(uv, np.float64)
    colours = None
    if getattr(visual, 'kind', None) == 'vertex':
        colours = np.asarray(visual.vertex_colors, np.float32)[:, :4] / 255.0
    return {'material': material, 'material_type': type(material).__name__ if material is not None else 'none',
            'uv': uv, 'vertex_colours': colours,
            'base_texture': getattr(material, 'baseColorTexture', None) if material is not None else None,
            'mr_texture': getattr(material, 'metallicRoughnessTexture', None) if material is not None else None,
            'base_factor': colour_factor(material), 'metallic_factor': scalar_factor(material, 'metallicFactor', 0.0),
            'roughness_factor': scalar_factor(material, 'roughnessFactor', 1.0)}


def colour_source(description):
    if description['base_texture'] is not None and description['uv'] is not None:
        return 'texture'
    if description['vertex_colours'] is not None:
        return 'vertex_colors'
    if description['material'] is not None and getattr(description['material'], 'baseColorFactor', None) is not None:
        return 'base_color_factor'
    return 'none'


def recommended_resolution(faces):
    for limit, resolution in ((5_000, 512), (50_000, 1024), (300_000, 2048)):
        if faces < limit:
            return resolution
    return 4096


def inspect(parameters):
    mesh, geometry_count, warnings = load_mesh(parameters['mesh_file'])
    description = describe_material(mesh)
    uv = description['uv']
    source = colour_source(description)
    texture_size = list(description['base_texture'].size) if description['base_texture'] is not None else []
    has_alpha = False
    if source == 'texture':
        has_alpha = bool(description['base_texture'].convert('RGBA').getextrema()[3][0] < 255)
    elif source == 'vertex_colors':
        has_alpha = bool(description['vertex_colours'][:, 3].min() < 1.0)
    if source == 'none':
        warnings.append('The mesh carries no colour: base colour will be the flat fallback grey.')
    if uv is None:
        warnings.append('No UV coordinates: uv_mode=auto unwraps with xatlas, or with the built-in grid unwrapper if xatlas fails.')
    elif not (uv.min() >= -1e-6 and uv.max() <= 1 + 1e-6):
        warnings.append('UV coordinates leave the unit square; texels outside [0,1] are wrapped.')
    return {'vertices': int(len(mesh.vertices)), 'faces': int(len(mesh.faces)), 'geometry_count': geometry_count,
            'file_bytes': int(Path(parameters['mesh_file']).stat().st_size),
            'is_watertight': bool(mesh.is_watertight),
            'bounds': [float(v) for v in np.asarray(mesh.bounds).ravel()],
            'extents': [float(v) for v in np.asarray(mesh.extents).ravel()],
            'has_uv': uv is not None, 'uv_in_unit_square': bool(uv is not None and uv.min() >= -1e-6 and uv.max() <= 1 + 1e-6),
            'material_type': description['material_type'], 'color_source': source,
            'has_vertex_colors': description['vertex_colours'] is not None,
            'has_base_color_texture': description['base_texture'] is not None,
            'base_color_texture_size': [int(v) for v in texture_size],
            'has_metallic_roughness_texture': description['mr_texture'] is not None, 'has_alpha': has_alpha,
            'recommended': {'uv_mode': 'keep' if uv is not None else 'unwrap',
                            'resolution': recommended_resolution(len(mesh.faces)),
                            'alpha_mode': 'from_source' if has_alpha else 'opaque'},
            'warnings': warnings}


def run_xatlas(vertices, faces, workspace):
    """Unwrap in a child process; a native abort becomes a return code, not a dead worker."""
    folder = Path(workspace) / 'input'
    folder.mkdir(parents=True, exist_ok=True)
    source, target = folder / 'unwrap_in.npz', folder / 'unwrap_out.npz'
    np.savez(source, vertices=vertices.astype(np.float32), faces=faces.astype(np.uint32))
    try:
        completed = subprocess.run([sys.executable, str(WORKERS / 'unwrap.py'), str(source), str(target)],
                                   cwd=WORKERS, capture_output=True, text=True, shell=False,
                                   timeout=UNWRAP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return None, f'xatlas exceeded {UNWRAP_TIMEOUT_SECONDS} seconds'
    if completed.returncode != 0 or not target.is_file():
        detail = (completed.stderr or '').strip().splitlines()
        return None, f'xatlas failed with exit code {completed.returncode}' + (f': {detail[-1]}' if detail else '')
    data = np.load(target)
    return (data['mapping'], data['faces'], data['uv']), None


def prepare_uv(mesh, description, parameters, attributes, workspace, warnings):
    """Return (vertices, faces, uv, attributes, uv_source). Unwrapping splits seam vertices."""
    existing, uv_mode = description['uv'], parameters['uv_mode']
    vertices, faces = np.asarray(mesh.vertices, np.float64), np.asarray(mesh.faces, np.int64)
    if uv_mode == 'keep':
        if existing is None:
            raise ValueError('uv_mode=keep requires the mesh to carry UV coordinates')
        return vertices, faces, existing, attributes, 'existing'
    if uv_mode == 'auto' and existing is not None:
        return vertices, faces, existing, attributes, 'existing'
    atlas, source = (None, 'grid') if uv_mode == 'grid' else (run_xatlas(vertices, faces, workspace), 'xatlas')
    if source == 'xatlas':
        atlas, failure = atlas
        if atlas is None:
            warnings.append(f'{failure}; fell back to the built-in grid unwrapper, '
                            'which never overlaps but wastes texels and adds a seam per triangle.')
            source = 'grid'
    if source == 'grid':
        atlas = pbrmaps.grid_unwrap(faces, parameters['resolution'], parameters['padding_pixels'])
        cell = parameters['resolution'] / np.ceil(np.sqrt(len(faces)))
        if cell < 8:
            warnings.append(f'Grid unwrap leaves about {cell:.1f} texels per triangle; '
                            'raise resolution or simplify the mesh for a usable base colour map.')
    mapping, indices, uvs = np.asarray(atlas[0], np.int64), np.asarray(atlas[1], np.int64), np.asarray(atlas[2], np.float64)
    return (vertices[mapping], indices, uvs,
            {name: value[mapping] for name, value in attributes.items()}, source)


def generate(parameters, workspace, reporter=None):
    from PIL import Image
    import trimesh

    def step(percent, name, message=''):
        if reporter is not None:
            reporter.progress(percent, name, message)

    started = time.monotonic()
    resolution = parameters['resolution']
    mesh, _, warnings = load_mesh(parameters['mesh_file'])
    description = describe_material(mesh)
    source = colour_source(description)
    if source == 'none':
        warnings.append('The mesh carries no colour; base colour falls back to flat 0.8 grey.')

    attributes = {'cavity': pbrmaps.vertex_cavity(mesh.vertices, mesh.faces, mesh.vertex_normals)[:, None]}
    if description['uv'] is not None:
        attributes['source_uv'] = description['uv']
    if description['vertex_colours'] is not None:
        attributes['vertex_colours'] = description['vertex_colours']
    step(12, 'UV', 'Preparing the UV layout')
    vertices, faces, uv, attributes, uv_source = prepare_uv(mesh, description, parameters, attributes,
                                                            workspace, warnings)
    loaded = time.monotonic()

    step(30, 'Rasterising', f'{resolution}x{resolution} atlas')
    face_index, barycentric = pbrmaps.rasterize(uv, faces, resolution)
    stamped = pbrmaps.stamp_missing_faces(uv, faces, face_index, barycentric)
    covered = face_index >= 0
    if not covered.any():
        raise ValueError('The UV layout covers no texel; try a higher resolution or uv_mode=unwrap')
    if stamped:
        warnings.append(f'{stamped} triangles were smaller than one texel and were stamped on a single texel.')

    rgba = np.zeros((resolution, resolution, 4), np.float32)
    rgba[..., 3] = 1.0
    if source == 'texture':
        texture = read_texture(description['base_texture'])
        sampled_uv = pbrmaps.interpolate(attributes['source_uv'], faces, face_index, barycentric)
        rgba[covered] = pbrmaps.sample_image(texture, sampled_uv[covered])
        rgba *= description['base_factor']
    elif source == 'vertex_colors':
        rgba[covered] = pbrmaps.interpolate(attributes['vertex_colours'], faces, face_index, barycentric)[covered]
    elif source == 'base_color_factor':
        rgba[covered] = description['base_factor']
    else:
        rgba[covered] = (0.8, 0.8, 0.8, 1.0)

    step(55, 'Base colour', f'Colour source: {source}')
    alpha_source = rgba[..., 3].copy()
    if parameters['cavity_delight'] > 0.0:
        cavity = pbrmaps.interpolate(attributes['cavity'], faces, face_index, barycentric)[..., 0]
        rgba[..., :3] = pbrmaps.apply_cavity_delight(rgba[..., :3], cavity, parameters['cavity_delight'])

    metallic_roughness = None
    if 'source' in (parameters['metallic_mode'], parameters['roughness_mode']):
        if description['mr_texture'] is not None and 'source_uv' in attributes:
            sampled_uv = pbrmaps.interpolate(attributes['source_uv'], faces, face_index, barycentric)
            metallic_roughness = np.zeros((resolution, resolution, 4), np.float32)
            metallic_roughness[covered] = pbrmaps.sample_image(read_texture(description['mr_texture']), sampled_uv[covered])
        else:
            warnings.append('No metallic-roughness texture on the source mesh; the declared factors were used instead.')

    if parameters['metallic_mode'] == 'source':
        metallic = (metallic_roughness[..., 2] * description['metallic_factor'] if metallic_roughness is not None
                    else np.full((resolution, resolution), description['metallic_factor'], np.float32))
    elif parameters['metallic_mode'] == 'estimate':
        metallic = pbrmaps.derive_metallic(rgba[..., :3], parameters['metallic_value'])
    else:
        metallic = np.full((resolution, resolution), parameters['metallic_value'], np.float32)

    if parameters['roughness_mode'] == 'source':
        roughness = (metallic_roughness[..., 1] * description['roughness_factor'] if metallic_roughness is not None
                     else np.full((resolution, resolution), description['roughness_factor'], np.float32))
    elif parameters['roughness_mode'] == 'estimate':
        roughness = pbrmaps.derive_roughness(rgba[..., :3], parameters['roughness_value'], covered)
    else:
        roughness = np.full((resolution, resolution), parameters['roughness_value'], np.float32)

    if parameters['alpha_mode'] == 'opaque':
        alpha = np.ones((resolution, resolution), np.float32)
    elif parameters['alpha_mode'] == 'from_coverage':
        alpha = covered.astype(np.float32)
    else:
        alpha = alpha_source
        if int(pbrmaps.to_uint8(alpha)[covered].min()) == 255:
            warnings.append('alpha_mode=from_source but the source is fully opaque; the alpha map is uniform white.')

    step(72, 'Channels', 'Metallic, roughness and alpha')
    padding = parameters['padding_pixels']
    if uv_source == 'grid':
        # Grid cells are only a few texels wide; a larger ring would bleed into the next triangle.
        usable = int(max(0.0, resolution / np.ceil(np.sqrt(len(faces))) * 0.25))
        if padding > usable:
            warnings.append(f'padding_pixels reduced from {padding} to {usable}: '
                            'grid cells cannot hold a wider ring without bleeding into their neighbour.')
            padding = usable
    index = pbrmaps.nearest_fill(covered, padding)
    padded = index >= 0
    rgb = pbrmaps.pad_map(rgba[..., :3], index)
    metallic = pbrmaps.pad_map(metallic, index)
    roughness = pbrmaps.pad_map(roughness, index)
    if parameters['alpha_mode'] != 'from_coverage':
        alpha = pbrmaps.pad_map(alpha, index)

    outputs = Path(workspace) / 'outputs'
    outputs.mkdir(parents=True, exist_ok=True)
    base_rgba = np.dstack([pbrmaps.to_uint8(rgb), pbrmaps.to_uint8(alpha)])
    files = {'base_color_file': ('base_color.png', base_rgba),
             'metallic_file': ('metallic.png', pbrmaps.to_uint8(metallic)),
             'roughness_file': ('roughness.png', pbrmaps.to_uint8(roughness)),
             'alpha_file': ('alpha.png', pbrmaps.to_uint8(alpha)),
             'metallic_roughness_file': ('metallic_roughness.png', np.dstack([
                 np.full((resolution, resolution), 255, np.uint8),
                 pbrmaps.to_uint8(roughness), pbrmaps.to_uint8(metallic)]))}
    result = {}
    for key, (name, array) in files.items():
        Image.fromarray(array).save(outputs / name, optimize=True)
        result[key] = str(outputs / name)

    material_mesh_file = ''
    # Keep a private preview with the baked UVs even when public GLB export is disabled.
    transparent = parameters['alpha_mode'] != 'opaque' and int(base_rgba[..., 3].min()) < 255
    material = trimesh.visual.material.PBRMaterial(
        name='CyTools_MeshStudio', baseColorTexture=Image.fromarray(base_rgba),
        metallicRoughnessTexture=Image.fromarray(files['metallic_roughness_file'][1]),
        metallicFactor=1.0, roughnessFactor=1.0, alphaMode='BLEND' if transparent else 'OPAQUE',
        doubleSided=bool(not mesh.is_watertight))
    exported = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    exported.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
    preview_mesh_file = str(outputs / ('material.glb' if parameters['export_glb'] else 'preview.glb'))
    material_mesh_file = preview_mesh_file if parameters['export_glb'] else ''
    exported.export(preview_mesh_file, include_normals=True)

    import psutil
    memory = psutil.Process().memory_info()
    result.update({
        'material_mesh_file': material_mesh_file, 'report_file': str(outputs / 'report.json'),
        'resolution': resolution, 'vertices': int(len(vertices)), 'faces': int(len(faces)),
        'uv_source': uv_source, 'color_source': source, 'padding_pixels': padding,
        'metallic_mode': parameters['metallic_mode'],
        'roughness_mode': parameters['roughness_mode'], 'alpha_mode': parameters['alpha_mode'],
        'texel_coverage': float(covered.mean()), 'padded_coverage': float(padded.mean()),
        'stamped_faces': stamped, 'source_texture_size': list(description['base_texture'].size)
        if description['base_texture'] is not None else [],
        'worker_memory_bytes': int(getattr(memory, 'peak_wset', memory.rss)),
        'memory_measurement': 'peak_working_set' if hasattr(memory, 'peak_wset') else 'rss_at_completion',
        'formulas': {'roughness': ROUGHNESS_FORMULA, 'metallic': METALLIC_FORMULA, 'cavity_delight': CAVITY_FORMULA},
        'color_space_note': SRGB_NOTE, 'warnings': warnings,
        'timings': {'load_seconds': loaded - started, 'bake_seconds': time.monotonic() - loaded,
                    'total_seconds': time.monotonic() - started}})
    Path(result['report_file']).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return result


def _handler_generate(request, reporter):
    parameters = dict(request.get('parameters') or {})
    reporter.progress(3, 'Loading', 'Reading the mesh and its materials')
    result = generate(parameters, request['workspace'], reporter=reporter)
    reporter.progress(100, 'Done', 'Maps written')
    return result


def _handler_inspect(request, reporter):
    if MISSING_MODULE is not None:
        raise ModuleNotFoundError(name=MISSING_MODULE)
    return inspect(dict(request.get('parameters') or {}))


def _handler_diagnose(request, reporter):
    return diagnose()


if __name__ == '__main__':
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(serve({'generate_pbr': _handler_generate, 'inspect': _handler_inspect,
                            'diagnose': _handler_diagnose}))
