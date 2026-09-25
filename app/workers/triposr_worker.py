"""TripoSR backend: one image to a mesh in seconds, ported from CyTools_TripoSR.

The upstream code lives in ``runtime/sources/TripoSR`` and the weights in
``data/models/triposr``. What the original Tool learned is kept: the image is composited over
mid grey the way the network was trained, the texture bake queries the triplane on the device
the model is on (upstream queries it with CPU tensors and fails), and when torchmcubes was
built without CUDA kernels the result says so instead of pretending.

The loaded model stays resident between jobs: it costs about 1.6 GiB and reloading it for
every image was most of the wall clock of a short run.
"""
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, isolate_native_output, memory_report, serve  # noqa: E402

isolate_native_output()

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'runtime' / 'sources' / 'TripoSR'
MODELS = ROOT / 'data' / 'models'
MODEL_DIR = MODELS / 'triposr'
CACHE = MODELS / 'triposr-cache'
MODEL_ID = 'stabilityai/TripoSR'
MODEL_REVISION = '5b521936b01fbe1890f6f9baed0254ab6351c04a'
MAX_IMAGE_PIXELS = 16_777_216

STATE = {'model': None, 'device': ''}


def _configure(parameters):
    os.environ.setdefault('HF_HUB_CACHE', str(CACHE / 'huggingface'))
    os.environ.setdefault('TORCH_HOME', str(CACHE / 'torch'))
    # rembg keeps its background-removal ONNX weights here, not in the user profile.
    os.environ.setdefault('U2NET_HOME', str(CACHE / 'u2net'))
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
    # The process only ever sees the requested GPU, so upstream "cuda" means that device.
    os.environ['CUDA_VISIBLE_DEVICES'] = ('' if parameters.get('device') == 'cpu'
                                          else str(parameters.get('gpu_index', 0)))
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))


def _subject_image(parameters):
    """The front cut-out of a prepared subject, when the workflow supplied one."""
    import json

    folder = (parameters.get('subject_set') or '').strip()
    if not folder:
        return '', []
    document = Path(folder) / 'subject.json'
    if not document.is_file():
        raise WorkerError('MissingInput', f'No subject.json in "{folder}"; run prepare_subject first.',
                          recoverable=True)
    data = json.loads(document.read_text('utf-8'))
    front = next((item.get('file') for item in data.get('views', [])
                  if item.get('role') == 'front'), '')
    if not front or not Path(front).is_file():
        raise WorkerError('InvalidInput', f'The subject set in "{folder}" carries no front view')
    return front, ['Image taken from the prepared subject set; its background was already removed.']


def _load_image(parameters, outputs, warnings, reporter):
    import numpy as np
    from PIL import Image, ImageOps
    from tsr.utils import remove_background, resize_foreground

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    prepared, notes = _subject_image(parameters)
    warnings.extend(notes)
    source = prepared or parameters['image_file']
    with Image.open(source) as handle:
        if handle.width * handle.height > MAX_IMAGE_PIXELS:
            raise WorkerError('InvalidInput', 'Image exceeds 16 megapixels')
        image = ImageOps.exif_transpose(handle)
        image.load()

    if parameters.get('remove_background', True) and not prepared:
        reporter.progress(20, 'Removing background')
        import rembg
        image = remove_background(image, rembg.new_session())
    if image.mode == 'RGBA' and image.getextrema()[3][1] > 0:
        if not parameters.get('remove_background', True) and not prepared:
            warnings.append('Existing transparency was used to crop the foreground even though '
                            'remove_background is false.')
        image = resize_foreground(image, parameters['foreground_ratio'])
        array = np.array(image).astype(np.float32) / 255.0
        # Upstream composites the object over mid grey; the network was trained that way.
        array = array[:, :, :3] * array[:, :, 3:4] + (1 - array[:, :, 3:4]) * 0.5
        image = Image.fromarray((array * 255.0).astype(np.uint8))
    elif image.mode == 'RGBA':
        raise WorkerError('InvalidInput', 'The image is fully transparent')
    else:
        warnings.append('No alpha channel was produced; the image was used unchanged and must '
                        'already show a centred object on a plain background.')
        image = image.convert('RGB')
    preprocessed = Path(outputs) / 'preprocessed.png'
    image.save(preprocessed)
    return image, preprocessed


