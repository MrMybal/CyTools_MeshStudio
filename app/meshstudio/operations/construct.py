"""Proxy construction: understanding, optional view synthesis, then deterministic fitting.

Ported from the orchestration of CyTools_MeshConstruct. Three processes take turns, and the
order matters: the models supply masks, relative depth and camera cues, a generator fills the
viewpoints the photographs never covered, and only then does the fitting engine — which
imports no model at all — build the geometry.

Nothing here loads a model: each stage is a job on its backend's worker.
"""
import json
from pathlib import Path

from cytools_core import CyToolError

from ..paths import MODELS, ROOT
from ..engines import registry as engines
from .common import IMAGE_SUFFIXES, require_file

MAX_IMAGE_BYTES = 64 * 1024 ** 2

# Sign that maps a generator azimuth onto this Tool's convention (camera towards the
# object's right side = +), plus what each generator needs. Measured by CyTools_MeshConstruct.
GENERATORS = {
    'zero123plus-v1.2': {'sign': -1.0, 'relative_elevation': False, 'backend': 'zero123plus',
                         'operation': 'synthesize', 'steps': 36, 'guidance': 4.0, 'vram': 7.0},
    'wonder3d-v1.0': {'sign': -1.0, 'relative_elevation': True, 'backend': 'wonder3d',
                      'operation': 'generate_views', 'steps': 50, 'guidance': 3.0, 'vram': 8.0,
                      'rig_refine': False, 'weight_factor': 0.67},
    'syncdreamer': {'sign': 1.0, 'relative_elevation': False, 'backend': 'syncdreamer',
                    'operation': 'generate_views', 'steps': 50, 'guidance': 2.0, 'vram': 10.0},
}

UNDERSTANDING_KEYS = ('images', 'generated_views', 'segmentation_model', 'depth_model',
                      'camera_model', 'device', 'view_synthesis', 'view_synthesis_model',
                      'synthesis_source', 'synthesis_steps', 'synthesis_seed',
                      'synthesis_guidance', 'synthesis_coverage_threshold', 'subject_set')

FAMILY_MODELS = {
    'segmentation': ('sam2.1-hiera-large', 'sam2.1-hiera-base-plus'),
    'depth': ('depth-anything-v2-small',),
    'camera': ('perspective-fields-paramnet-360cities',),
}


def _installed(model_id):
    return (MODELS / model_id).is_dir() and any((MODELS / model_id).iterdir())


def _resolve(family, requested):
    """Which model of a family this run uses: the one asked for, the best installed, or none."""
    if requested in ('none', ''):
        return None
    if requested and requested != 'auto':
        return requested if _installed(requested) else None
    return next((item for item in FAMILY_MODELS[family] if _installed(item)), None)


def _check_image(path):
    candidate = Path(path)
    if candidate.suffix.lower() not in IMAGE_SUFFIXES:
        raise CyToolError('InvalidInput', f'Unsupported picture format: {candidate.name}')
    if not candidate.is_file():
        raise CyToolError('MissingInput', f'File not found: {candidate}', recoverable=True)
    if candidate.stat().st_size > MAX_IMAGE_BYTES:
        raise CyToolError('InvalidInput', f'{candidate.name} exceeds 64 MiB')
    return str(candidate.resolve())


