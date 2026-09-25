"""Handlers of the model-driven operations: reconstruction, views, rigging, motion.

Each one validates its inputs, resolves the backend (the manifest lets several answer the
same operation) and hands the job to that backend's worker. The worker runs in the engine
environment of the backend; when that engine is not installed yet, ``engines.require``
raises a MissingDependency error naming the engine to install, and nothing is pretended.
"""
from pathlib import Path
import re
import unicodedata

from cytools_core import CyToolError

from ..engines import registry as engines
from ..backends import registry as backends
from .common import (GiB, MiB, IMAGE_SUFFIXES, MESH_SUFFIXES, VIDEO_SUFFIXES, fit_to_card,
                     require_file, selected_backend)

# operation -> (default backend, worker op, file fields, list fields, timeout seconds)
ROUTES = {
    'prepare_subject': ('birefnet', 'prepare_subject',
                        {'front': IMAGE_SUFFIXES, 'right': IMAGE_SUFFIXES,
                         'left': IMAGE_SUFFIXES, 'back': IMAGE_SUFFIXES}, ('images',), 900),
    'image_to_mesh_triposr': ('triposr', 'image_to_mesh', {'image_file': IMAGE_SUFFIXES}, (), 1800),
    'image_to_mesh_spar3d': ('spar3d', 'image_to_mesh', {'image_file': IMAGE_SUFFIXES}, (), 1800),
    'photos_to_mesh': ('trellis', 'generate',
                       {'front': IMAGE_SUFFIXES, 'right': IMAGE_SUFFIXES,
                        'left': IMAGE_SUFFIXES, 'back': IMAGE_SUFFIXES}, (), 5400),
    'views_generate': ('zero123plus', 'generate_views', {}, ('images',), 3600),
    'views_auto_complete': ('zero123plus', 'auto_complete_view_set', {}, ('images',), 3600),
    'views_turntable': ('zero123plus', 'turntable_views', {}, ('images',), 3600),
    'views_mirror': ('mirror', 'mirror_view', {}, ('images',), 600),
    'views_validate': ('zero123plus', 'validate_views', {}, ('images', 'candidates'), 1800),
    'segment_object': ('sam2', 'segment_object', {}, ('images',), 1200),
    'texture_mesh': ('trellis', 'texture_mesh',
                     {'mesh_file': MESH_SUFFIXES, 'detail_mesh': MESH_SUFFIXES,
                      'image': IMAGE_SUFFIXES}, (), 3600),
    'refine_mesh': ('trellis', 'refine_mesh',
                    {'mesh_file': MESH_SUFFIXES, 'image': IMAGE_SUFFIXES}, (), 5400),
    'mesh_to_rig': ('unirig', 'mesh_to_rig', {'mesh': MESH_SUFFIXES}, (), 3600),
    'video_to_motion': ('wham', 'reconstruct', {'video': VIDEO_SUFFIXES}, (), 7200),
    'video_inspect': ('wham', 'inspect_video', {'video': VIDEO_SUFFIXES}, (), 1800),
}


#: The picture a prepared subject set replaces (the manifest makes it optional accordingly).
SUBJECT_REPLACES = {'photos_to_mesh': 'front', 'image_to_mesh_triposr': 'image_file',
                    'image_to_mesh_spar3d': 'image_file'}


#: Words of a file name that give a photograph its role, in English and in French.
ROLE_WORDS = {'front': ('front', 'face', 'avant', 'devant'),
              'right': ('right', 'droite', 'droit'),
              'left': ('left', 'gauche'),
              'back': ('back', 'rear', 'dos', 'arriere', 'derriere')}


def roles_from_names(parameters):
    """Give the photographs of ``images`` their role from their file names.

    Used when a set of photographs arrives as one list — a workflow that takes a folder
    together — rather than one field per view: ``statue-front.jpg``, ``statue_droite.png``. A
    role already given in its own field is kept; without any front, the first photograph that
    has no role becomes the front, and the others stay extra views.
    """
    images = [item for item in (parameters.get('images') or []) if isinstance(item, str) and item]
    if not images or parameters.get('front'):
        return parameters
    resolved = dict(parameters)
    remaining = []
    for path in images:
        plain = unicodedata.normalize('NFKD', Path(path).stem.lower()).encode('ascii', 'ignore').decode()
        words = set(re.split(r'[^a-z0-9]+', plain))
        role = next((name for name, keys in ROLE_WORDS.items()
                     if words & set(keys) and not resolved.get(name)), None)
        if role:
            resolved[role] = path
        else:
            remaining.append(path)
    if not resolved.get('front') and remaining:
        resolved['front'] = remaining.pop(0)
    resolved['images'] = remaining
    return resolved


