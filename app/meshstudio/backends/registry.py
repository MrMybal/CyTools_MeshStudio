"""Every backend of the Tool: which engine runs it, which worker script, which models.

A backend is the pairing of an implementation (a worker script) with the environment
that can import it. The manifest declares the same ids in ``operations[].supportedBackends``;
this table is what turns an id into a process.
"""
from pathlib import Path

from ..paths import APP

WORKERS = APP / 'workers'


class Backend:
    def __init__(self, backend_id, *, label, engine, worker, models=(), resident_gpu=False,
                 idle_seconds=300, natives=(), note='', env=None):
        self.id = backend_id
        self.label = label
        self.engine = engine
        self.worker = worker
        self.models = tuple(models)
        self.resident_gpu = resident_gpu
        self.idle_seconds = idle_seconds
        self.natives = tuple(natives)
        self.note = note
        #: Variables the upstream code reads at import time, relative to the Tool root.
        self.env = dict(env or {})

    def worker_script(self):
        return WORKERS / self.worker

    def environment(self, root):
        """The declared variables, with their paths resolved under the Tool root."""
        import os
        return {key: str(root / value).replace('/', os.sep) if not os.path.isabs(value) else value
                for key, value in self.env.items()}

    def describe(self):
        return {'id': self.id, 'label': self.label, 'engine': self.engine, 'worker': self.worker,
                'models': list(self.models), 'residentGpu': self.resident_gpu,
                'natives': list(self.natives), 'note': self.note}


