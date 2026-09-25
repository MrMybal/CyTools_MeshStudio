#!/usr/bin/env python
"""One-shot SyncDreamer runner (single image -> 16 consistent views).

Contract
--------
stdin : ONE JSON object {"parameters": {...}}
stdout: EXACTLY ONE JSON object (result or {"error": {...}})
stderr: every diagnostic, including everything upstream prints.

Generation parameters
    image      abs path of an RGB / RGBA picture                      (required)
    mask       abs path of a mask, white = object                     (optional)
    output     abs output directory                                   (required)
    engine     abs path of the SyncDreamer checkout                   (required)
    model      abs path of the folder holding syncdreamer-pretrain.ckpt
               and ViT-L-14.pt                                        (required)
    elevation  elevation of the INPUT view, degrees (default 30)
    steps      DDIM steps (default 50)
    seed       int (default 6033, the upstream default)
    guidance   classifier free guidance scale (default 2.0)
    crop_size  object size inside the 256x256 conditioning image (default 200,
               -1 = upstream "do not crop" mode)
    device     "cuda" or "cuda:N"
    batch_view_num  views denoised together (default 8 like upstream; halved
               automatically after a CUDA out-of-memory)

Diagnose: {"parameters": {"task": "diagnose"}}

The upstream source tree is used as is (no file of it is modified). The only
runtime adaptation is an instance-level wrapper around the sampler's
``denoise_apply`` used to publish progress.

Camera convention of the 16 generated views (read from upstream
``meta_info/camera-16.pkl`` and checked on real outputs): view k sits at the
upstream azimuth k*22.5 deg relative to the input view, elevation 30 deg,
distance 1.5, 35 mm lens on a 32 mm sensor (fov 49.13 deg). Upstream azimuth
grows when the camera moves to ITS OWN RIGHT (counter-clockwise seen from
above, Blender Z-up). The Tool convention is the opposite ("+" = the camera
moves towards the object's right side = to the camera's left), hence
generatorAzimuth = -k*22.5 wrapped to (-180, 180].
"""
import json
import math
import os
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _protocol import isolate_native_output, serve  # noqa: E402
from _legacy import legacy_handler  # noqa: E402

isolate_native_output()
import time
import traceback

CKPT_NAME = 'syncdreamer-pretrain.ckpt'
CLIP_NAME = 'ViT-L-14.pt'
TARGET_ELEVATION_DEG = 30.0  # fixed by upstream get_viewpoint_embedding / camera-16.pkl
AZIMUTH_SIGN = -1.0          # upstream azimuth -> Tool azimuth (see module docstring)


class RunnerError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- io
def _take_over_stdout():
    """Keep the real stdout for the final JSON; send every other write to stderr."""
    sys.stdout.flush()
    real = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return real


def _emit(fd, obj):
    data = (json.dumps(obj, allow_nan=False) + '\n').encode('utf-8')
    while data:
        data = data[os.write(fd, data):]


def log(*parts):
    print('[syncdreamer]', *parts, file=sys.stderr, flush=True)


_last_progress = [0.0]


def note(output, percent, step, force=True):
    """Best effort progress file, written atomically."""
    now = time.time()
    if not force and now - _last_progress[0] < 0.25:
        return
    _last_progress[0] = now
    try:
        target = os.path.join(output, 'progress.json')
        temp = target + '.tmp'
        with open(temp, 'w', encoding='utf-8') as handle:
            json.dump({'percent': int(max(0, min(100, round(percent)))), 'step': step}, handle)
        os.replace(temp, target)
    except OSError:
        pass


