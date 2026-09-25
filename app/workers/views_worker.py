"""Views backend: Zero123++ and the geometric mirror, ported from CyTools_ViewGenerator.

Segmentation, camera placement, the same-object check, view generation, the turntable, the
mirror and the scoring of candidate views all live here. The runtime, the CLI, MCP and the
interface never import torch: they talk to this process through the JSON-lines protocol.

The models it reads are the ones the catalogue holds: SAM 2.1, DINOv2, Zero123++ v1.2 with
its pipeline and its optional normal ControlNet. Everything the model produces is a
hypothesis about parts of an object that were never photographed, and the View Set says so
per view.
"""
import json
import os
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import isolate_native_output, serve  # noqa: E402

isolate_native_output()

APP = Path(__file__).resolve().parents[1]
DATA = APP.parent / 'data'


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text('utf-8'))
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    return path


import viewsets  # noqa: E402

class Context:
    """Progress reporting shared by every action.

    The original Tool polled a cancel file because its worker was one-shot; here the host
    kills the process tree on cancellation, so ``check`` has nothing to poll and the
    progress goes straight to the job through the reporter.
    """

    def __init__(self, workspace, reporter=None):
        self.reporter = reporter
        self.workspace = Path(workspace)
        self.outputs = self.workspace / 'outputs'
        self.outputs.mkdir(parents=True, exist_ok=True)
        self.started = time.time()
        self._percent = 0.0

    def check(self):
        return None

    def progress(self, percent, message=''):
        # A bar never goes backwards: a late tick proposing less than the highest point
        # already reached is dropped, label included.
        self._percent = max(self._percent, float(percent))
        if self.reporter is not None:
            self.reporter.progress(min(99.0, self._percent), str(message))

    def stage(self, message):
        self.progress(self._percent, message)

    def elapsed(self):
        return round(time.time() - self.started, 3)


def model_dirs():
    return {'sam2': DATA / 'models/sam2.1-hiera-base-plus',
            'dinov2': DATA / 'models/dinov2-base',
            'zero123plus': DATA / 'models/zero123plus-v1.2',
            'zero123plus-pipeline': DATA / 'models/zero123plus-pipeline/pipeline.py',
            'zero123plus-normal': DATA / 'models/controlnet-zp12-normal-gen-v1'}


def resolve_device(requested):
    import torch
    available = torch.cuda.is_available()
    if requested == 'cpu':
        return 'cpu', 'CPU was selected explicitly.'
    if requested == 'cuda':
        if not available:
            raise RuntimeError('CUDA was selected but no CUDA device is available.')
        return 'cuda', 'CUDA was selected explicitly.'
    if available:
        return 'cuda', 'Auto selected CUDA: a compatible device is present.'
    return 'cpu', 'Auto selected CPU: no CUDA device is present. Generation on CPU is very slow.'


def sources_from(parameters, key='images'):
    entries = []
    for index, entry in enumerate(parameters.get(key) or []):
        path = entry.get('file') or entry.get('path') or ''
        if not path:
            raise ValueError('Image %d has no file path.' % (index + 1))
        entries.append({'name': entry.get('name') or Path(path).stem,
                        'path': path, 'view': entry.get('view', 'Auto'),
                        'azimuth': entry.get('azimuth'), 'elevation': entry.get('elevation'),
                        'roll': entry.get('roll'), 'fov': entry.get('fov')})
    names = [e['name'] for e in entries]
    for index, name in enumerate(names):
        if names.count(name) > 1:
            entries[index]['name'] = '%s-%d' % (name, index + 1)
    if not entries:
        raise ValueError('At least one image is required.')
    return entries


def make_embedder(directory, device):
    from viewengine import identity
    if not Path(directory).is_dir():
        return None
    return lambda images: identity.embed(images, directory, device)