def _views_from(parameters):
    """The view list the fitting engine expects, built from the declared pictures."""
    views = []
    for index, item in enumerate(parameters.get('images') or []):
        image = item.get('image') if isinstance(item, dict) else item
        if not image:
            raise CyToolError('InvalidParameters', f'images[{index}] carries no picture')
        entry = {'name': f"r{index:02d}_{Path(image).stem}"[:40], 'image': _check_image(image),
                 'kind': 'real', 'azimuth': 0.0, 'elevation': 0.0, 'fov': 30}
        if isinstance(item, dict):
            for key, field in (('azimuth', 'azimuth'), ('elevation', 'elevation'), ('fov', 'fov'),
                               ('label', 'label'), ('weight', 'weight'), ('box', 'box')):
                if item.get(field) is not None:
                    entry[key] = item[field]
            if item.get('mask'):
                entry.update(mask=_check_image(item['mask']), maskMethod='user mask',
                             maskConfidence=0.97)
        views.append(entry)
    if not views:
        raise CyToolError('InvalidParameters', 'At least one picture is required')

    for index, item in enumerate(parameters.get('generated_views') or []):
        source = int(item.get('source', 0))
        if source >= len(views):
            raise CyToolError('InvalidParameters',
                              f'generated_views[{index}].source refers to a missing picture')
        entry = {'name': f"g{index:02d}_{Path(item['image']).stem}"[:40],
                 'image': _check_image(item['image']), 'kind': 'generated',
                 'sourceViews': [views[source]['name']],
                 'relativeAzimuth': item['relative_azimuth'], 'elevation': item['elevation'],
                 'fov': item.get('fov', 30), 'azimuth': 0.0,
                 'requested': [item['relative_azimuth'], item['elevation']]}
        if item.get('weight'):
            entry['weight'] = item['weight']
        if item.get('mask'):
            entry.update(mask=_check_image(item['mask']), maskMethod='user mask', maskConfidence=0.9)
        views.append(entry)
    return views


def _subject_views(parameters, views):
    """Use the cut-outs of a prepared subject as the masks of the real views."""
    folder = (parameters.get('subject_set') or '').strip()
    if not folder:
        return []
    document = Path(folder) / 'subject.json'
    if not document.is_file():
        raise CyToolError('MissingInput', f'No subject.json in "{folder}"; run prepare_subject first.',
                          recoverable=True)
    data = json.loads(document.read_text('utf-8'))
    cutouts = [item for item in data.get('views', []) if Path(item.get('file', '')).is_file()]
    notes = []
    for view, item in zip([v for v in views if v['kind'] == 'real'], cutouts):
        view.update(mask=item['file'], maskMethod='prepared subject', maskConfidence=0.95)
    if cutouts:
        notes.append(f'{min(len(cutouts), len(views))} view(s) took their mask from the prepared '
                     'subject set instead of segmenting the pictures again.')
    return notes