def _resolve_inputs(parameters, files, lists):
    resolved = dict(parameters)
    for field, suffixes in files.items():
        value = parameters.get(field)
        if not value:
            continue  # optional views; the operation's own schema says which are required
        resolved[field] = str(require_file(value, field, suffixes))
    for field in lists:
        values = parameters.get(field) or []
        if not isinstance(values, list):
            raise CyToolError('InvalidParameters', f'Parameter "{field}" must be a list')
        # A list entry is either a path or an object carrying one with its angles and role.
        entries = []
        for item in values:
            if isinstance(item, dict):
                key = next((name for name in ('file', 'image', 'path') if item.get(name)), '')
                if not key:
                    raise CyToolError('InvalidParameters',
                                      f'An entry of "{field}" carries no picture')
                entries.append({**item, key: str(require_file(item[key], field, IMAGE_SUFFIXES))})
            else:
                entries.append(str(require_file(item, field, IMAGE_SUFFIXES)))
        resolved[field] = entries
    return resolved


def register(runtime, services):
    def make(operation, route):
        default_backend, worker_op, files, lists, timeout = route

        def handler(context, parameters):
            picture = SUBJECT_REPLACES.get(operation)
            if picture and not parameters.get(picture) and not parameters.get('subject_set'):
                raise CyToolError('MissingInput', f'Give "{picture}", or a subject set prepared '
                                  'with prepare_subject.', recoverable=True)
            if operation == 'prepare_subject':
                parameters = roles_from_names(parameters)
                if not parameters.get('front'):
                    raise CyToolError('MissingInput', 'Give the front view, or photographs in "images".',
                                      recoverable=True)
            backend_id = selected_backend(context, default_backend)
            backend = backends.get(backend_id)
            script = backend.worker_script()
            if not script.is_file():
                raise CyToolError(
                    'MissingDependency',
                    f'The worker of backend "{backend_id}" is not available in this build yet '
                    f'({script.name}). See app/Docs/Architecture.md for what is ported.',
                    recoverable=False, details={'backend': backend_id, 'operation': operation})
            engines.require(backend.engine)
            payload = {'parameters': _resolve_inputs(parameters, files, lists),
                       'models': str(Path(context.runtime.data_dir).parents[0] / 'models')
                       if hasattr(context.runtime, 'data_dir') else ''}
            return services.run(context, backend_id, worker_op, payload, timeout=timeout)
        return handler

    def estimate_for(operation):
        def estimate(parameters, backend, model):
            resource = {'ramBytes': 8 * GiB, 'diskBytes': 1 * GiB}
            if operation in ('video_to_motion', 'video_inspect'):
                resource['diskBytes'] = 4 * GiB
            if operation == 'photos_to_mesh':
                tier = str(parameters.get('tier', 'standard'))
                resource['vramBytes'] = {'auto': {'draft': 8, 'standard': 10, 'high': 14,
                                                 'max': 24}.get(tier, 10) * GiB}
                resource['ramBytes'] = 16 * GiB
            elif operation == 'refine_mesh':
                grid = int(parameters.get('resolution') or 1536)
                resource['vramBytes'] = {'auto': (24 if grid >= 1536 else 14) * GiB}
                resource['ramBytes'] = 24 * GiB
            elif operation == 'texture_mesh':
                size = int(parameters.get('texture_size') or 4096)
                resource['vramBytes'] = {'auto': (14 if size >= 8192 else 10) * GiB}
                resource['ramBytes'] = 16 * GiB
            elif operation.startswith('image_to_mesh'):
                resource['vramBytes'] = {'auto': 6 * GiB if operation.endswith('triposr') else 8 * GiB}
            elif operation.startswith('views_') or operation in ('segment_object', 'analyze_views', 'construct_proxy'):
                resource['vramBytes'] = {'auto': 8 * GiB}
            elif operation in ('mesh_to_rig', 'video_to_motion'):
                resource['vramBytes'] = {'auto': 8 * GiB}
            if backend is not None and getattr(backend, 'id', '') == 'mirror':
                resource.pop('vramBytes', None)
                resource['ramBytes'] = 2 * GiB
            return fit_to_card(runtime, resource)
        return estimate

    registered = {}
    for operation, route in ROUTES.items():
        registered[operation] = make(operation, route)
        runtime.register(operation, registered[operation], estimate=estimate_for(operation))
    return registered
