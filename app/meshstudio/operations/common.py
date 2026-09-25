"""Shared services for the handlers: worker pool, backend selection, outputs."""
from pathlib import Path
import re

from cytools_core import CyToolError

from ..paths import APP, LOGS, ROOT, base_python
from ..engines import registry as engines
from ..engines.workerhost import WorkerHost, WorkerPool
from ..backends import registry as backends

MiB = 1024 ** 2
GiB = 1024 ** 3
MESH_SUFFIXES = ('.glb', '.gltf', '.obj', '.ply', '.stl', '.off')
IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff')
VIDEO_SUFFIXES = ('.mp4', '.mov', '.mkv', '.avi', '.webm')


class Services:
    """One persistent worker per backend, reused across jobs and released with the runtime."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.pool = WorkerPool(runtime)

    def host(self, backend_id):
        backend = backends.get(backend_id)

        def factory():
            if backend.engine:
                info = engines.require(backend.engine)
                python = Path(info['python'])
                env = engines.worker_environment(backend.engine)
            else:
                python = base_python()
                env = engines.base_environment()
            env.update(backend.environment(ROOT))
            return WorkerHost(backend_id, [python, backend.worker_script()], cwd=APP, env=env,
                              log_path=LOGS / f'worker-{backend_id}.log',
                              idle_seconds=backend.idle_seconds, startup_timeout=300)
        return self.pool.get(backend_id, factory)

    def run(self, context, backend_id, op, payload, *, timeout=None,
            progress_offset=0.0, progress_scale=1.0):
        backend = backends.get(backend_id)
        host = self.host(backend_id)
        if backend.resident_gpu:
            # A 24 GiB card cannot hold two reconstruction models at once.
            self.pool.make_exclusive(backend_id)
        payload = dict(payload)
        payload.setdefault('workspace', str(context.workspace))
        return host.run_job(context, op, payload, timeout=timeout,
                            progress_offset=progress_offset, progress_scale=progress_scale)


def fit_to_card(runtime, resource):
    """Keep a VRAM reservation within what the scheduler can ever grant.

    The Core measures each card's free memory once, when the runtime starts, and refuses any
    reservation above it with "No GPU fits the requested reservation". A job that wants the
    whole card — LocalMesh's max tier, a refinement on the 1536 grid — asked for 24 GiB on a
    24 GiB card that Windows already uses 3 GiB of, and could therefore never start. Such a job
    reserves the whole card instead; the engine itself then checks the card it needs (the tier
    guard) and sizes its work on the memory really available (the token ceiling).
    """
    wanted = (resource.get('vramBytes') or {}).get('auto')
    if not wanted:
        return resource
    try:
        capacity = max(runtime.ledger.capacity.get('vramBytes', {}).values(), default=0)
    except Exception:  # noqa: BLE001
        capacity = 0
    if capacity and wanted > capacity:
        resource = dict(resource)
        resource['vramBytes'] = {'auto': int(capacity)}
    return resource


def selected_backend(context, default=''):
    """The backendId chosen for this job (JobContext exposes no accessor for it)."""
    try:
        with context.runtime._cv:
            return context.runtime._jobs[context.job_id].get('backendId') or default
    except Exception:
        return default


def require_file(path, field='input', suffixes=MESH_SUFFIXES):
    if not path:
        raise CyToolError('MissingInput', f'Parameter "{field}" is required')
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise CyToolError('MissingInput', f'File not found for "{field}": {path}', recoverable=True)
    if suffixes and candidate.suffix.lower() not in suffixes:
        raise CyToolError('InvalidInput',
                          f'Unsupported extension for "{field}": {candidate.suffix}. '
                          f'Expected one of {", ".join(suffixes)}')
    return candidate.resolve()


def safe_name(name, fallback='output'):
    cleaned = re.sub(r'[^A-Za-z0-9._ -]+', '_', str(name or '')).strip(' ._')
    return cleaned[:120] or fallback