def run_analysis(context, parameters, *, estimate_unknown=True):
    from viewengine import analysis
    device, device_note = resolve_device(parameters.get('device', 'auto'))
    sources = sources_from(parameters)
    result = analysis.analyse(
        sources, segmentation_backend=parameters.get('segmentation_backend', 'sam2'),
        model_dirs=model_dirs(), device=device, estimate_unknown=estimate_unknown,
        progress=lambda p, m: context.progress(p * 0.5, m), cancel=context.check)
    result['device'] = device
    result['deviceNote'] = device_note
    return result


def guard_same_object(result, parameters):
    verdict = result['sameObject']
    if verdict['suspiciousImages'] and not parameters.get('force_same_object'):
        raise BusinessError(
            'DifferentObject',
            'At least one image does not look like the same object as the others '
            '(aggregate confidence %.2f, threshold %.2f). Review the images, or set '
            'force_same_object to true to use them anyway.'
            % (verdict['sameObjectConfidence'], verdict['threshold']),
            details={'suspiciousImages': verdict['suspiciousImages'],
                     'pairs': verdict['pairs']})


class BusinessError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def write_view_files(context, name, rgb, mask, *, background, resolution, upscale,
                     normal=None):
    from viewengine import generation, imaging
    values, mask, native, notes = generation.compose_view(
        rgb, mask, background=background, resolution=resolution, upscale=upscale)
    image_path = imaging.save(context.outputs / ('views/%s.png' % name), values)
    mask_path = imaging.save(context.outputs / ('masks/%s.png' % name), mask)
    normal_path = ''
    if normal is not None:
        if resolution and resolution != normal.shape[1] and (resolution < normal.shape[1] or upscale):
            normal = imaging.resize(normal, (resolution, resolution))
        normal_path = str(imaging.save(context.outputs / ('normals/%s.png' % name), normal))
    return {'image': str(image_path), 'mask': str(mask_path), 'normal': normal_path,
            'native': native, 'notes': notes, 'rgb': values, 'maskArray': mask}


def targets_from(parameters):
    """Requested viewpoints: presets, explicit angles, or both."""
    targets = []
    for entry in parameters.get('targets') or []:
        view = (entry.get('view') or 'Custom').strip()
        if view and view != 'Custom':
            azimuth, elevation = viewsets.preset_pose(view)
            targets.append({'azimuth': azimuth, 'elevation': elevation,
                            'roll': float(entry.get('roll') or 0.0), 'name': view})
        else:
            targets.append({'azimuth': float(entry.get('azimuth') or 0.0),
                            'elevation': float(entry.get('elevation') or 0.0),
                            'roll': float(entry.get('roll') or 0.0),
                            'name': entry.get('name') or ''})
    return targets


def component_status(model_id):
    """What the catalogue says about one model: installed, its revision and its size.

    CyTools_ViewGenerator kept its own installation receipt; here the single catalogue of the
    Tool (app/models/catalog.json) answers the same question, so one report cannot disagree
    with another.
    """
    catalogue = APP / 'models' / 'catalog.json'
    try:
        models = {item['id']: item for item in json.loads(catalogue.read_text('utf-8'))['models']}
    except (OSError, ValueError, KeyError):
        return {'name': model_id, 'installed': False, 'reason': 'NoCatalogue', 'bytes': 0}
    entry = models.get(model_id)
    if entry is None:
        return {'name': model_id, 'installed': False, 'reason': 'NotInCatalogue', 'bytes': 0}
    directory = APP.parent / entry['directory']
    for check in entry.get('verify', []):
        path = directory / check['path']
        if not path.is_file():
            return {'name': model_id, 'installed': False, 'reason': 'FileMissing', 'bytes': 0}
        if check.get('sizeBytes') and path.stat().st_size != check['sizeBytes']:
            return {'name': model_id, 'installed': False, 'reason': 'FileChanged', 'bytes': 0}
    return {'name': model_id, 'installed': directory.is_dir(), 'reason': 'Verified',
            'bytes': entry.get('sizeBytes', 0), 'repository': entry['source'].get('repository', ''),
            'revision': entry.get('revision') or ''}