# --------------------------------------------------------------------- diagnose
def diagnose():
    import platform
    info = {'python': platform.python_version(), 'executable': sys.executable, 'platform': platform.platform()}
    missing = []
    for label, module in (('torch', 'torch'), ('torchvision', 'torchvision'), ('pytorch_lightning', 'pytorch_lightning'),
                          ('numpy', 'numpy'), ('omegaconf', 'omegaconf'), ('einops', 'einops'), ('kornia', 'kornia'),
                          ('transformers', 'transformers'), ('taming', 'taming'), ('clip', 'clip'), ('cv2', 'cv2'),
                          ('skimage', 'skimage'), ('PIL', 'PIL')):
        try:
            loaded = __import__(module)
            info[label] = str(getattr(loaded, '__version__', 'installed'))
        except Exception as exc:  # noqa: BLE001 - a broken package is a diagnosis, not a crash
            info[label] = None
            missing.append('%s (%s)' % (module, exc))
    info['missing'] = missing
    info['cudaAvailable'] = False
    try:
        import torch
        info['cudaAvailable'] = bool(torch.cuda.is_available())
        info['cudaRuntime'] = torch.version.cuda
        if info['cudaAvailable']:
            index = torch.cuda.current_device()
            free, total = torch.cuda.mem_get_info(index)
            info['devices'] = [{'index': i, 'name': torch.cuda.get_device_name(i),
                                'capability': '.'.join(map(str, torch.cuda.get_device_capability(i)))}
                               for i in range(torch.cuda.device_count())]
            info['freeVramBytes'] = int(free)
            info['totalVramBytes'] = int(total)
    except Exception as exc:  # noqa: BLE001
        info['cudaError'] = str(exc)
    return {'diagnose': info}


# ------------------------------------------------------------- conditioning image
def _border_background_mask(rgb):
    """Foreground mask for an opaque picture: the background is every region whose colour is
    close to the border colour AND which is connected to the image border."""
    import cv2
    import numpy as np
    height, width = rgb.shape[:2]
    band = max(2, min(height, width) // 64)
    border = np.concatenate([rgb[:band].reshape(-1, 3), rgb[-band:].reshape(-1, 3),
                             rgb[:, :band].reshape(-1, 3), rgb[:, -band:].reshape(-1, 3)]).astype(np.float32)
    colour = np.median(border, 0)
    spread = float(np.percentile(np.linalg.norm(border - colour, axis=1), 95))
    tolerance = max(18.0, 3.0 * spread)
    close = (np.linalg.norm(rgb.astype(np.float32) - colour, axis=2) <= tolerance).astype(np.uint8)
    count, labels = cv2.connectedComponents(close, connectivity=4)
    touching = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    touching = touching[touching != 0]  # label 0 = pixels that are NOT close to the border colour
    background = np.isin(labels, touching) & (close == 1)
    foreground = (~background).astype(np.uint8)
    # drop specks smaller than 0.02 % of the picture
    count, labels, stats, _ = cv2.connectedComponentsWithStats(foreground, connectivity=8)
    minimum = max(16, int(0.0002 * height * width))
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] < minimum:
            foreground[labels == index] = 0
    log('border background removal: colour=%s tolerance=%.1f foreground=%.2f%%'
        % (colour.round(1).tolist(), tolerance, 100.0 * foreground.mean()))
    return foreground * 255


def build_rgba(image_path, mask_path, output):
    """Returns the path of an RGBA picture (alpha = object mask), the form upstream expects."""
    import numpy as np
    from PIL import Image
    picture = Image.open(image_path)
    picture.load()
    source = None
    if mask_path:
        mask = Image.open(mask_path).convert('L')
        if mask.size != picture.size:
            mask = mask.resize(picture.size, Image.BILINEAR)
        alpha = np.asarray(mask)
        source = 'mask'
    elif picture.mode in ('RGBA', 'LA', 'PA') or (picture.mode == 'P' and 'transparency' in picture.info):
        alpha = np.asarray(picture.convert('RGBA'))[:, :, 3]
        if alpha.min() < 250:
            source = 'alpha'
    if source is None:
        alpha = _border_background_mask(np.asarray(picture.convert('RGB')))
        source = 'border-colour'
    alpha = np.where(alpha > 127, alpha, 0).astype(np.uint8) if source != 'border-colour' else alpha.astype(np.uint8)
    if int((alpha > 0).sum()) < 64:
        raise RunnerError('GenerationFailed', 'The object mask is empty (source: %s); provide a mask or a picture with a plain background.' % source)
    rgba = np.dstack([np.asarray(picture.convert('RGB')), alpha])
    path = os.path.join(output, 'input_rgba.png')
    Image.fromarray(rgba, 'RGBA').save(path)
    return path, source


# ------------------------------------------------------------------- generation
def _is_oom(exc):
    return 'out of memory' in str(exc).lower()