def _synthesize(context, services, parameters, views, engine_options, chosen, understanding, output):
    """Fill the viewpoints the photographs never covered, when they do not cover the object.

    In ``auto`` the coverage of the real pictures is measured first, by the fitting engine
    itself, and nothing is generated when they already cover the object: a generated view is a
    hypothesis, and paying for one that adds nothing only adds risk.
    """
    generator = GENERATORS[chosen['synthesis']]
    mode = parameters.get('view_synthesis', 'auto')
    needed = mode == 'always'
    if not needed:
        context.progress(36, currentStep='Measuring the coverage of the real views')
        preview = services.run(context, 'proxyfit', 'analyze',
                               {'parameters': {'task': 'analyze', 'views': views,
                                               'options': engine_options,
                                               'output': str(output / 'coverage-check'),
                                               'progressRange': [0, 100]}},
                               timeout=1800, progress_offset=36.0, progress_scale=0.08)
        score = preview.get('real_coverage_score', 0.0)
        understanding['viewSynthesis']['realCoverageBefore'] = score
        needed = score < parameters.get('synthesis_coverage_threshold', 0.6)
        if not needed:
            understanding['viewSynthesis']['skipped'] = 'the real pictures already cover the object'
            return

    real = [view for view in views if view['kind'] == 'real']
    index = int(parameters.get('synthesis_source', -1))
    if index >= len(real):
        raise CyToolError('InvalidParameters', 'synthesis_source refers to a missing picture')
    if index < 0:
        # A level view shows more of the object than a top or bottom one.
        index = next((position for position, view in enumerate(real)
                      if view.get('label') not in ('Top', 'Bottom')
                      and abs(view.get('elevation', 0)) < 60), 0)
    source = real[index]
    folder = output / 'synthesis'
    folder.mkdir(parents=True, exist_ok=True)

    context.progress(45, currentStep=f'Generating the missing views with {chosen["synthesis"]}')
    payload = {'image': source['image'], 'mask': source.get('mask'), 'output': str(folder),
               'engine': str(ROOT / 'runtime' / 'sources'
                             / ('Wonder3D' if chosen['synthesis'] == 'wonder3d-v1.0' else 'SyncDreamer')),
               'model': str(MODELS / chosen['synthesis']),
               'elevation': float(source.get('elevation', parameters.get('default_elevation', 12))),
               'steps': parameters.get('synthesis_steps') or generator['steps'],
               'seed': parameters.get('synthesis_seed', 0),
               'guidance': parameters.get('synthesis_guidance') or generator['guidance'],
               'device': 'cuda'}
    if generator['backend'] == 'zero123plus':
        payload = {'task': 'synthesize', 'device': 'cuda', 'output': str(folder),
                   'synthesis': {'id': chosen['synthesis'], 'path': str(MODELS / chosen['synthesis']),
                                 'source': {'image': source['image'], 'mask': source.get('mask')},
                                 'steps': payload['steps'], 'seed': payload['seed'],
                                 'guidance': payload['guidance']}}
    made = services.run(context, generator['backend'], generator['operation'],
                        {'parameters': payload}, timeout=3600,
                        progress_offset=45.0, progress_scale=0.17)

    for number, item in enumerate(made.get('generated', [])):
        relative = generator['sign'] * item['generatorAzimuth']
        view = {'name': f"g{number:02d}_az{int(round(item['generatorAzimuth'])) % 360:03d}",
                'image': item['image'], 'kind': 'generated', 'sourceViews': [source['name']],
                'relativeAzimuth': relative, 'elevation': item['elevation'],
                'fov': item['fov'], 'azimuth': 0.0,
                'requested': [relative, item['elevation']]}
        if generator['relative_elevation']:
            view['relativeElevation'] = item['elevation']
        if not generator.get('rig_refine', True):
            view['rigRefine'] = False
        if generator.get('weight_factor'):
            view['weight'] = round(parameters.get('generated_view_weight', 0.45)
                                   * generator['weight_factor'], 4)
        views.append(view)
    understanding['viewSynthesis'].update(generated=len(made.get('generated', [])),
                                          source=source['name'], stats=made.get('stats', {}))