def backend_for(parameters, device):
    from viewengine import backends
    identifier = parameters.get('_backend_id') or 'zero123plus'
    directories = model_dirs()
    if identifier == 'zero123plus':
        model_dir = directories['zero123plus']
        selection = parameters.get('_cy_selection') or {}
        custom = (selection.get('model') or {}).get('path')
        if custom:
            model_dir = Path(custom)
        return backends.load('zero123plus', model_dir=model_dir,
                             pipeline_file=directories['zero123plus-pipeline'],
                             controlnet_dir=directories['zero123plus-normal'],
                             device=device, app_dir=APP,
                             revision='local-reference' if custom else
                             component_status('zero123plus-v1.2').get('revision', ''),
                             dtype='float16' if device.startswith('cuda') else 'float32')
    if identifier == 'mirror':
        return backends.load('mirror')
    return backends.load(identifier)


def produce(context, parameters, analysis_result, targets):
    """Execute a plan: reuse real views, mirror, or generate with the backend."""
    from viewengine import generation, identity, imaging
    from viewengine.backends import base as backend_base, mirror as mirror_backend
    device = analysis_result['device']
    items = {item['name']: item for item in analysis_result['items']}
    real_views = list(analysis_result['views'])
    symmetry = parameters.get('symmetry', 'auto')
    symmetry_scores = {v['name']: v.get('symmetry', 0.0) for v in real_views}
    embed = make_embedder(model_dirs()['dinov2'], device)
    references = {v['name']: v for v in real_views}

    backend, backend_note = None, ''
    identifier = parameters.get('_backend_id') or 'zero123plus'
    if identifier != 'mirror':
        backend = backend_for(parameters, device)
    entries = generation.plan(
        targets, real_views, [], backend, references,
        reuse_tolerance=float(parameters.get('reuse_tolerance', generation.REUSE_TOLERANCE)),
        allow_mirror=bool(parameters.get('allow_mirror', True)) or identifier == 'mirror',
        symmetry=symmetry, symmetry_scores=symmetry_scores,
        prefer_real=bool(parameters.get('prefer_real', True)))

    variants = max(1, int(parameters.get('variants', 1)))
    seed = int(parameters.get('seed', -1))
    rings, generated, notes = {}, [], []
    peak_vram, resolved_seeds = 0.0, []
    needed = [(e['reference'], variant) for e in entries if e['action'] == 'generate'
              for variant in range(variants)]
    total = max(len(needed), 1)
    done = 0
    for entry in entries:
        context.check()
        if entry['action'] != 'generate':
            continue
        for variant in range(variants):
            key = (entry['reference'], variant)
            if key in rings:
                continue
            context.progress(50 + 40.0 * done / total,
                             'Generating from %s (variant %d/%d)'
                             % (entry['reference'], variant + 1, variants))
            reference_item = items[entry['reference']]
            values = dict(parameters)
            values['seed'] = -1 if seed < 0 else seed + variant
            samples, meta = generation.build_ring(
                backend, reference_item, values,
                progress=lambda m: context.stage(m), cancel=context.check)
            rings[key] = (samples, meta)
            resolved_seeds.append({'reference': entry['reference'], 'variant': variant,
                                   'seed': meta['seed']})
            peak_vram = max(peak_vram, meta.get('peakVramGiB', 0.0))
            done += 1

    background = parameters.get('background', 'transparent')
    resolution = int(parameters.get('resolution', 0) or 0)
    upscale = bool(parameters.get('upscale', False))
    # Several requested viewpoints can resolve to the same reachable pose: the ring is
    # coarser than the request. The view is produced once and lists every target it answers.
    produced = {}
    for index, entry in enumerate(entries):
        context.check()
        target = entry['target']
        requested = (target['azimuth'], target['elevation'], target['roll'])
        if entry['action'] == 'reuse-real':
            existing = next(v for v in real_views if v['name'] == entry['reference'])
            existing.setdefault('notes', []).append(
                'This real view also answers the requested %s viewpoint.'
                % (target['name'] or 'custom'))
            continue
        if entry['action'] == 'unavailable':
            notes.append('No view could be produced for %s: %s'
                         % (target['name'] or 'custom', entry['reason']))
            continue
        if entry['action'] == 'mirror':
            source = items[entry['mirrorSource']]
            engine = mirror_backend.Backend()
            mirrored = engine.mirror(source['rgb'], source['mask'], symmetry_mode=symmetry,
                                     threshold=float(parameters.get('symmetry_threshold', 0.82)))
            name = '%s-mirror-%02d' % (target['name'] or 'custom', index)
            files = write_view_files(context, name, mirrored['rgb'], mirrored['mask'],
                                     background=background, resolution=resolution,
                                     upscale=upscale)
            candidate = identity.prepare(files['rgb'], files['maskArray'], name=name)
            reference_items = [items[v['name']] for v in real_views if v['name'] in items]
            consistency = generation.evaluate(candidate, reference_items, embed)
            view_notes = list(files['notes']) + list(consistency['notes'])
            if mirrored['forced']:
                view_notes.append('Symmetry was forced: the measured score %.3f is below the '
                                  '%.2f threshold, so this mirrored view may be wrong.'
                                  % (mirrored['symmetry'], mirrored['threshold']))
            confidence = generation.confidence_of(
                consistency, entry['poseError'],
                base_confidence=min(1.0, mirrored['symmetry'] /
                                    max(mirrored['threshold'], 1e-6)))
            state = generation.flag(confidence, view_notes)
            generated.append(viewsets.make_view(
                azimuth=entry['achieved']['azimuth'], elevation=entry['achieved']['elevation'],
                roll=-float(target['roll']), fov=None, is_real=False, name=name,
                image=files['image'], mask=files['mask'], confidence=confidence,
                source_views=[entry['mirrorSource']], backend='mirror',
                model_version='geometric-mirror-1', method='mirror', requested=requested,
                notes=view_notes,
                extra={'state': state, 'variant': 0, 'consistency': consistency,
                       'symmetryScore': mirrored['symmetry'],
                       'plan': {k: entry[k] for k in ('action', 'reason', 'poseError')},
                       'nativeWidth': files['native'][0], 'nativeHeight': files['native'][1]}))
            continue
        for variant in range(variants):
            context.check()
            key = (entry['reference'], entry['sampleIndex'], variant)
            if key in produced:
                answered = produced[key].setdefault('alsoAnswers', [])
                answered.append({'name': target['name'] or 'custom',
                                 'azimuth': target['azimuth'],
                                 'elevation': target['elevation'],
                                 'poseError': entry['poseError']})
                continue
            samples, meta = rings[(entry['reference'], variant)]
            sample = samples[entry['sampleIndex']]
            suffix = '' if variants == 1 else '-v%d' % (variant + 1)
            name = '%s-%02d%s' % (target['name'] or 'custom', index, suffix)
            files = write_view_files(context, name, sample['rgb'], sample['mask'],
                                     background=background, resolution=resolution,
                                     upscale=upscale, normal=sample['normal'])
            candidate = identity.prepare(files['rgb'], files['maskArray'], name=name)
            reference_items = [items[v['name']] for v in real_views if v['name'] in items]
            mirror_reference = None
            opposite, _ = viewsets.existing_match(
                real_views, viewsets.mirror_pose(entry['achieved']['azimuth'],
                                                 entry['achieved']['elevation'])[:2],
                viewsets.REAL_TOLERANCE)
            if opposite is not None and opposite['name'] in items:
                mirror_reference = items[opposite['name']]
            consistency = generation.evaluate(candidate, reference_items, embed,
                                              mirror_reference=mirror_reference)
            view_notes = list(files['notes']) + list(consistency['notes'])
            confidence = generation.confidence_of(consistency, entry['poseError'])
            state = generation.flag(confidence, view_notes)
            generated.append(viewsets.make_view(
                azimuth=entry['achieved']['azimuth'], elevation=entry['achieved']['elevation'],
                roll=0.0, fov=backend.fov, is_real=False, name=name, image=files['image'],
                mask=files['mask'], normal=files['normal'], confidence=confidence,
                source_views=[entry['reference']], backend=backend.id,
                model_version=backend.model_version(), method='backend', requested=requested,
                notes=view_notes,
                extra={'state': state, 'variant': variant, 'consistency': consistency,
                       'seed': meta['seed'], 'steps': meta['steps'], 'guidance': meta['guidance'],
                       'plan': {k: entry[k] for k in ('action', 'reason', 'poseError',
                                                      'sampleIndex')},
                       'nativeWidth': files['native'][0], 'nativeHeight': files['native'][1]}))
            produced[key] = generated[-1]
    if backend is not None:
        if backend.elevation_absolute and backend.offsets:
            levels = sorted({e for _, e in backend.offsets})
            notes.append('Backend "%s" renders fixed absolute elevations (%s degrees) at '
                         'azimuths spaced %.0f degrees apart from the reference view. A '
                         'requested elevation outside that set cannot be produced exactly; '
                         'every view reports the pose actually achieved and its angular error.'
                         % (backend.id, ', '.join('%.0f' % x for x in levels),
                            abs(backend.offsets[1][0] - backend.offsets[0][0])
                            if len(backend.offsets) > 1 else 0.0))
        backend.release()
    return {'plan': entries, 'generated': generated, 'notes': notes,
            'peakVramGiB': round(peak_vram, 3), 'seeds': resolved_seeds}


