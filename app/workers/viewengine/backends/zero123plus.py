"""Zero123++ v1.2 adapter.

Camera parameters come from the upstream documentation
(https://github.com/SUDO-AI-3D/zero123plus, section "Camera Parameters"):

* azimuth relative to the input view: ``30, 90, 150, 210, 270, 330``
* v1.2 elevation, absolute: ``20, -10, 20, -10, 20, -10``
* v1.2 field of view, absolute: ``30`` degrees

The sign of the azimuth direction in that table is not stated by upstream. It is
measured on this machine, recorded in ``app/backend-calibration.json`` and applied
here, so the reported poses follow this Tool's convention instead of an assumption.

The custom diffusers pipeline is not fetched from the network at run time: it is
downloaded once during the guided installation, its SHA-256 is verified and the file
is loaded from ``data/models/zero123plus-pipeline/pipeline.py``.
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

from . import base

DESCRIPTOR = {
    'id': 'zero123plus',
    'name': 'Zero123++ v1.2',
    'implemented': True,
    'source': 'https://github.com/SUDO-AI-3D/zero123plus',
    'weights': 'https://huggingface.co/sudo-ai/zero123plus-v1.2',
    'codeLicense': 'Apache-2.0',
    'weightsLicense': 'CC-BY-NC-4.0',
}
AZIMUTHS = (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)
ELEVATIONS = (20.0, -10.0, 20.0, -10.0, 20.0, -10.0)
FOV = 30.0
TILE = 320
GRID = (3, 2)


def calibration(app_dir):
    values = {'azimuthSign': 1.0, 'measured': False}
    path = Path(app_dir) / 'backend-calibration.json'
    try:
        stored = json.loads(path.read_text(encoding='utf-8-sig')).get('zero123plus', {})
    except (OSError, ValueError):
        return values
    if stored.get('azimuthSign') in (1, -1, 1.0, -1.0):
        values.update(azimuthSign=float(stored['azimuthSign']),
                      measured=bool(stored.get('measured')),
                      evidence=stored.get('evidence', ''))
    return values


def load_pipeline_module(pipeline_file):
    name = 'zero123plus_pipeline'
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(pipeline_file))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def prepare_condition(rgb, mask, *, size=512, ratio=0.95):
    """Square, recentred RGBA condition image, following the upstream example."""
    from .. import imaging
    box = imaging.bounding_box(mask)
    if box is None:
        square = imaging.resize(rgb, (size, size))
        return np.dstack([square, np.full((size, size), 255, np.uint8)])
    x, y, width, height = box
    side = int(max(width, height) / float(ratio))
    canvas = np.zeros((side, side, 4), dtype=np.uint8)
    centre = side // 2
    top, left = centre - height // 2, centre - width // 2
    canvas[top:top + height, left:left + width, :3] = rgb[y:y + height, x:x + width]
    canvas[top:top + height, left:left + width, 3] = \
        (mask[y:y + height, x:x + width] > 127).astype(np.uint8) * 255
    return imaging.resize(canvas, (size, size))


def split_grid(image):
    """Six 320x320 tiles from the 640x960 sheet, in the engine's pose order."""
    values = np.asarray(image)
    rows, columns = GRID
    height, width = values.shape[0] // rows, values.shape[1] // columns
    tiles = []
    for row in range(rows):
        for column in range(columns):
            tiles.append(values[row * height:(row + 1) * height,
                                column * width:(column + 1) * width])
    return tiles