def register(runtime, services):
    def plan(parameters):
        """What the understanding stage will really use. Shared by the estimator and the run."""
        segmentation = _resolve('segmentation', parameters.get('segmentation_model', 'auto'))
        depth = (_resolve('depth', parameters.get('depth_model', 'auto'))
                 if parameters.get('use_depth', True) else None)
        camera = _resolve('camera', parameters.get('camera_model', 'auto'))
        synthesis = None
        if parameters.get('view_synthesis', 'auto') != 'off':
            wanted = parameters.get('view_synthesis_model', 'auto')
            ready = [name for name in GENERATORS if _installed(name)]
            if wanted != 'auto':
                synthesis = wanted if wanted in ready else None
            else:
                synthesis = ready[0] if ready else None
        return {'segmentation': segmentation, 'depth': depth, 'camera': camera,
                'synthesis': synthesis, 'device': parameters.get('device', 'auto')}

    def understanding_ready():
        status = engines.status('diffusion')
        return bool(status['installed'])

    def run(task):
        def handler(context, parameters):
            chosen = plan(parameters)
            views = _views_from(parameters)
            notes = _subject_views(parameters, views)
            output = Path(context.path('outputs/.keep')).parent
            understanding = {
                'segmentation': chosen['segmentation'] or 'classical (alpha / plain background / GrabCut)',
                'depth': chosen['depth'] or 'none',
                'camera': chosen['camera'] or 'none (user angles, depth axis, defaults)',
                'device': chosen['device'], 'notes': notes}

            wanted = any((chosen['segmentation'], chosen['depth'], chosen['camera']))
            missing_masks = any('mask' not in view for view in views)
            if wanted and missing_masks and understanding_ready():
                context.progress(2, currentStep='Understanding the pictures')
                payload = {'task': 'understand', 'device': chosen['device'],
                           'output': str(output / 'understanding'),
                           'images': [{'name': view['name'], 'image': view['image'],
                                       'box': view.get('box'), 'needMask': 'mask' not in view}
                                      for view in views]}
                for family, key in (('segmentation', 'segmentation'), ('depth', 'depth'),
                                    ('camera', 'camera')):
                    if chosen[family]:
                        payload[key] = {'id': chosen[family], 'path': str(MODELS / chosen[family])}
                if chosen['camera']:
                    payload['camera']['engine'] = str(ROOT / 'runtime' / 'sources' / 'PerspectiveFields')
                (output / 'understanding').mkdir(parents=True, exist_ok=True)
                result = services.run(context, 'depthanything', 'understand', {'parameters': payload},
                                      timeout=1800, progress_offset=2.0, progress_scale=0.33)
                for view in views:
                    found = (result.get('views') or {}).get(view['name'], {})
                    if 'mask' not in view and 'mask' in found:      # a user mask always wins
                        view.update(mask=found['mask'], maskMethod=found['maskMethod'],
                                    maskConfidence=found['maskConfidence'])
                    if 'depth' in found:
                        view['depth'] = found['depth']
                    if 'cameraCue' in found:
                        view['cameraCue'] = found['cameraCue']
                understanding['stats'] = result.get('stats', {})
                understanding['device'] = (result.get('stats') or {}).get('device', chosen['device'])
            elif wanted and missing_masks:
                understanding['fallback'] = ('The diffusion engine is not installed: masks come '
                                             'from alpha or a plain background, and no depth cue '
                                             'is used.')

            engine_options = {key: value for key, value in parameters.items()
                              if key not in UNDERSTANDING_KEYS}
            mode = parameters.get('view_synthesis', 'auto')
            understanding['viewSynthesis'] = {'mode': mode, 'model': chosen['synthesis'],
                                              'generated': 0}
            if mode != 'off' and not chosen['synthesis']:
                understanding['viewSynthesis']['skipped'] = (
                    'No generator is installed, or its engine is not built')

            if chosen['synthesis'] and mode != 'off' and task == 'construct_mesh':
                _synthesize(context, services, parameters, views, engine_options, chosen,
                            understanding, output)

            context.progress(45, currentStep='Fitting the proxy geometry')
            payload = {'task': 'analyze' if task == 'analyze_views' else 'construct',
                       'views': views, 'options': engine_options, 'output': str(output),
                       'progressRange': [0, 100]}
            result = services.run(context, 'proxyfit',
                                  'analyze' if task == 'analyze_views' else 'construct',
                                  {'parameters': payload}, timeout=5400,
                                  progress_offset=45.0, progress_scale=0.54)
            result['understanding'] = understanding
            (output / 'understanding.json').write_text(
                json.dumps(understanding, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
            context.progress(100, currentStep='Completed')
            return result
        return handler

    def estimate(parameters, backend, model):
        chosen = plan(parameters)
        vram = 0.0
        if chosen['segmentation'] or chosen['depth'] or chosen['camera']:
            vram = 2.6
        if chosen['synthesis']:
            vram = max(vram, GENERATORS[chosen['synthesis']]['vram'])
        budget = {'ramBytes': 12 * 1024 ** 3, 'diskBytes': 2 * 1024 ** 3}
        if vram:
            budget['vramBytes'] = {'auto': int(vram * 1024 ** 3)}
        return budget

    registered = {'construct_proxy': run('construct_mesh'), 'analyze_views': run('analyze_views')}
    for name, handler in registered.items():
        runtime.register(name, handler, estimate=estimate)
    return registered