def _bake_on_device(mesh, model, scene_code, resolution, device):
    """Upstream's positions_to_colors queries the triplane with CPU tensors while the model is
    on CUDA, which fails. Its atlas and rasterizer are reused; only the query is placed."""
    import numpy as np
    import torch
    from tsr.bake_texture import make_atlas, rasterize_position_atlas

    padding = round(max(2, resolution / 256))
    atlas = make_atlas(mesh, resolution, padding)
    positions = rasterize_position_atlas(mesh, atlas['vmapping'], atlas['indices'],
                                         atlas['uvs'], resolution, padding)
    flat = positions.reshape(-1, 4)
    with torch.no_grad():
        queried = model.renderer.query_triplane(model.decoder,
                                                torch.tensor(flat[:, :3], device=device), scene_code)
    colors = np.insert(queried['color'].detach().cpu().numpy().reshape(-1, 3), 3, flat[:, -1], axis=1)
    colors[colors[:, -1] == 0.0] = [0, 0, 0, 0]
    return {**atlas, 'colors': colors.reshape(resolution, resolution, 4)}


def _export(parameters, mesh, model, scene_code, outputs, warnings, reporter):
    mesh_file = Path(outputs) / ('mesh.' + parameters['output_format'])
    if not parameters.get('bake_texture'):
        mesh.export(str(mesh_file))
        return mesh_file, ''
    import numpy as np
    import xatlas
    from PIL import Image

    reporter.progress(85, 'Baking the texture atlas')
    baked = _bake_on_device(mesh, model, scene_code, parameters['texture_resolution'],
                            parameters['device'])
    texture_file = Path(outputs) / 'texture.png'
    xatlas.export(str(mesh_file), mesh.vertices[baked['vmapping']], baked['indices'],
                  baked['uvs'], mesh.vertex_normals[baked['vmapping']])
    Image.fromarray((baked['colors'] * 255.0).astype(np.uint8)) \
        .transpose(Image.FLIP_TOP_BOTTOM).save(texture_file)
    warnings.append('The OBJ carries UVs but no material: assign texture.png as the base colour '
                    'map in your DCC tool.')
    return mesh_file, texture_file


def _model(device, chunk_size, reporter):
    from tsr.system import TSR

    if STATE['model'] is not None and STATE['device'] == device:
        STATE['model'].renderer.set_chunk_size(chunk_size)
        return STATE['model']
    reporter.progress(30, 'Loading the TripoSR weights')
    model = TSR.from_pretrained(str(MODEL_DIR), config_name='config.yaml', weight_name='model.ckpt')
    model.renderer.set_chunk_size(chunk_size)
    model.to(device)
    model.eval()
    STATE['model'], STATE['device'] = model, device
    return model


def image_to_mesh(request, reporter):
    parameters = dict(request.get('parameters') or {})
    workspace = Path(request['workspace'])
    _configure(parameters)

    import torch
    import torchmcubes

    device = parameters.get('device', 'cuda')
    if device == 'cuda' and not torch.cuda.is_available():
        raise WorkerError('MissingGPU', 'CUDA PyTorch and an NVIDIA GPU are required for device=cuda',
                          recoverable=True)
    if not (MODEL_DIR / 'model.ckpt').is_file():
        raise WorkerError('MissingModel', f'TripoSR weights are missing from {MODEL_DIR}',
                          recoverable=True)

    started = time.monotonic()
    warnings = []
    if device == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    else:
        warnings.append('device=cpu is an upstream capability that this Tool has not validated; '
                        'expect minutes per image.')
    torch.set_num_threads(4)
    outputs = inside(workspace, 'outputs/.keep').parent

    reporter.progress(10, 'Preparing the image')
    image, preprocessed = _load_image(parameters, outputs, warnings, reporter)
    model = _model(device, parameters['chunk_size'], reporter)
    loaded = time.monotonic()

    reporter.progress(45, 'Running the network')
    with torch.no_grad():
        scene_codes = model([image], device=device)
    if device == 'cuda':
        torch.cuda.synchronize()
    inferred = time.monotonic()

    preview_files = []
    if parameters.get('preview_views'):
        reporter.progress(55, 'Rendering previews')
        size = parameters['preview_size']
        frames = model.render(scene_codes, n_views=parameters['preview_views'],
                              height=size, width=size, return_type='pil')[0]
        for index, frame in enumerate(frames):
            path = outputs / f'preview_{index:02d}.png'
            frame.save(path)
            preview_files.append(str(path))

    reporter.progress(65, 'Extracting the isosurface')
    meshes = model.extract_mesh(scene_codes, not parameters.get('bake_texture'),
                                resolution=parameters['mc_resolution'],
                                threshold=float(parameters['density_threshold']))
    mesh = meshes[0]
    if mesh is None or len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise WorkerError('InvalidOutput', 'TripoSR returned an empty mesh; try a lower density_threshold')
    meshed = time.monotonic()

    reporter.progress(80, 'Exporting the mesh')
    mesh_file, texture_file = _export(parameters, mesh, model, scene_codes[0], outputs,
                                      warnings, reporter)
    if device == 'cuda' and not torchmcubes.HAS_CUDA:
        warnings.append('Marching cubes ran on the CPU: torchmcubes was built without CUDA kernels.')

    reporter.progress(100, 'Done', f'{len(mesh.faces)} faces')
    reporter.resident(model='triposr', gpu=device == 'cuda')
    return {
        'mesh_file': str(mesh_file), 'texture_file': str(texture_file),
        'preprocessed_image': str(preprocessed), 'preview_files': preview_files,
        'report_file': '', 'output_format': parameters['output_format'],
        'bake_texture': bool(parameters.get('bake_texture')),
        'has_vertex_colors': not parameters.get('bake_texture'),
        'vertices': int(len(mesh.vertices)), 'faces': int(len(mesh.faces)),
        'mc_resolution': parameters['mc_resolution'],
        'density_threshold': float(parameters['density_threshold']),
        'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
        'source_revision': _source_revision(), 'device': device,
        'gpu_index': parameters.get('gpu_index', 0),
        'cuda_marching_cubes': bool(torchmcubes.HAS_CUDA),
        'peak_vram_bytes': int(torch.cuda.max_memory_allocated()) if device == 'cuda' else 0,
        'load_seconds': loaded - started, 'inference_seconds': inferred - loaded,
        'mesh_seconds': meshed - inferred, 'total_seconds': time.monotonic() - started,
        'warnings': warnings,
    }


