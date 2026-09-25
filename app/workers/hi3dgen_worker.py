"""Hi3DGen backend: one picture, a normal map, then geometry (Stable-X, MIT).

Two models, run in this order:

1. StableNormal's YOSO estimator turns the cut-out into a normal map
   (``runtime/sources/StableNormal`` at its pinned revision, weights ``yoso-normal-v1-8-1``);
2. a TRELLIS v1 retrained on normal maps turns that normal map into a mesh
   (``runtime/sources/Hi3DGen``, weights ``hi3dgen-trellis-normal``), conditioned through
   DINOv2 ViT-L/14 with registers.

Upstream reaches for three things over the network while a job runs: DINOv2's code and weights
through ``torch.hub``, and StableNormal's code the same way. None of that happens here: torch.hub
is pointed at the pinned DINOv2 checkout, its weights are read from ``TORCH_HOME`` inside
``data/models``, and StableNormal is imported from its checkout. A job that would still try to
fetch something is refused with the name of what it wanted.

The input must already be cut out (an alpha channel): the operation prepares one with the shared
front end when it is given a plain photograph, so Hi3DGen's own BiRefNet is never needed.

The mesh comes out in the same frame as LocalMesh's — Y up, through the very rotation TRELLIS.2
uses — so ``refine_mesh`` and ``texture_mesh`` can take it as it is. Geometry only.
"""
import json
import os
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, isolate_native_output, serve  # noqa: E402

isolate_native_output()

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / 'runtime' / 'sources'
MODELS = ROOT / 'data' / 'models'
HI3DGEN = SOURCES / 'Hi3DGen'
STABLENORMAL = SOURCES / 'StableNormal'
DINOV2 = SOURCES / 'dinov2'
TRELLIS_NORMAL = MODELS / 'hi3dgen-trellis-normal'
YOSO = MODELS / 'yoso-normal-v1-8-1'
DINO_HOME = MODELS / 'dinov2-vitl14-reg'
DINO_WEIGHTS = DINO_HOME / 'hub' / 'checkpoints' / 'dinov2_vitl14_reg4_pretrain.pth'

STATE = {'pipeline': None, 'normals': None, 'hub': False}


def _environment():
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
    os.environ['ATTN_BACKEND'] = 'xformers'
    os.environ['SPARSE_BACKEND'] = 'spconv'
    os.environ.setdefault('SPCONV_ALGO', 'native')
    os.environ['TORCH_HOME'] = str(DINO_HOME)      # torch.hub reads its checkpoints from here
    for path in (HI3DGEN, STABLENORMAL):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _missing():
    wanted = {
        'Hi3DGen sources': HI3DGEN / 'hi3dgen' / 'pipelines' / 'hi3dgen.py',
        'StableNormal sources': STABLENORMAL / 'hubconf.py',
        'DINOv2 sources': DINOV2 / 'hubconf.py',
        'hi3dgen-trellis-normal': TRELLIS_NORMAL / 'pipeline.json',
        'yoso-normal-v1-8-1': YOSO / 'model_index.json',
        'dinov2-vitl14-reg': DINO_WEIGHTS,
    }
    return [name for name, path in wanted.items() if not path.is_file()]


def _require_installed():
    missing = _missing()
    if missing:
        raise WorkerError('MissingModel', 'Hi3DGen is not fully installed: ' + ', '.join(missing)
                          + '. Install the "hi3dgen" engine and its three models from the '
                          'Installation tab.', recoverable=True)


def _offline_hub():
    """Serve upstream's torch.hub calls from the pinned checkout, and refuse any other."""
    if STATE['hub']:
        return
    import torch

    original = torch.hub.load

    def load(repo_or_dir, model, *args, **kwargs):
        name = str(repo_or_dir).replace('\\', '/').lower()
        if 'dinov2' in name:
            kwargs.pop('source', None)
            kwargs.pop('trust_repo', None)
            return original(str(DINOV2), model, *args, source='local', **kwargs)
        raise WorkerError('BackendFailure', f'Upstream tried to fetch "{repo_or_dir}" through '
                          'torch.hub while a job was running; this Tool serves everything from '
                          'local copies.')

    torch.hub.load = load
    STATE['hub'] = True


def _pipeline(reporter):
    if STATE['pipeline'] is None:
        _offline_hub()
        reporter.progress(20, 'Loading', 'Hi3DGen normal-to-geometry model')
        from hi3dgen.pipelines import Hi3DGenPipeline

        pipeline = Hi3DGenPipeline.from_pretrained(str(TRELLIS_NORMAL))
        pipeline.cuda()
        STATE['pipeline'] = pipeline
    return STATE['pipeline']


def _normal_predictor(reporter):
    if STATE['normals'] is None:
        import importlib.util

        reporter.progress(6, 'Loading', 'StableNormal YOSO normal estimator')
        spec = importlib.util.spec_from_file_location('stablenormal_hubconf', STABLENORMAL / 'hubconf.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        STATE['normals'] = module.StableNormal_turbo(local_cache_dir=str(MODELS),
                                                     yoso_version=YOSO.name, device='cuda')
    return STATE['normals']