def adopt_real_views(context, analysis_result):
    """Copy every real view and its mask into the job outputs.

    The imported input copy is temporary and disappears when the worker stops, so a
    View Set that referenced it would break. The bundle therefore owns its own copy of
    each real image, while the original path stays recorded as ``sourceFile``.
    """
    from viewengine import imaging
    items = {item['name']: item for item in analysis_result['items']}
    for view in analysis_result['views']:
        item = items.get(view['name'])
        if item is None:
            continue
        view['sourceFile'] = view['image']
        view['image'] = str(imaging.save(context.outputs / ('views/%s.png' % view['name']),
                                         item['rgb']))
        view['mask'] = str(imaging.save(context.outputs / ('masks/%s.png' % view['name']),
                                        item['mask']))
        # The original pixels stay untouched at their native resolution; the cut-out is
        # written beside them so a consumer can use the object without the background.
        rgba, _ = imaging.compose_background(item['rgb'], item['mask'], 'transparent')
        view['rgbaImage'] = str(imaging.save(
            context.outputs / ('rgba/%s.png' % view['name']), rgba))


def finish(context, parameters, analysis_result, production, *, operation):
    """Write the View Set bundle, the contact sheet and the operation outputs."""
    from viewengine import imaging
    adopt_real_views(context, analysis_result)
    views = list(analysis_result['views']) + list(production['generated'])
    report = viewsets.coverage(views)
    document = viewsets.view_set(
        read_json(APP / 'CyTool.json').get('version', '0.0.0'), views,
        coverage_report=report,
        analysis={'sameObject': analysis_result['sameObject'],
                  'declaredViewpoints': analysis_result['declaredViewpoints'],
                  'estimatedViewpoints': analysis_result['estimatedViewpoints'],
                  'relations': analysis_result['relations'],
                  'images': [{k: v for k, v in record.items() if k != 'view'}
                             for record in analysis_result['images']],
                  'device': analysis_result['device'],
                  'deviceNote': analysis_result['deviceNote']},
        notes=list(analysis_result['notes']) + list(production['notes']),
        extra={'operationId': operation, 'plan': production['plan'],
               'seeds': production['seeds'],
               'lowConfidenceViews': [v['name'] for v in views
                                      if v.get('state') == 'LowConfidence']})
    path = context.outputs / 'view-set.json'
    write_json(path, document)
    previews = []
    for view in views:
        try:
            values, _, _ = imaging.load_rgb(view['image'])
            previews.append(values)
        except (OSError, ValueError):
            continue
    sheet = imaging.thumbnail(previews)
    thumbnail = '' if sheet is None else str(imaging.save(context.outputs / 'contact-sheet.png', sheet))
    return {
        'viewSet': str(path),
        'directory': str(context.outputs),
        'thumbnail': thumbnail,
        'views': [{k: v for k, v in view.items() if k not in ('consistency',)} for view in views],
        'coverage': report,
        'sameObjectConfidence': analysis_result['sameObject']['sameObjectConfidence'],
        'recommendations': viewsets.recommendations(report),
        'generatedCount': len(production['generated']),
        'realCount': len(analysis_result['views']),
        'lowConfidenceViews': document['lowConfidenceViews'],
        'seeds': production['seeds'],
        'device': analysis_result['device'],
        'peakVramGiB': production['peakVramGiB'],
        'seconds': context.elapsed(),
        'notes': document['notes'],
    }


