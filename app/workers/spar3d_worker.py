"""SPAR3D backend: one image to a textured mesh and its point cloud, ported from CyTools_SPAR3D.

The upstream code lives in ``runtime/sources/SPAR3D`` and the weights in ``data/models/spar3d``;
the auxiliary models (Alpha-CLIP, transparent-background, DINOv2) are in ``data/models/spar3d-cache``.

Two checks from the original Tool are kept because they turn an unreadable crash into a
sentence: CUDA must be available, and ``texture_baker`` must have been built with its CUDA
kernel — without it the bake fails deep inside C++. The model stays resident between jobs.
"""
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, isolate_native_output, memory_report, serve  # noqa: E402

isolate_native_output()

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'runtime' / 'sources' / 'SPAR3D'
MODELS = ROOT / 'data' / 'models'
MODEL_DIR = MODELS / 'spar3d'
CACHE = MODELS / 'spar3d-cache'
MODEL_ID = 'stabilityai/stable-point-aware-3d'

STATE = {'model': None, 'low_vram': None}


def _configure(parameters):
    os.environ.setdefault('HF_HUB_CACHE', str(CACHE / 'huggingface'))
    os.environ.setdefault('TORCH_HOME', str(CACHE / 'torch'))
    os.environ.setdefault('ALPHA_CLIP_PATH', str(CACHE / 'alpha-clip'))
    os.environ.setdefault('TRANSPARENT_BACKGROUND_FILE_PATH', str(CACHE / 'background'))
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ['NO_ALBUMENTATIONS_UPDATE'] = '1'
    os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
    os.environ['CUDA_VISIBLE_DEVICES'] = str(parameters.get('gpu_index', 0))
    os.environ.pop('SPAR3D_USE_CPU', None)
    os.environ.pop('SPAR3D_LOW_VRAM', None)
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))
    # Upstream resolves several of its own assets relative to the checkout.
    os.chdir(SOURCE)


def _source_revision():
    import subprocess
    try:
        return subprocess.run(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                              if sys.platform == 'win32' else 0).stdout.strip()
    except Exception:  # noqa: BLE001
        return ''


def _subject_image(parameters):
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


def _model(low_vram, reporter):
    from spar3d.system import SPAR3D

    if STATE['model'] is not None and STATE['low_vram'] == bool(low_vram):
        return STATE['model']
    reporter.progress(25, 'Loading the SPAR3D weights')
    model = SPAR3D.from_pretrained(str(MODEL_DIR), config_name='config.yaml',
                                   weight_name='model.safetensors',
                                   low_vram_mode=bool(low_vram)).to('cuda').eval()
    STATE['model'], STATE['low_vram'] = model, bool(low_vram)
    return model


def image_to_mesh(request, reporter):
    parameters = dict(request.get('parameters') or {})
    workspace = Path(request['workspace'])
    _configure(parameters)

    import random
    import numpy as np
    import torch
    from PIL import Image, ImageOps
    from spar3d.models.mesh import TRIANGLE_REMESH_AVAILABLE, QUAD_REMESH_AVAILABLE
    from spar3d.utils import foreground_crop, remove_background

    if not torch.cuda.is_available():
        raise WorkerError('MissingGPU', 'CUDA PyTorch and an NVIDIA GPU are required', recoverable=True)
    # The operator only exists once its extension is imported, so ask afterwards.
    import texture_baker  # noqa: F401
    if not torch._C._dispatch_has_kernel_for_dispatch_key('texture_baker_cpp::rasterize', 'CUDA'):
        raise WorkerError('MissingDependency',
                          'texture_baker was built without its CUDA kernel; reinstall the '
                          'torch-cu124 engine so it is compiled against the CUDA redistributables.',
                          recoverable=True)
    if not (MODEL_DIR / 'model.safetensors').is_file():
        raise WorkerError('MissingModel', f'SPAR3D weights are missing from {MODEL_DIR}',
                          recoverable=True)

    remesh = parameters.get('remesh') or 'none'
    if (remesh == 'triangle' and not TRIANGLE_REMESH_AVAILABLE) or \
            (remesh == 'quad' and not QUAD_REMESH_AVAILABLE):
        raise WorkerError('MissingDependency', f'The optional {remesh} remesher is not installed',
                          recoverable=True)

    started = time.monotonic()
    seed = int(parameters.get('seed', 42))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()

    outputs = inside(workspace, 'outputs/.keep').parent
    warnings = []
    prepared, notes = _subject_image(parameters)
    warnings.extend(notes)

    reporter.progress(8, 'Preparing the image')
    Image.MAX_IMAGE_PIXELS = 16_777_216
    with Image.open(prepared or parameters['image_file']) as handle:
        if handle.width * handle.height > Image.MAX_IMAGE_PIXELS:
            raise WorkerError('InvalidInput', 'Image exceeds 16 megapixels')
        image = ImageOps.exif_transpose(handle).convert('RGBA')
    if parameters.get('remove_background', True) and not prepared and image.getextrema()[3][0] == 255:
        reporter.progress(15, 'Removing the background')
        from transparent_background import Remover
        image = remove_background(image, Remover(device='cuda'))
    if image.getextrema()[3][1] == 0:
        raise WorkerError('InvalidInput', 'The image is fully transparent')
    image = foreground_crop(image, parameters['foreground_ratio'])
    preprocessed = outputs / 'preprocessed.png'
    image.save(preprocessed)

    model = _model(parameters.get('low_vram'), reporter)
    loaded = time.monotonic()

    reporter.progress(45, 'Reconstructing', f'texture {parameters["texture_resolution"]} px')
    # An explicit autocast context follows the official inference entry point.
    with torch.no_grad(), torch.autocast(device_type='cuda', dtype=torch.bfloat16):
        mesh, auxiliary = model.run_image(image,
                                          bake_resolution=parameters['texture_resolution'],
                                          remesh=remesh,
                                          vertex_count=parameters.get('target_vertices', -1),
                                          return_points=True)
    if mesh is None or len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise WorkerError('InvalidOutput', 'SPAR3D returned an empty mesh')

    reporter.progress(88, 'Exporting')
    mesh_file = outputs / 'mesh.glb'
    points_file = outputs / 'points.ply'
    mesh.export(str(mesh_file), include_normals=True)
    auxiliary['point_clouds'][0].export(str(points_file))
    torch.cuda.synchronize()
    if remesh == 'quad':
        warnings.append('GLB exports triangles, including after quad remeshing.')

    reporter.progress(100, 'Done', f'{len(mesh.faces)} faces')
    reporter.resident(model='spar3d', gpu=True)
    return {
        'mesh_file': str(mesh_file), 'point_cloud_file': str(points_file),
        'preprocessed_image': str(preprocessed), 'report_file': '',
        'vertices': int(len(mesh.vertices)), 'faces': int(len(mesh.faces)),
        'remesh': remesh, 'export_topology': 'triangles', 'model_id': MODEL_ID,
        'model_revision': '', 'source_revision': _source_revision(), 'seed': seed,
        'gpu_index': parameters.get('gpu_index', 0),
        'peak_vram_bytes': int(torch.cuda.max_memory_allocated()),
        'load_seconds': loaded - started, 'total_seconds': time.monotonic() - started,
        'warnings': warnings,
    }