def _source_revision():
    import subprocess
    try:
        return subprocess.run(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                              if sys.platform == 'win32' else 0).stdout.strip()
    except Exception:  # noqa: BLE001
        return ''


def diagnose_backend(request, reporter):
    import importlib

    parameters = dict(request.get('parameters') or {})
    _configure(parameters)
    checks = {'source_present': (SOURCE / 'tsr/system.py').is_file(),
              'model_present': (MODEL_DIR / 'model.ckpt').is_file(),
              'model_directory': str(MODEL_DIR), 'model_revision': MODEL_REVISION,
              'source_revision': _source_revision(), 'dependencies': {},
              'optional_dependencies': {}, 'cuda_available': False,
              'cuda_marching_cubes': False, 'resident': STATE['model'] is not None}
    for name in ('torch', 'torchmcubes', 'transformers', 'omegaconf', 'einops',
                 'trimesh', 'rembg', 'imageio', 'tsr.system'):
        try:
            module = importlib.import_module(name)
            checks['dependencies'][name] = 'OK'
            if name == 'torch':
                checks['torch_version'] = module.__version__
                checks['cuda_available'] = module.cuda.is_available()
                if checks['cuda_available']:
                    checks['gpu_name'] = module.cuda.get_device_name(0)
                    checks['gpu_vram_total_bytes'] = module.cuda.get_device_properties(0).total_memory
            if name == 'torchmcubes':
                checks['cuda_marching_cubes'] = bool(getattr(module, 'HAS_CUDA', False))
        except Exception as exc:  # noqa: BLE001
            checks['dependencies'][name] = f'{type(exc).__name__}: {exc}'
    for name in ('xatlas', 'moderngl'):
        try:
            importlib.import_module(name)
            checks['optional_dependencies'][name] = 'OK'
        except Exception as exc:  # noqa: BLE001
            checks['optional_dependencies'][name] = f'{type(exc).__name__}: {exc}'
    checks['texture_baking_available'] = all(value == 'OK'
                                             for value in checks['optional_dependencies'].values())
    checks['ready_for_model_load'] = (checks['source_present'] and checks['model_present']
                                      and all(value == 'OK' for value in checks['dependencies'].values()))
    checks['note'] = ('Readiness checks imports and weights only. It does not run inference, does '
                      'not open an OpenGL context and does not prove that auxiliary downloads '
                      'succeeded.')
    checks.update(memory_report())
    return checks


def release(request, reporter):
    """Drop the resident model without killing the worker."""
    STATE['model'], STATE['device'] = None, ''
    import gc
    import torch
    gc.collect()
    torch.cuda.empty_cache()
    return {'released': True}


if __name__ == '__main__':
    raise SystemExit(serve({'image_to_mesh': image_to_mesh, 'diagnose': diagnose_backend,
                            'release': release}))
