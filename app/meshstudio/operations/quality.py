"""What MeshStudio adds around LocalMesh: generated side views for its four-view path.

LocalMesh fuses four views of the subject — front, right, back, left — with a model trained to
do exactly that, but from a single picture it has to invent the back itself. Wonder3D produces
four viewpoints from one picture, 0/90/180/270 degrees around the vertical axis OF THE PICTURE.
``complete_subject`` chains the two:

1. the reference is cut out once (BiRefNet, the shared front end);
2. Wonder3D generates the six views around it;
3. the right, left and back views are given their roles, and the four are cut out again at one
   common scale, as LocalMesh wants them;
4. the subject set says which views are generated; LocalMesh measures their angles itself.

ONLY FOR A LEVEL FRONT VIEW. The first real run, an aircraft seen three-quarters from above,
showed why: Wonder3D's side views were edge-on slivers and its back view was tilted, because the
picture's vertical axis is not the aircraft's. The four views contradicted each other and the
fused shape came out deformed, while every later step followed it to 0.1 %. Declaring the angles
exact had forbidden LocalMesh to notice; they are no longer declared exact.

A generated view is a hypothesis, not a photograph: at 256 px it carries less than the real
picture, and it can be wrong. Whether four views with three generated beat one real picture is
something to compare on each subject, which is why the workflow keeps the single-picture path.
"""
import json
from pathlib import Path

from cytools_core import CyToolError

from ..paths import MODELS, ROOT
from ..engines import registry as engines
from .common import GiB, IMAGE_SUFFIXES, fit_to_card, require_file

GENERATOR_MODEL = 'wonder3d-v1.0'
#: Wonder3D's own names for its views are in the input camera's frame; the Tool's azimuth is the
#: other way round (see app/workers/wonder3d_worker.py). Roles are taken from the Tool azimuth:
#: +90 is the camera on the object's right side.
ROLE_OF_TOOL_AZIMUTH = {90.0: 'right', -90.0: 'left', 180.0: 'back'}


def _subject_front(subject_set):
    root = Path(subject_set)
    document = root / 'subject.json' if root.is_dir() else root
    if not document.is_file():
        raise CyToolError('MissingInput', f'No subject.json in "{subject_set}"; run prepare_subject first.',
                          recoverable=True)
    data = json.loads(document.read_text('utf-8'))
    front = next((Path(view['file']) for view in data.get('views', [])
                  if view.get('role') == 'front' and Path(view.get('file', '')).is_file()), None)
    if front is None:
        raise CyToolError('InvalidInput', f'The subject set in "{subject_set}" carries no front view')
    return front, data