def action_diagnose(context, parameters):
    import torch
    from viewengine import backends
    devices = []
    for index in range(torch.cuda.device_count()):
        properties = torch.cuda.get_device_properties(index)
        devices.append({'index': index, 'name': properties.name,
                        'totalVramGiB': round(properties.total_memory / 1024 ** 3, 2)})
    modules = {}
    for name in ('diffusers', 'transformers', 'cv2', 'scipy', 'pymatting', 'numpy'):
        try:
            modules[name] = getattr(__import__(name), '__version__', 'installed')
        except Exception as exc:
            modules[name] = type(exc).__name__
    catalogue = {}
    for identifier in ('zero123plus', 'mirror', 'wonder3d', 'syncdreamer'):
        catalogue[identifier] = backends.descriptor(identifier)
    directories = {name: {'path': str(path), 'present': Path(path).exists()}
                   for name, path in model_dirs().items()}
    return {'python': sys.version.split()[0], 'torch': torch.__version__,
            'cuda': torch.version.cuda or '', 'cudaAvailable': bool(torch.cuda.is_available()),
            'devices': devices, 'modules': modules, 'backends': catalogue,
            'models': directories, 'offline': os.environ.get('HF_HUB_OFFLINE') == '1'}


def action_segment(context, parameters):
    from viewengine import imaging, segment
    device, device_note = resolve_device(parameters.get('device', 'auto'))
    outputs = []
    sources = sources_from(parameters)
    for index, source in enumerate(sources):
        context.progress(10 + 80.0 * index / len(sources), 'Segmenting %s' % source['name'])
        rgb, alpha, native = imaging.load_rgb(source['path'])
        result = segment.segment(rgb, alpha,
                                 backend=parameters.get('segmentation_backend', 'sam2'),
                                 model_dir=model_dirs().get('sam2'), device=device)
        rgba, _ = imaging.compose_background(rgb, result['mask'], 'transparent')
        entry = {'name': source['name'], 'source': str(source['path']),
                 'mask': str(imaging.save(context.outputs / ('masks/%s.png' % source['name']),
                                          result['mask'])),
                 'rgba': str(imaging.save(context.outputs / ('rgba/%s.png' % source['name']), rgba)),
                 'boundingBox': result['boundingBox'] or [],
                 'coverage': result['coverage'], 'method': result['method'],
                 'confidence': result['confidence'], 'width': native[0], 'height': native[1],
                 'notes': result['notes']}
        outputs.append(entry)
    return {'objects': outputs, 'directory': str(context.outputs), 'device': device,
            'deviceNote': device_note, 'seconds': context.elapsed()}