def generate(p):
    for key in ('image', 'output', 'engine', 'model'):
        if not p.get(key):
            raise RunnerError('GenerationFailed', 'Missing parameter: %s' % key)
    image_path, output = os.path.abspath(p['image']), os.path.abspath(p['output'])
    engine, model_dir = os.path.abspath(p['engine']), os.path.abspath(p['model'])
    mask_path = os.path.abspath(p['mask']) if p.get('mask') else None
    elevation = float(p.get('elevation', 30.0) if p.get('elevation') is not None else 30.0)
    steps = int(p.get('steps') or 50)
    seed = int(p['seed']) if p.get('seed') is not None else 6033
    guidance = float(p['guidance']) if p.get('guidance') is not None else 2.0
    crop_size = int(p['crop_size']) if p.get('crop_size') is not None else 200
    batch_view_num = max(1, min(16, int(p.get('batch_view_num') or 8)))
    device_name = str(p.get('device') or 'cuda')

    os.makedirs(output, exist_ok=True)
    note(output, 0, 'Starting SyncDreamer')
    ckpt_path, clip_path = os.path.join(model_dir, CKPT_NAME), os.path.join(model_dir, CLIP_NAME)
    config_path = os.path.join(engine, 'configs', 'syncdreamer.yaml')
    for path in (image_path, mask_path, config_path, os.path.join(engine, 'meta_info', 'camera-16.pkl')):
        if path and not os.path.isfile(path):
            raise RunnerError('GenerationFailed', 'File not found: %s' % path)
    for path in (ckpt_path, clip_path):
        if not os.path.isfile(path):
            raise RunnerError('MissingDependency', 'Model file not found: %s' % path)
    if not 1 <= steps <= 1000:
        raise RunnerError('GenerationFailed', 'steps must be within 1..1000')

    import numpy as np
    import torch
    if not device_name.startswith('cuda'):
        raise RunnerError('DeviceUnavailable', 'SyncDreamer has only been validated on CUDA (requested device: %s).' % device_name)
    if not torch.cuda.is_available():
        raise RunnerError('DeviceUnavailable', 'CUDA is not available in this environment (torch %s).' % torch.__version__)
    index = int(device_name.split(':', 1)[1]) if ':' in device_name else 0
    if index >= torch.cuda.device_count():
        raise RunnerError('DeviceUnavailable', 'CUDA device %d does not exist.' % index)
    torch.cuda.set_device(index)
    device = torch.device('cuda', index)

    # upstream reads meta_info/camera-16.pkl relative to the working directory
    os.chdir(engine)
    sys.dont_write_bytecode = True  # keep the pinned checkout free of __pycache__ folders
    sys.path.insert(0, engine)
    from omegaconf import OmegaConf
    from PIL import Image
    from ldm.base_utils import read_pickle
    from ldm.models.diffusion.sync_dreamer import SyncDDIMSampler, SyncMultiviewDiffusion
    from ldm.util import instantiate_from_config, prepare_inputs

    note(output, 2, 'Preparing the conditioning image')
    rgba_path, mask_source = build_rgba(image_path, mask_path, output)
    data = prepare_inputs(rgba_path, elevation, crop_size)  # upstream preprocessing, unchanged
    conditioning = os.path.join(output, 'conditioning.png')
    Image.fromarray(((data['input_image'].numpy() + 1.0) * 127.5).round().clip(0, 255).astype(np.uint8)).save(conditioning)

    note(output, 5, 'Loading the SyncDreamer model')
    started = time.time()
    # same steps as upstream generate.load_model, with the CLIP path taken from the model folder
    config = OmegaConf.load(config_path)
    config.model.params.clip_image_encoder_path = clip_path
    model = instantiate_from_config(config.model)
    log('loading model from', ckpt_path)
    checkpoint = torch.load(ckpt_path, map_location='cpu')
    model.load_state_dict(checkpoint['state_dict'], strict=True)
    del checkpoint
    if not isinstance(model, SyncMultiviewDiffusion):
        raise RunnerError('GenerationFailed', 'Unexpected model class: %s' % type(model).__name__)
    model = model.to(device).eval()
    load_seconds = time.time() - started
    log('model loaded in %.1fs' % load_seconds)

    batch = {key: value.unsqueeze(0).to(device) for key, value in data.items()}  # ONE sample
    torch.cuda.reset_peak_memory_stats(device)
    started = time.time()
    attempts = []
    while True:
        torch.random.manual_seed(seed)
        np.random.seed(seed)
        sampler = SyncDDIMSampler(model, steps)
        total = int(sampler.ddim_timesteps.shape[0])
        state = {'done': 0}
        original = sampler.denoise_apply

        def wrapped(*args, _original=original, _state=state, _total=total, **kwargs):
            result = _original(*args, **kwargs)
            _state['done'] += 1
            note(output, 10 + 82.0 * _state['done'] / _total, 'Denoising step %d/%d' % (_state['done'], _total),
                 force=_state['done'] == _total)
            return result

        sampler.denoise_apply = wrapped  # instance attribute only: upstream files stay untouched
        note(output, 10, 'Denoising step 0/%d' % total)
        attempts.append(batch_view_num)
        try:
            x_sample = model.sample(sampler, batch, guidance, batch_view_num)
            break
        except RuntimeError as exc:
            if not _is_oom(exc) or batch_view_num == 1:
                raise
            log('CUDA out of memory with batch_view_num=%d, retrying with %d' % (batch_view_num, batch_view_num // 2))
            del exc
            batch_view_num //= 2
            torch.cuda.empty_cache()
    torch.cuda.synchronize(device)
    sample_seconds = time.time() - started

    note(output, 94, 'Writing the generated views')
    x_sample = (torch.clamp(x_sample, max=1.0, min=-1.0) + 1) * 0.5
    x_sample = (x_sample.permute(0, 1, 3, 4, 2).cpu().numpy() * 255).astype(np.uint8)[0]  # N,H,W,3

    K, azimuths, elevations, distances, _ = read_pickle(os.path.join(engine, 'meta_info', 'camera-%d.pkl' % model.view_num))
    size = int(x_sample.shape[2])
    fov = math.degrees(2.0 * math.atan(0.5 * 256.0 / float(K[0, 0])))  # K is expressed for 256 px renders
    generated = []
    for view in range(x_sample.shape[0]):
        path = os.path.join(output, 'view_%02d.png' % view)
        Image.fromarray(x_sample[view]).save(path)
        upstream = math.degrees(float(azimuths[view] - azimuths[0]))
        azimuth = (AZIMUTH_SIGN * upstream + 180.0) % 360.0 - 180.0
        if azimuth == -180.0:
            azimuth = 180.0
        generated.append({'image': path, 'index': view, 'generatorAzimuth': round(azimuth, 4) + 0.0,
                          'upstreamAzimuth': round(upstream % 360.0, 4), 'elevation': round(math.degrees(float(elevations[view])), 4),
                          'fov': round(fov, 4), 'distance': round(float(distances[view]), 4)})
    strip = os.path.join(output, 'views_strip.png')  # same layout as upstream output/<name>/0.png
    Image.fromarray(np.concatenate(list(x_sample), 1)).save(strip)

    stats = {'model': 'syncdreamer', 'device': '%s (%s)' % (device, torch.cuda.get_device_name(index)), 'steps': steps, 'seed': seed,
             'guidance': guidance, 'cropSize': crop_size, 'inputElevation': elevation, 'batchViewNum': batch_view_num,
             'batchViewNumAttempts': attempts, 'maskSource': mask_source, 'imageSize': size,
             'loadSeconds': round(load_seconds, 3), 'sampleSeconds': round(sample_seconds, 3),
             'peakVramBytes': int(torch.cuda.max_memory_allocated(device)),
             'peakVramReservedBytes': int(torch.cuda.max_memory_reserved(device)),
             'conditioningImage': conditioning, 'strip': strip,
             'torch': torch.__version__, 'azimuthConvention': 'generatorAzimuth = -upstreamAzimuth; + = camera towards the object right side'}
    note(output, 100, 'SyncDreamer complete')
    return {'generated': generated, 'stats': stats}


def _execute(parameters):
    """The upstream runner, reached through one entry point like the other ported workers."""
    if parameters.get('task') == 'diagnose':
        return diagnose()
    return generate(parameters)


if __name__ == '__main__':
    handler = legacy_handler(_execute)
    raise SystemExit(serve({'generate_views': handler, 'diagnose': handler}))