def diagnose_backend(request, reporter):
    import importlib

    parameters = dict(request.get('parameters') or {})
    _configure(parameters)
    checks = {'source_present': (SOURCE / 'spar3d/system.py').is_file(),
              'model_present': (MODEL_DIR / 'model.safetensors').is_file(),
              'model_directory': str(MODEL_DIR), 'source_revision': _source_revision(),
              'dependencies': {}, 'cuda_available': False, 'native_cuda_baker': False,
              'resident': STATE['model'] is not None}
    for name in ('torch', 'torchvision', 'safetensors', 'transparent_background',
                 'texture_baker', 'uv_unwrapper', 'spar3d.system'):
        try:
            module = importlib.import_module(name)
            if name == 'texture_baker':
                getattr(module, 'TextureBaker')
            if name == 'uv_unwrapper':
                getattr(module, 'Unwrapper')
            checks['dependencies'][name] = 'OK'
            if name == 'torch':
                checks['cuda_available'] = module.cuda.is_available()
                checks['torch_version'] = module.__version__
                if checks['cuda_available']:
                    checks['gpu_name'] = module.cuda.get_device_name(0)
        except Exception as exc:  # noqa: BLE001
            checks['dependencies'][name] = f'{type(exc).__name__}: {exc}'
    try:
        import torch
        import texture_baker  # noqa: F401 - registers the operator asked about below
        checks['native_cuda_baker'] = torch._C._dispatch_has_kernel_for_dispatch_key(
            'texture_baker_cpp::rasterize', 'CUDA')
    except Exception:  # noqa: BLE001
        pass
    try:
        from spar3d.models.mesh import TRIANGLE_REMESH_AVAILABLE, QUAD_REMESH_AVAILABLE
        checks['remesh'] = {'triangle': TRIANGLE_REMESH_AVAILABLE, 'quad': QUAD_REMESH_AVAILABLE}
    except Exception:  # noqa: BLE001
        checks['remesh'] = {'triangle': False, 'quad': False}
    checks['ready_for_model_load'] = (checks['source_present'] and checks['model_present']
                                      and checks['cuda_available'] and checks['native_cuda_baker']
                                      and all(value == 'OK' for value in checks['dependencies'].values()))
    checks['note'] = 'Readiness does not verify auxiliary model caches or a complete reconstruction.'
    checks.update(memory_report())
    return checks


def release(request, reporter):
    STATE['model'], STATE['low_vram'] = None, None
    import gc
    import torch
    gc.collect()
    torch.cuda.empty_cache()
    return {'released': True}


if __name__ == '__main__':
    raise SystemExit(serve({'image_to_mesh': image_to_mesh, 'diagnose': diagnose_backend,
                            'release': release}))