BACKENDS = {item.id: item for item in [
    # ------------------------------------------------------------------ geometry, CPU
    Backend('autoremesher', label='AutoRemesher 1.2.0 (quad remesh)', engine='geometry',
            worker='autoremesher_worker.py', natives=('autoremesher',), idle_seconds=120,
            note='Drives the official AutoRemesher program. Geometry only: UV and materials are not kept.'),
    Backend('quadwild', label='QuadWild Bi-MDF (field aligned quad remesh)', engine='geometry',
            worker='quadwild_worker.py', natives=('quadwild',), idle_seconds=120,
            note='Drives the official QuadWild Bi-MDF binaries on a triangulated mesh.'),
    Backend('xatlas', label='xatlas (UV unwrap and packing)', engine='geometry',
            worker='xatlas_worker.py', idle_seconds=300),
    Backend('pbrbake', label='PBR baking (base colour, metallic, roughness, alpha)', engine='geometry',
            worker='pbr_worker.py', idle_seconds=300,
            note='Bakes what the mesh carries into a UV atlas; channels it does not carry are derived '
                 'with documented deterministic heuristics, not invented by a model.'),
    Backend('meshedit', label='Mesh editing and inspection', engine='geometry',
            worker='meshedit_worker.py', idle_seconds=600),
    Backend('proxyfit', label='Proxy mesh fitting (cross-section loft, primitives)', engine='geometry',
            worker='proxyfit_worker.py', idle_seconds=300),

    # -------------------------------------------------------- reconstruction, CUDA 12.4
    Backend('triposr', label='TripoSR (single image to mesh)', engine='torch-cu124',
            worker='triposr_worker.py', models=('triposr', 'triposr-cache'), resident_gpu=True,
            env={'HF_HUB_CACHE': 'data/models/triposr-cache/huggingface',
                 'TORCH_HOME': 'data/models/triposr-cache/torch',
                 'U2NET_HOME': 'data/models/triposr-cache/u2net'}),
    Backend('spar3d', label='SPAR3D (image to mesh and point cloud)', engine='torch-cu124',
            worker='spar3d_worker.py', models=('spar3d', 'spar3d-cache'), resident_gpu=True,
            env={'HF_HUB_CACHE': 'data/models/spar3d-cache/huggingface',
                 'TORCH_HOME': 'data/models/spar3d-cache/torch',
                 'ALPHA_CLIP_PATH': 'data/models/spar3d-cache/alpha-clip',
                 'TRANSPARENT_BACKGROUND_FILE_PATH': 'data/models/spar3d-cache/background'}),
    Backend('unirig', label='UniRig Articulation-XL (skeleton and skinning)', engine='torch-cu124',
            worker='unirig_worker.py', models=('unirig',), resident_gpu=True),

    # ------------------------------------------------------------------ TRELLIS.2 stack
    Backend('trellis', label='LocalMesh (TRELLIS.2)', engine='trellis',
            worker='trellis_worker.py',
            models=('trellis2-4b', 'trellis-image-large', 'trellis2-4b-reconviagen',
                    'localmesh-multivue', 'dinov3-vitl16', 'birefnet-hr'),
            resident_gpu=True, idle_seconds=240),

    Backend('hi3dgen', label='Hi3DGen (normal map, then geometry)', engine='hi3dgen',
            worker='hi3dgen_worker.py',
            models=('hi3dgen-trellis-normal', 'yoso-normal-v1-8-1', 'dinov2-vitl14-reg'),
            resident_gpu=True, idle_seconds=240,
            note='Geometry only, from a TRELLIS v1 retrained on normal maps (256 grid): texture it '
                 'with texture_mesh, or refine it on the 1536 grid first.'),

    Backend('birefnet', label='BiRefNet HR (subject cut-out and camera measurement)',
            engine='trellis', worker='trellis_worker.py',
            models=('birefnet-hr', 'localmesh-multivue'), resident_gpu=True, idle_seconds=180,
            note='Shared front end: cuts the subject out of every view at a common scale and '
                 'measures where each photograph was taken from.'),

    # --------------------------------------------------------- diffusion and understanding
    Backend('zero123plus', label='Zero123++ v1.2 (synthetic views)', engine='diffusion',
            worker='views_worker.py',
            models=('zero123plus-v1.2', 'zero123plus-pipeline', 'controlnet-zp12-normal-gen-v1', 'dinov2-base'),
            resident_gpu=True, env={'HF_HOME': 'data/models/hf'}),
    Backend('mirror', label='Mirrored view (geometric, no model)', engine='diffusion',
            worker='views_worker.py', models=('dinov2-base',), idle_seconds=120,
            env={'HF_HOME': 'data/models/hf'},
            note='A geometric flip of a real photograph, only valid for a symmetric object.'),
    Backend('sam2', label='SAM 2.1 (object segmentation)', engine='diffusion',
            worker='views_worker.py',
            models=('sam2.1-hiera-base-plus', 'sam2.1-hiera-large'), resident_gpu=True,
            env={'HF_HOME': 'data/models/hf'},
            note='Segmentation is implemented by the views worker, which already owns the '
                 'framing and the same-object check.'),
    Backend('depthanything', label='Depth Anything V2 (relative depth)', engine='diffusion',
            worker='understanding_worker.py', models=('depth-anything-v2-small',), resident_gpu=True),
    Backend('perspectivefields', label='PerspectiveFields (camera estimation)', engine='diffusion',
            worker='understanding_worker.py', models=('perspective-fields-paramnet-360cities',),
            resident_gpu=True),

    # ------------------------------------------------------------------- legacy multi-view
    Backend('wonder3d', label='Wonder3D v1.0 (multi-view with normals)', engine='wonder3d',
            worker='wonder3d_worker.py', models=('wonder3d-v1.0',), resident_gpu=True),
    Backend('syncdreamer', label='SyncDreamer (16 consistent views)', engine='syncdreamer',
            worker='syncdreamer_worker.py', models=('syncdreamer',), resident_gpu=True),

    # ------------------------------------------------------------------------- human motion
    Backend('wham', label='WHAM (video to 3D human motion)', engine='wham',
            worker='wham_worker.py', models=('wham',), resident_gpu=True,
            env={'WHAM_ROOT': 'data/models/wham'},
            note='Weights and the SMPL body model are not installed yet; both need a personal '
                 'acceptance on their official pages.'),
]}


def get(backend_id):
    from cytools_core import CyToolError
    backend = BACKENDS.get(backend_id)
    if backend is None:
        raise CyToolError('InvalidParameters', f'Unknown backend "{backend_id}"')
    return backend


def for_engine(engine_name):
    return [item for item in BACKENDS.values() if item.engine == engine_name]


def describe_all():
    return [item.describe() for item in BACKENDS.values()]