def action_analyze(context, parameters):
    result = run_analysis(context, parameters)
    context.progress(90, 'Writing the report')
    production = {'plan': [], 'generated': [], 'notes': [], 'peakVramGiB': 0.0, 'seeds': []}
    return finish(context, parameters, result, production, operation='analyze_views')


def action_generate(context, parameters):
    result = run_analysis(context, parameters)
    guard_same_object(result, parameters)
    targets = targets_from(parameters)
    if not targets:
        raise ValueError('At least one requested view is needed.')
    targets = viewsets.dedupe_targets(
        [(t['azimuth'], t['elevation'], t['roll'], t['name']) for t in targets])
    targets = [{'azimuth': t[0], 'elevation': t[1], 'roll': t[2], 'name': t[3]} for t in targets]
    production = produce(context, parameters, result, targets)
    context.progress(94, 'Validating the generated views')
    return finish(context, parameters, result, production, operation='generate_views')


def action_auto_complete(context, parameters):
    result = run_analysis(context, parameters)
    guard_same_object(result, parameters)
    recommended = viewsets.recommendations(
        result['coverage'], include_polar=bool(parameters.get('include_polar', True)),
        limit=int(parameters.get('max_views', 8)))
    targets = []
    for name in recommended:
        azimuth, elevation = viewsets.preset_pose(name)
        targets.append({'azimuth': azimuth, 'elevation': elevation, 'roll': 0.0, 'name': name})
    if not targets:
        production = {'plan': [], 'generated': [], 'peakVramGiB': 0.0, 'seeds': [],
                      'notes': ['Every important viewpoint is already covered by a real image; '
                                'nothing was generated.']}
    else:
        production = produce(context, parameters, result, targets)
    output = finish(context, parameters, result, production, operation='auto_complete_view_set')
    output['requestedViews'] = recommended
    return output