def _cut_out(path):
    from PIL import Image
    import numpy as np

    image = Image.open(path)
    image.load()
    if image.mode != 'RGBA' or np.all(np.asarray(image)[:, :, 3] == 255):
        raise WorkerError('InvalidInput', f'{Path(path).name} has no alpha channel. Hi3DGen needs '
                          'the subject cut out; the operation prepares one with prepare_subject.')
    return image


def generate(request, reporter):
    import numpy as np
    import torch

    parameters = dict(request.get('parameters') or {})
    workspace = Path(request['workspace'])
    _environment()
    _require_installed()
    if not torch.cuda.is_available():
        raise WorkerError('MissingGPU', 'No CUDA GPU is available for Hi3DGen', recoverable=True)
    started = time.monotonic()
    outputs = inside(workspace, 'outputs/.keep').parent
    notes = []
    seed = int(parameters.get('seed', -1))
    if seed < 0:
        seed = random.randint(0, 2 ** 31 - 1)
    torch.cuda.reset_peak_memory_stats()

    image = _cut_out(parameters['image'])
    predictor = _normal_predictor(reporter)
    pipeline = _pipeline(reporter)

    reporter.progress(30, 'Preparing', 'crop and pad around the subject')
    prepared = pipeline.preprocess_image(image, resolution=1024)
    prepared_path = outputs / 'prepared.png'
    prepared.save(prepared_path)

    reporter.progress(35, 'Normals', 'StableNormal YOSO')
    with torch.no_grad():
        normal_image = predictor(prepared, resolution=int(parameters.get('normal_resolution') or 768),
                                 match_input_resolution=True, data_type='object')
    normal_path = outputs / 'normal.png'
    normal_image.save(normal_path)
    torch.cuda.empty_cache()

    reporter.progress(50, 'Geometry', 'sparse structure, then structured latent')
    with torch.no_grad():
        result = pipeline.run(
            normal_image, seed=seed, formats=['mesh'], preprocess_image=False,
            sparse_structure_sampler_params={'steps': int(parameters.get('ss_steps') or 50),
                                             'cfg_strength': float(parameters.get('ss_guidance') or 3.0)},
            slat_sampler_params={'steps': int(parameters.get('slat_steps') or 6),
                                 'cfg_strength': float(parameters.get('slat_guidance') or 3.0)})
    reporter.progress(88, 'Exporting', 'Y-up, the frame LocalMesh uses')
    mesh = result['mesh'][0].to_trimesh(transform_pose=True)
    if parameters.get('origin_at_base', True):
        vertices = np.asarray(mesh.vertices).copy()
        vertices[:, 1] -= vertices[:, 1].min()
        mesh.vertices = vertices
    _ = mesh.vertex_normals
    mesh_path = outputs / 'mesh.glb'
    mesh.export(str(mesh_path))
    peak = torch.cuda.max_memory_allocated() / 1024 ** 3
    torch.cuda.empty_cache()

    notes.append('Geometry only: texture it with "Texture a mesh for its own topology", or '
                 'regenerate its detail on the 1536 grid first with "Refine a mesh".')
    report = {'seed': seed, 'faces': int(len(mesh.faces)), 'vertices': int(len(mesh.vertices)),
              'normalResolution': int(parameters.get('normal_resolution') or 768),
              'ssSteps': int(parameters.get('ss_steps') or 50),
              'slatSteps': int(parameters.get('slat_steps') or 6),
              'peakVramGb': round(peak, 2), 'seconds': round(time.monotonic() - started, 1),
              'notes': notes}
    report_path = outputs / 'hi3dgen-report.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    reporter.progress(100, 'Done', f'{len(mesh.faces):,} faces')
    return {'file': str(mesh_path.resolve()), 'normal_file': str(normal_path.resolve()),
            'prepared_file': str(prepared_path.resolve()), 'report': str(report_path.resolve()),
            'seed': seed, 'faces': int(len(mesh.faces)), 'vertices': int(len(mesh.vertices)),
            'peak_vram_gb': round(peak, 2), 'seconds': round(time.monotonic() - started, 1),
            'notes': notes}


def diagnose(request, reporter):
    """What is installed, without loading any weight."""
    _environment()
    report = {'python': sys.version.split()[0], 'missing': _missing(), 'imports': {}}
    for name in ('torch', 'spconv', 'xformers', 'diffusers', 'transformers', 'trimesh'):
        try:
            module = __import__(name)
            report['imports'][name] = getattr(module, '__version__', True)
        except Exception as exc:  # noqa: BLE001
            report['imports'][name] = f'{type(exc).__name__}: {exc}'
    try:
        import torch
        report['cuda'] = bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        report['cuda'] = False
    return report


if __name__ == '__main__':
    raise SystemExit(serve({'generate': generate, 'diagnose': diagnose}))