class Backend(base.MultiViewBackend):
    id = 'zero123plus'
    elevation_absolute = True
    fov = FOV
    resolution = TILE
    parameters = ('seed', 'steps', 'guidance', 'generate_normals', 'normal_guidance',
                  'condition_ratio')
    supports_normals = True
    supports_multi_reference = False

    def __init__(self, *, model_dir, pipeline_file, controlnet_dir=None, device='cuda',
                 app_dir=None, dtype='float16', revision=''):
        self.model_dir = Path(model_dir)
        self.pipeline_file = Path(pipeline_file)
        self.controlnet_dir = None if controlnet_dir is None else Path(controlnet_dir)
        self.device = device
        self.dtype = dtype
        self.revision = str(revision or '')
        self.calibration = calibration(app_dir or Path(__file__).resolve().parents[2])
        self.offsets = tuple((self.calibration['azimuthSign'] * a, e)
                             for a, e in zip(AZIMUTHS, ELEVATIONS))
        self._pipeline = None
        self._normal_pipeline = None
        self._revision = ''

    def model_version(self):
        """The pinned repository revision of the installed weights, when it is known."""
        if not self._revision:
            self._revision = ('sudo-ai/zero123plus-v1.2@' + self.revision) if self.revision                 else 'sudo-ai/zero123plus-v1.2 (revision not recorded)'
        return self._revision

    def _load(self, normals=False):
        import copy
        import torch
        from diffusers import EulerAncestralDiscreteScheduler
        if self._pipeline is None:
            if not (self.model_dir / 'model_index.json').is_file():
                raise base.BackendUnavailable('MissingModel',
                                              'Zero123++ weights are not installed.')
            if not self.pipeline_file.is_file():
                raise base.BackendUnavailable('MissingModel',
                                              'The verified Zero123++ pipeline file is missing.')
            module = load_pipeline_module(self.pipeline_file)
            dtype = torch.float16 if self.dtype == 'float16' else torch.float32
            pipeline = module.Zero123PlusPipeline.from_pretrained(
                str(self.model_dir), torch_dtype=dtype, local_files_only=True)
            pipeline.scheduler = EulerAncestralDiscreteScheduler.from_config(
                pipeline.scheduler.config, timestep_spacing='trailing')
            pipeline.set_progress_bar_config(disable=True)
            pipeline.to(self.device, dtype)
            self._pipeline = pipeline
        if normals and self._normal_pipeline is None:
            import torch
            from diffusers import ControlNetModel
            if self.controlnet_dir is None or not (self.controlnet_dir / 'config.json').is_file():
                raise base.BackendUnavailable(
                    'MissingModel',
                    'The Zero123++ normal ControlNet is not installed; normal maps are '
                    'unavailable until it is downloaded in Installation.')
            dtype = torch.float16 if self.dtype == 'float16' else torch.float32
            normal_pipeline = copy.copy(self._pipeline)
            normal_pipeline.add_controlnet(ControlNetModel.from_pretrained(
                str(self.controlnet_dir), torch_dtype=dtype, local_files_only=True),
                conditioning_scale=1.0)
            normal_pipeline.set_progress_bar_config(disable=True)
            normal_pipeline.to(self.device, dtype)
            self._normal_pipeline = normal_pipeline
        return self._pipeline, self._normal_pipeline

    def generate(self, condition, parameters, *, progress=None, cancel=None):
        """Render the six views, and optionally their normals and matted alpha."""
        import torch
        from PIL import Image
        wants_normals = bool(parameters.get('generate_normals'))
        pipeline, normal_pipeline = self._load(wants_normals)
        if cancel:
            cancel()
        steps = int(parameters.get('steps', 36))
        guidance = float(parameters.get('guidance', 4.0))
        seed = int(parameters.get('seed', -1))
        if seed < 0:
            seed = int(torch.randint(0, 2 ** 31 - 1, (1,)).item())
        generator = torch.Generator(device=self.device).manual_seed(seed)
        image = Image.fromarray(condition)
        torch.cuda.reset_peak_memory_stats() if self.device.startswith('cuda') else None
        if progress:
            progress('Generating six views')
        sheet = pipeline(image, prompt='', guidance_scale=guidance, num_inference_steps=steps,
                         width=640, height=960, generator=generator).images[0]
        if cancel:
            cancel()
        normals_sheet = None
        if wants_normals:
            if progress:
                progress('Generating view-space normals')
            normal_guidance = float(parameters.get('normal_guidance', guidance))
            normal_generator = torch.Generator(device=self.device).manual_seed(seed)
            normals_sheet = normal_pipeline(image, depth_image=sheet, prompt='',
                                            guidance_scale=normal_guidance,
                                            num_inference_steps=steps, width=640, height=960,
                                            generator=normal_generator).images[0]
            if cancel:
                cancel()
        colours, normals, alphas = split_grid(sheet), None, None
        if normals_sheet is not None:
            colours, normals, alphas = self._matte(sheet, normals_sheet)
        peak = 0.0
        if self.device.startswith('cuda'):
            peak = torch.cuda.max_memory_allocated() / 1024 ** 3
        return {'views': colours, 'normals': normals, 'alphas': alphas, 'seed': seed,
                'steps': steps, 'guidance': guidance, 'peakVramGiB': round(float(peak), 3),
                'sheet': np.asarray(sheet)}

    @staticmethod
    def _matte(sheet, normals_sheet):
        """Upstream matting post-process: alpha from the normal magnitude, then closed form."""
        from pymatting.alpha.estimate_alpha_cf import estimate_alpha_cf
        from scipy.ndimage import binary_erosion
        vectors = np.asarray(normals_sheet, dtype=np.float64) / 255.0 * 2 - 1
        magnitude = np.linalg.norm(vectors, axis=-1)
        structure = np.ones((4, 4), dtype=np.uint8)
        foreground = binary_erosion(magnitude > 0.6, structure=structure)
        background = binary_erosion(magnitude < 0.2, structure=structure, border_value=1)
        trimap = np.full(magnitude.shape, 128, dtype=np.uint8)
        trimap[foreground] = 255
        trimap[background] = 0
        alpha = estimate_alpha_cf(np.asarray(sheet, dtype=np.float64) / 255.0,
                                  trimap.astype(np.float64) / 255.0)
        unit = vectors / (np.linalg.norm(vectors, axis=-1, keepdims=True) + 1e-8)
        # Outside the object the predicted direction is meaningless, so the upstream
        # post-process fades it to flat 0.5 grey using the matted alpha.
        faded = (unit * 0.5 + 0.5) * alpha[..., None] + 0.5 * (1.0 - alpha[..., None])
        shaded = np.clip(faded * 255, 0, 255).astype(np.uint8)
        alpha_image = np.clip(alpha * 255, 0, 255).astype(np.uint8)
        return (split_grid(np.asarray(sheet)), split_grid(shaded), split_grid(alpha_image))

    def release(self):
        self._pipeline = None
        self._normal_pipeline = None
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