def action_turntable(context, parameters):
    result = run_analysis(context, parameters)
    guard_same_object(result, parameters)
    count = int(parameters.get('count', 8))
    elevations = [float(x) for x in (parameters.get('ring_elevations') or
                                     [float(parameters.get('elevation', 0.0))])]
    poses = viewsets.rings(count, elevations, float(parameters.get('start_azimuth', 0.0)))
    targets = [{'azimuth': a, 'elevation': e, 'roll': 0.0,
                'name': 'turntable-%03d' % round(viewsets.wrap180(a) % 360)}
               for a, e in poses]
    production = produce(context, parameters, result, targets)
    output = finish(context, parameters, result, production, operation='turntable_views')
    output['requestedViews'] = ['%.1f/%.1f' % (a, e) for a, e in poses]
    return output


def action_mirror(context, parameters):
    from viewengine import identity, imaging
    from viewengine.backends import mirror as mirror_backend
    result = run_analysis(context, parameters, estimate_unknown=False)
    if len(result['views']) != 1:
        raise ValueError('mirror_view takes exactly one image.')
    source_view = result['views'][0]
    item = result['items'][0]
    engine = mirror_backend.Backend()
    context.progress(70, 'Mirroring the view')
    mirrored = engine.mirror(item['rgb'], item['mask'],
                             symmetry_mode=parameters.get('symmetry', 'auto'),
                             threshold=float(parameters.get('symmetry_threshold', 0.82)))
    name = 'mirror-of-' + source_view['name']
    files = write_view_files(context, name, mirrored['rgb'], mirrored['mask'],
                             background=parameters.get('background', 'transparent'),
                             resolution=int(parameters.get('resolution', 0) or 0),
                             upscale=bool(parameters.get('upscale', False)))
    candidate = identity.prepare(files['rgb'], files['maskArray'], name=name)
    embed = make_embedder(model_dirs()['dinov2'], result['device'])
    from viewengine import generation
    consistency = generation.evaluate(candidate, [item], embed, mirror_reference=item)
    azimuth, elevation, roll = viewsets.mirror_pose(source_view['azimuth'],
                                                    source_view['elevation'],
                                                    source_view['roll'])
    notes = list(files['notes']) + list(consistency['notes'])
    if mirrored['forced']:
        notes.append('Symmetry was forced below the threshold; this mirrored view may be wrong.')
    notes.append('A mirrored view is a geometric flip of a real photograph, not an AI '
                 'generation. It is only correct for a bilaterally symmetric object.')
    # The consistency signals compare a flip with its own source, so they are optimistic:
    # the measured symmetry, not the comparison, decides how much to trust this view.
    confidence = generation.confidence_of(consistency, 0.0,
                                          base_confidence=min(1.0, mirrored['symmetry'] /
                                                              max(mirrored['threshold'], 1e-6)))
    view = viewsets.make_view(
        azimuth=azimuth, elevation=elevation, roll=roll, fov=source_view['fov'], is_real=False,
        name=name, image=files['image'], mask=files['mask'], confidence=confidence,
        source_views=[source_view['name']], backend='mirror',
        model_version='geometric-mirror-1', method='mirror',
        requested=(azimuth, elevation, roll), notes=notes,
        extra={'state': generation.flag(confidence, notes), 'variant': 0,
               'consistency': consistency, 'symmetryScore': mirrored['symmetry'],
               'nativeWidth': files['native'][0], 'nativeHeight': files['native'][1]})
    production = {'plan': [], 'generated': [view], 'notes': [], 'peakVramGiB': 0.0, 'seeds': []}
    output = finish(context, parameters, result, production, operation='mirror_view')
    output['symmetryScore'] = mirrored['symmetry']
    return output