def register(runtime, services):
    def complete_subject(context, parameters):
        engines.require('wonder3d')
        engines.require('trellis')
        if not (MODELS / GENERATOR_MODEL).is_dir():
            raise CyToolError('MissingModel', f'The {GENERATOR_MODEL} weights are not installed.',
                              recoverable=True)
        notes = []
        original = (parameters.get('image') or '').strip()
        subject_set = (parameters.get('subject_set') or '').strip()
        if subject_set:
            cut_front, _data = _subject_front(subject_set)
            if not original:
                original = str(cut_front)
        elif original:
            original = str(require_file(original, 'image', IMAGE_SUFFIXES))
            context.progress(3, currentStep='Cutting out the reference')
            first = services.run(context, 'birefnet', 'prepare_subject',
                                 {'parameters': {'front': original, 'common_framing': False,
                                                 'measure_camera': False, 'contact_sheet': False,
                                                 'gpu': parameters.get('gpu', 0)}},
                                 timeout=900, progress_offset=3.0, progress_scale=0.12)
            cut_front = Path(first['subject_set']) / 'front.png'
            if not cut_front.is_file():
                cut_front = Path(next(view['file'] for view in first['views']
                                      if view.get('role') == 'front'))
        else:
            raise CyToolError('MissingInput', 'Give the reference image, or a subject set from prepare_subject.')

        folder = Path(context.workspace) / 'outputs' / 'wonder3d'
        folder.mkdir(parents=True, exist_ok=True)
        context.progress(16, currentStep='Generating the side views with Wonder3D')
        made = services.run(context, 'wonder3d', 'generate_views', {'parameters': {
            'image': str(cut_front), 'mask': None, 'output': str(folder),
            'engine': str(ROOT / 'runtime' / 'sources' / 'Wonder3D'),
            'model': str(MODELS / GENERATOR_MODEL),
            'steps': int(parameters.get('steps') or 50), 'seed': int(parameters.get('seed', 42)),
            'guidance': float(parameters.get('guidance') or 3.0), 'device': 'cuda'}},
            timeout=3600, progress_offset=16.0, progress_scale=0.6)

        roles = {}
        for item in made.get('generated', []):
            azimuth = float(item.get('toolAzimuth', 0.0))
            azimuth = 180.0 if abs(abs(azimuth) - 180.0) < 1e-6 else azimuth
            role = ROLE_OF_TOOL_AZIMUTH.get(azimuth)
            if role and Path(item.get('image', '')).is_file():
                roles[role] = item['image']
        missing = sorted({'right', 'left', 'back'} - set(roles))
        if missing:
            raise CyToolError('BackendFailure', f'Wonder3D did not return the {", ".join(missing)} view(s).')

        context.progress(78, currentStep='Cutting the four views at one common scale')
        prepared = services.run(context, 'birefnet', 'prepare_subject', {'parameters': {
            'front': original, 'right': roles['right'], 'left': roles['left'], 'back': roles['back'],
            'common_framing': True, 'measure_camera': False, 'contact_sheet': True,
            'gpu': parameters.get('gpu', 0)}},
            timeout=900, progress_offset=78.0, progress_scale=0.18)

        document = Path(prepared['subject_file'])
        data = json.loads(document.read_text('utf-8'))
        # The poses are exact only in the frame of the input picture: Wonder3D orbits around the
        # picture's own vertical axis. For a level front view that is the object's axis; for a
        # three-quarter view from above (most presentation renders) it is not, and declaring
        # them exact made LocalMesh fuse four contradicting views into a deformed shape. The
        # engine measures the angles itself instead, and falls back to its convention.
        data['nominalAngles'] = False
        data['generator'] = GENERATOR_MODEL
        data['generatedRoles'] = ['right', 'left', 'back']
        data['generation'] = {'seed': (made.get('stats') or {}).get('seed'),
                              'steps': (made.get('stats') or {}).get('steps'),
                              'resolution': [(made.get('generated') or [{}])[0].get('width'),
                                             (made.get('generated') or [{}])[0].get('height')],
                              'projection': 'orthographic'}
        for view in data.get('views', []):
            view['generated'] = view.get('role') in data['generatedRoles']
        document.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        notes.extend(prepared.get('notes') or [])
        notes.append('Right, left and back were generated by Wonder3D around the vertical axis of the '
                     'picture. They match the object only when the picture is a level front view; '
                     'with a three-quarter or top view the fusion deforms the object: use the '
                     'single-picture workflow instead.')
        context.progress(100, currentStep='Done')
        return {'subject_set': prepared['subject_set'], 'subject_file': str(document),
                'contact_sheet': prepared.get('contact_sheet', ''), 'views': prepared.get('views', []),
                'viewCount': prepared.get('viewCount', 4), 'generated': ['right', 'left', 'back'],
                'generator': GENERATOR_MODEL, 'wonder3d_folder': str(folder), 'notes': notes}

    def estimate(parameters, backend, model):
        return fit_to_card(runtime, {'ramBytes': 12 * GiB, 'vramBytes': {'auto': 10 * GiB},
                                     'diskBytes': 1 * GiB})

    def _has_alpha(path):
        from PIL import Image
        try:
            with Image.open(path) as image:
                if image.mode not in ('RGBA', 'LA'):
                    return False
                return image.getchannel('A').getextrema()[0] < 250
        except OSError:
            return False

    def image_to_mesh_hi3dgen(context, parameters):
        """Hi3DGen from one picture: the cut-out comes from the shared front end."""
        engines.require('hi3dgen')
        subject_set = (parameters.get('subject_set') or '').strip()
        image = (parameters.get('image') or '').strip()
        if subject_set:
            cut, _data = _subject_front(subject_set)
        elif image:
            image = str(require_file(image, 'image', IMAGE_SUFFIXES))
            if _has_alpha(image):
                cut = Path(image)
            else:
                context.progress(2, currentStep='Cutting the subject out (BiRefNet)')
                first = services.run(context, 'birefnet', 'prepare_subject',
                                     {'parameters': {'front': image, 'common_framing': False,
                                                     'measure_camera': False,
                                                     'contact_sheet': False,
                                                     'gpu': parameters.get('gpu', 0)}},
                                     timeout=900, progress_offset=2.0, progress_scale=0.1)
                subject_set = first['subject_set']
                cut = Path(next(view['file'] for view in first['views'] if view.get('role') == 'front'))
        else:
            raise CyToolError('MissingInput', 'Give the picture, or a subject set from prepare_subject.')

        payload = {key: parameters[key] for key in ('seed', 'normal_resolution', 'ss_steps',
                                                    'ss_guidance', 'slat_steps', 'slat_guidance',
                                                    'origin_at_base', 'gpu') if key in parameters}
        payload['image'] = str(cut)
        result = services.run(context, 'hi3dgen', 'generate', {'parameters': payload},
                              timeout=3600, progress_offset=12.0, progress_scale=0.88)
        return {**result, 'subject_set': subject_set}

    def estimate_hi3dgen(parameters, backend, model):
        return fit_to_card(runtime, {'ramBytes': 16 * GiB, 'vramBytes': {'auto': 12 * GiB},
                                     'diskBytes': 1 * GiB})

    runtime.register('complete_subject', complete_subject, estimate=estimate)
    runtime.register('image_to_mesh_hi3dgen', image_to_mesh_hi3dgen, estimate=estimate_hi3dgen)
    return {'complete_subject': complete_subject, 'image_to_mesh_hi3dgen': image_to_mesh_hi3dgen}