def action_validate(context, parameters):
    from viewengine import generation, identity, imaging, segment
    device, device_note = resolve_device(parameters.get('device', 'auto'))
    reference_sources = sources_from(parameters, 'images')
    candidate_sources = sources_from(parameters, 'candidates')
    embed = make_embedder(model_dirs()['dinov2'], device)
    references = []
    for index, source in enumerate(reference_sources):
        context.progress(10 + 30.0 * index / len(reference_sources), 'Reading %s' % source['name'])
        rgb, alpha, _ = imaging.load_rgb(source['path'])
        mask = segment.segment(rgb, alpha, backend=parameters.get('segmentation_backend', 'sam2'),
                               model_dir=model_dirs().get('sam2'), device=device)
        references.append(identity.prepare(rgb, mask['mask'], name=source['name']))
    results = []
    for index, source in enumerate(candidate_sources):
        context.progress(45 + 50.0 * index / len(candidate_sources),
                         'Validating %s' % source['name'])
        rgb, alpha, native = imaging.load_rgb(source['path'])
        mask = segment.segment(rgb, alpha, backend=parameters.get('segmentation_backend', 'sam2'),
                               model_dir=model_dirs().get('sam2'), device=device)
        candidate = identity.prepare(rgb, mask['mask'], name=source['name'])
        consistency = generation.evaluate(candidate, references, embed)
        notes = list(consistency['notes'])
        confidence = generation.confidence_of(consistency, 0.0)
        results.append({'name': source['name'], 'file': str(source['path']),
                        'state': generation.flag(confidence, notes), 'confidence': confidence,
                        'signals': consistency['signals'], 'weights': consistency['weights'],
                        'width': native[0], 'height': native[1], 'notes': notes})
    return {'candidates': results, 'referenceCount': len(references), 'device': device,
            'deviceNote': device_note, 'directory': str(context.outputs),
            'lowConfidenceViews': [r['name'] for r in results if r['state'] == 'LowConfidence'],
            'seconds': context.elapsed()}


ACTIONS = {
    'diagnose_backend': action_diagnose,
    'segment_object': action_segment,
    'analyze_views': action_analyze,
    'generate_views': action_generate,
    'auto_complete_view_set': action_auto_complete,
    'turntable_views': action_turntable,
    'mirror_view': action_mirror,
    'validate_views': action_validate,
}


def _handler(action):
    """One protocol operation per upstream action, with its own Context."""
    def handler(request, reporter):
        parameters = dict(request.get('parameters') or {})
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                          HF_HUB_DISABLE_TELEMETRY='1',
                          HF_HOME=str(DATA / 'models/hf'),
                          TOKENIZERS_PARALLELISM='false')
        context = Context(request['workspace'], reporter)
        context.progress(2, 'Starting')
        try:
            result = ACTIONS[action](context, parameters)
        except BusinessError as exc:
            from _protocol import WorkerError
            raise WorkerError(exc.code, exc.message, details=exc.details, recoverable=True) from exc
        context.progress(99, 'Completed')
        reporter.progress(100, 'Done')
        return result
    return handler


if __name__ == '__main__':
    raise SystemExit(serve({name: _handler(name) for name in ACTIONS}))
