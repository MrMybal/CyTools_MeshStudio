"""TRELLIS.2 backend: photographs to a textured mesh, ported from CyTools_LocalMesh.

The engine (``runtime/sources/localmesh-engine``, installed as a package in the ``trellis``
engine environment) owns the pipeline. This worker is the adapter: it resolves the model
layout, patches the matting model to the local weights, forwards the engine's stage
progress to the job, and keeps the loaded pipeline resident between jobs — which is the
whole point of a persistent worker here, since the weights are 7.6 GiB.

``generate`` runs the engine's own chain end to end, exactly as LocalMesh did: every
decision it encodes (monotonic progress, the face ceiling and its fallback to a lower tier,
NVML VRAM metering, the atlas repad, the atomic export, deleting the stage previews) stays
where it was measured. It only adds two measurements the engine does not report: the grid the
shape was really sampled on, and a token ceiling taken on the memory actually available.

``texture_mesh`` is the texturing stage on its own: the engine's ``texture_mesh`` applied to a
mesh that did not come out of the same run — a QuadWild remesh of the LocalMesh result, for
instance — with the normal bake and the texture transfer of ``normalbake``. The shape stages
stay inside ``generate``: upstream holds their GPU state in one method.
"""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import SessionStore, WorkerError, inside, isolate_native_output, serve  # noqa: E402

isolate_native_output()

ENGINE = {'instance': None}
SESSIONS = SessionStore(limit=1)


def models_root():
    """Root the engine reads its weights from (the per-engine layout of junctions)."""
    root = os.environ.get('LOCALMESH_ROOT')
    if not root:
        raise WorkerError('MissingDependency',
                          'LOCALMESH_ROOT is not set: the trellis model layout was not created.',
                          recoverable=True)
    return Path(root) / 'models'


def _prepare_environment(parameters):
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
    gpu = int(parameters.get('gpu', 0) or 0)
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu)
    return gpu


def _patch_matting():
    """Point BiRefNet at the verified local tree instead of the Hugging Face id.

    ``matting.MODEL_ID`` is the repository name; offline, that resolves to a cache this Tool
    does not use. LocalMesh overrode it the same way, including the constructor default, so
    that every call site lands on the revision-pinned copy.
    """
    from localmesh_engine import matting

    local = str(models_root() / 'BiRefNet_HR')
    matting.MODEL_ID = local
    original = matting.Matter.__init__
    if getattr(matting.Matter, '_meshstudio_patched', False):
        return local
    matting.Matter.__init__ = lambda self, model_id=None: original(self, local)
    matting.Matter._meshstudio_patched = True
    return local


def _engine():
    if ENGINE['instance'] is None:
        from localmesh_engine import Engine
        _patch_matting()
        ENGINE['instance'] = Engine()
    return ENGINE['instance']


def _apply_subject_set(parameters):
    """Replace the view paths by the cut-outs a prepare_subject run produced.

    The subject set is the shared front end's output: views already cut at one common scale,
    with what was measured about them. Consuming it here is what stops every backend from
    segmenting the same photographs again with a different model and a different framing.
    """
    import json

    folder = (parameters.get('subject_set') or '').strip()
    if not folder:
        return parameters, []
    root = Path(folder)
    document = root / 'subject.json'
    if root.is_file() and root.name == 'subject.json':
        document, root = root, root.parent
    if not document.is_file():
        raise WorkerError('MissingInput',
                          f'No subject.json in "{folder}"; run prepare_subject first.',
                          recoverable=True)
    try:
        data = json.loads(document.read_text('utf-8'))
    except ValueError as exc:
        raise WorkerError('InvalidInput', f'{document} is not valid JSON: {exc}') from exc

    notes = []
    found = {}
    for view in data.get('views', []):
        role = view.get('role')
        path = Path(view.get('file', ''))
        if role in ('front', 'right', 'left', 'back') and path.is_file():
            found[role] = str(path)
    if 'front' not in found:
        raise WorkerError('InvalidInput', f'The subject set in "{folder}" carries no front view')

    parameters = dict(parameters)
    for role, path in found.items():
        parameters[role] = path
    if not parameters.get('mode') and len(found) >= 4:
        parameters['mode'] = 'four'
    if data.get('nominalAngles') and len(found) >= 4:
        # The side views were generated at exact poses (0/90/180/270): measuring them again
        # could only add error. Which profile is which is still measured by the engine.
        parameters['angles_mv'] = 'nominaux'
        notes.append('The side views were generated by ' + str(data.get('generator', 'a model'))
                     + ' at exact poses; the engine takes them as 0/90/180/270 degrees.')
    notes.append(f'Views taken from the prepared subject set ({len(found)} view(s), '
                 f'common framing: {data.get("matting", {}).get("commonFraming", False)}).')
    camera = data.get('camera') or {}
    if camera.get('measured'):
        measured = ', '.join(f'{item["role"]} {item["azimuthDegrees"]:.1f} deg'
                             for item in data.get('views', []) if item.get('azimuthMeasured'))
        notes.append(f'The subject set carries measured angles ({measured}). The engine measures '
                     'them again internally: its multi-view path takes no injected angle.')
    elif camera.get('refusedBecause'):
        notes.append('The subject set reports no usable angle. ' + camera['refusedBecause'])
    return parameters, notes


def _settings(parameters):
    from localmesh_engine import GenerateSettings
    from localmesh_engine.meshops import FinishSettings

    mode = parameters.get('mode', 'single')
    front = parameters.get('front') or ''
    if not front:
        raise WorkerError('MissingInput', 'The front view is required')

    finish = FinishSettings(remove_floaters=bool(parameters.get('remove_floaters', True)),
                            fill_holes=bool(parameters.get('fill_holes', True)))
    if int(parameters.get('target_faces', 0) or 0) > 0:
        finish.target_faces = int(parameters['target_faces'])

    options = {
        'images': [Path(front)],
        'detail': parameters.get('tier', 'standard'),
        'seed': int(parameters.get('seed', -1)),
        'bake_normal_map': bool(parameters.get('bake_normal_map', True)),
        'transparency': parameters.get('transparency', 'auto'),
        'up_axis': parameters.get('up_axis', 'y'),
        'origin_at_base': bool(parameters.get('origin_at_base', True)),
        'finish': finish,
    }
    # Zero means "take it from the tier recipe"; only an explicit value overrides it.
    for key in ('steps_structure', 'steps_shape', 'steps_texture', 'texture_size',
                'fidelity', 'tex_guidance', 'real_size_mm'):
        value = parameters.get(key, 0)
        if value:
            options[key] = value
    if parameters.get('sampler') and parameters['sampler'] != 'recipe':
        options['sampler'] = parameters['sampler']
    if parameters.get('angles_mv') in ('auto', 'nominaux'):
        options['angles_mv'] = parameters['angles_mv']
    if mode == 'four':
        views = {}
        for english, french in (('right', 'droite'), ('left', 'gauche'), ('back', 'dos')):
            path = parameters.get(english)
            if path:
                views[french] = Path(path)
        options['vues'] = views
        options['chemin_mv'] = 'porte'
    else:
        options['vues'] = {}
        options['chemin_mv'] = 'auto'
    return GenerateSettings(**options)


def _check_runtime(parameters):
    import torch

    if not torch.cuda.is_available():
        raise WorkerError('MissingGPU', 'No CUDA GPU is available for the TRELLIS.2 engine',
                          recoverable=True)
    if torch.__version__ != '2.8.0+cu128':
        raise WorkerError('IncompatibleABI',
                          f'The CUDA extensions are compiled against torch 2.8.0+cu128, '
                          f'this environment has {torch.__version__}')
    # The engine's command line refuses a tier the card cannot hold; its library entry point does
    # not, so the check is made here, where the refusal can name the card and the requirement.
    from localmesh_engine import config as engine_config
    tier = parameters.get('tier', 'standard')
    card = engine_config.gpu_report()
    if not engine_config.palier_tenable(tier, card.total_vram_gb):
        needed = engine_config.recette(tier).vram_min_gb
        raise WorkerError('InsufficientVRAM',
                          f'The "{tier}" tier needs a {needed:.0f} GB card; {card.name} has '
                          f'{card.total_vram_gb:.1f} GB. Choose "high" instead.',
                          recoverable=True)
    if parameters.get('mode') == 'four':
        import natten
        if not natten.HAS_LIBNATTEN:
            raise WorkerError('MissingDependency',
                              'The four-view path needs the natten CUDA extension; '
                              'this build reports it as unavailable.', recoverable=True)


def generate(request, reporter):
    parameters = dict(request.get('parameters') or {})
    workspace = Path(request['workspace'])
    _prepare_environment(parameters)
    parameters, subject_notes = _apply_subject_set(parameters)
    for note in subject_notes:
        reporter.log(note)
    _check_runtime(parameters)

    settings = _settings(parameters)
    outputs = inside(workspace, 'outputs/.keep').parent

    def progress(stage, fraction):
        reporter.progress(min(100.0, float(fraction) * 100.0), stage)

    def on_preview(stage, path):
        reporter.log(f'preview ready: {stage} -> {path}')

    reporter.progress(1, 'Loading', 'Starting the TRELLIS.2 pipeline')
    engine = _engine()
    measured = {}
    with _Instrumented(measured):
        result = engine.generate(settings, outputs, progress=progress, on_preview=on_preview)
    grid_notes = _grid_notes(parameters.get('tier', 'standard'), measured)

    report = result.as_dict()
    report['grid'] = measured
    report['engine_revision'] = request.get('revision', '')
    report['network_generation'] = False
    report_path = inside(workspace, 'outputs/report.json')
    import json
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str),
                           encoding='utf-8')

    reporter.progress(100, 'Done', f'{result.faces} faces in {result.duration_s:.1f} s')
    return {
        'file': str(Path(result.glb_path).resolve()),
        'mimeType': 'model/gltf-binary',
        'report': str(report_path),
        'thumbnail': str(Path(result.thumbnail).resolve()) if result.thumbnail else '',
        'seed': int(result.seed),
        'faces': int(result.faces),
        'vertices': int(result.vertices),
        'seconds': float(result.duration_s),
        'peak_vram_gb': float(result.peak_vram_gb),
        'grid_resolution': int(measured.get('gridResolution') or 0),
        'token_cap': int(measured.get('tokenCap') or 0),
        'notes': subject_notes + grid_notes + list(result.notes),
    }


#: Grid of each recipe's pipeline type, when the cascade does not report one.
RECIPE_GRID = {'512': 512, '1024': 1024, '1024_cascade': 1024, '1536_cascade': 1536}


class _Instrumented:
    """Measure what the engine does not report, without changing what it computes.

    Two things. The token ceiling LocalMesh applies is 2 600 tokens per gigabyte of the card's
    TOTAL memory; when another program already holds part of the card that is too optimistic,
    so the ceiling is taken on what is available at the start of the job (free memory plus what
    this process has cached), and never above the engine's own figure. And the 1536 cascade
    lowers its grid by steps of 128 when the object has more tokens than the ceiling, which the
    engine only prints; the grid it really used is recorded and reported.
    """

    def __init__(self, record):
        self.record = record
        self.restore = []

    def __enter__(self):
        try:
            import torch
            from localmesh_engine import config as engine_config
            from localmesh_engine import pipeline as engine_pipeline

            torch.cuda.empty_cache()
            free, total = torch.cuda.mem_get_info()
            available = (free + torch.cuda.memory_reserved()) / 1024 ** 3
            record = self.record
            record['availableGb'] = round(available, 2)
            record['cardGb'] = round(total / 1024 ** 3, 2)
            original_cap = engine_pipeline._plafond_de_tokens

            def cap():
                engine_cap = original_cap()
                record['engineTokenCap'] = engine_cap
                record['tokenCap'] = min(engine_cap, max(8_192, int(2_600 * available)))
                return record['tokenCap']

            engine_pipeline._plafond_de_tokens = cap
            self.restore.append((engine_pipeline, '_plafond_de_tokens', original_cap))

            pipeline_class = engine_config.trellis('pipelines').Trellis2ImageTo3DPipeline
            original_cascade = pipeline_class.sample_shape_slat_cascade

            def cascade(this, *args, **kwargs):
                slat, grid = original_cascade(this, *args, **kwargs)
                record['gridResolution'] = int(grid)
                return slat, grid

            pipeline_class.sample_shape_slat_cascade = cascade
            self.restore.append((pipeline_class, 'sample_shape_slat_cascade', original_cascade))
        except Exception as exc:  # noqa: BLE001 - measuring must never break a generation
            self.record['instrumentError'] = f'{type(exc).__name__}: {exc}'
        return self

    def __exit__(self, *_exception):
        for owner, name, original in reversed(self.restore):
            setattr(owner, name, original)
        return False


def _grid_notes(tier, measured):
    """Say which grid the shape was really sampled on, and why when it is not the recipe's."""
    try:
        from localmesh_engine import config as engine_config
        recipe_grid = RECIPE_GRID.get(engine_config.recette(tier).pipeline_type, 0)
    except Exception:  # noqa: BLE001
        recipe_grid = 0
    if not measured.get('gridResolution') and recipe_grid:
        measured['gridResolution'] = recipe_grid
    grid = measured.get('gridResolution') or 0
    if recipe_grid and grid and grid < recipe_grid:
        return [f'Shape sampled on a {grid} grid instead of {recipe_grid}: the object needed more '
                f'tokens than the ceiling of {measured.get("tokenCap", 0):,} this card allows '
                f'({measured.get("availableGb", 0)} GB available at the start of the job).']
    if grid:
        return [f'Shape sampled on a {grid} grid, as the "{tier}" recipe asks.']
    return []


ROLE_FILES = {'front': 'front', 'droite': 'right', 'gauche': 'left', 'dos': 'back'}
ENGLISH_TO_FRENCH = {'right': 'droite', 'left': 'gauche', 'back': 'dos'}


def prepare_subject(request, reporter):
    """Cut the subject out of every view once, at a common scale, and measure the cameras.

    This is the shared front end: four Tools used to carry their own background remover
    (BiRefNet here, u2net in TripoSR, transparent-background in SPAR3D, SAM 2.1 in the view
    tools) and three of them estimated the camera differently. One pass writes a *subject
    set* — the cut-outs plus what was measured about them — which every reconstruction
    backend can consume, and which the artist can look at before paying for a reconstruction.

    The framing matters and is not cosmetic: cutting each view on its own scales an
    elongated object differently per view (a motorbike measured 37.9 % apart between its
    profile and its front), and the fusion then thickens it. ``preparer_lot`` gives the
    four views one common scale; ``common_framing: false`` restores per-view framing.
    """
    import json

    from PIL import Image

    parameters = dict(request.get('parameters') or {})
    workspace = Path(request['workspace'])
    _prepare_environment(parameters)

    views = {}
    for english in ('front', 'right', 'left', 'back'):
        path = parameters.get(english)
        if path:
            views[english] = Path(path)
    for extra in (parameters.get('images') or []):
        views.setdefault(f'view{len(views) + 1}', Path(extra))
    if 'front' not in views:
        raise WorkerError('MissingInput', 'The front view is required to prepare a subject')

    reporter.progress(5, 'Loading', 'Loading the matting model')
    _patch_matting()
    from localmesh_engine import matting

    opened, unreadable = {}, []
    for role, path in views.items():
        try:
            opened[role] = Image.open(path)
        except Exception as exc:  # noqa: BLE001
            unreadable.append({'role': role, 'file': str(path), 'error': str(exc)})
    if 'front' not in opened:
        raise WorkerError('InvalidInput', f'The front view could not be read: {unreadable}')

    reporter.progress(20, 'Cutting out', f'{len(opened)} view(s) through BiRefNet')
    common = bool(parameters.get('common_framing', True)) and len(opened) > 1
    matter = matting.matter()
    if common:
        batch = matter.preparer_lot(opened)
    else:
        batch = {role: matter.preparer_avec_geometrie(image) for role, image in opened.items()}

    folder = inside(workspace, 'outputs/subject/.keep').parent
    entries, thumbnails = [], []
    for role, (image, geometry) in batch.items():
        name = f'{role}.png'
        target = folder / name
        image.save(target)
        thumbnails.append(image)
        entries.append({'role': role, 'file': str(target), 'source': str(views.get(role, '')),
                        'size': list(image.size), 'geometry': geometry,
                        'azimuthDegrees': None, 'azimuthMeasured': False})

    camera = {'backend': 'none', 'measured': False, 'decision': '', 'report': {}}
    if parameters.get('measure_camera', True) and len(batch) > 1:
        reporter.progress(60, 'Measuring the cameras', 'Depth Anything 3 on the cut-outs')
        camera = _measure_cameras(batch, entries, reporter)

    if bool(parameters.get('contact_sheet', True)) and thumbnails:
        reporter.progress(85, 'Contact sheet', 'Assembling the views')
        _contact_sheet(thumbnails, folder / 'contact.png')

    document = {
        'format': 'cytools-meshstudio-subject',
        'schemaVersion': 1,
        'matting': {'backend': 'birefnet', 'model': 'BiRefNet_HR',
                    'commonFraming': common,
                    'note': ('A common framing keeps the four views at one scale, which is what a '
                             'multi-view fusion needs; it changes nothing on an object that is '
                             'taller than it is wide.')},
        'views': entries,
        'camera': camera,
        'unreadable': unreadable,
    }
    subject_file = folder / 'subject.json'
    subject_file.write_text(json.dumps(document, indent=2, ensure_ascii=False, default=str),
                            encoding='utf-8')

    notes = [f'{item["role"]}: unreadable ({item["error"]})' for item in unreadable]
    if common:
        notes.append('The views were cut out together, at a common scale.')
    if camera.get('measured'):
        notes.append('Camera angles measured: ' + ', '.join(
            f'{item["role"]} {item["azimuthDegrees"]:.1f} deg'
            for item in entries if item.get('azimuthMeasured')))
    elif camera.get('refusedBecause'):
        notes.append('Round angles used. ' + camera['refusedBecause'])

    reporter.progress(100, 'Done', f'{len(entries)} view(s) prepared')
    return {
        'subject_set': str(folder),
        'subject_file': str(subject_file),
        'views': entries,
        'contact_sheet': str(folder / 'contact.png') if (folder / 'contact.png').is_file() else '',
        'camera': camera,
        'viewCount': len(entries),
        'commonFraming': common,
        'notes': notes,
    }


def _measure_cameras(batch, entries, reporter):
    """Where each photograph was really taken from, when the measurement is available."""
    from localmesh_engine import config
    from localmesh_engine.multivue import cotes as _cotes

    if not _cotes.disponible(config):
        return {'backend': 'depth-anything-3', 'measured': False,
                'decision': '', 'report': {},
                'note': 'Measurement unavailable: ' + ', '.join(_cotes.manquants(config))}
    measurable = {role: image for role, (image, _geometry) in batch.items()}
    report = _cotes.mesurer(config, measurable)
    azimuths = _cotes.azimuts_mesures(report) or {}
    for entry in entries:
        value = azimuths.get(entry['role'])
        if value is not None:
            entry['azimuthDegrees'] = float(value)
            entry['azimuthMeasured'] = True
    result = {'backend': 'depth-anything-3', 'measured': bool(azimuths),
              'decision': report.get('decision', ''), 'report': report,
              'note': ('Azimuths are measured, not assumed: a view filed as "left" was found at '
                       '-53.6 deg on the reference subject, and projecting it at -90 deg carved a '
                       'cavity in the back.')}
    if not azimuths:
        result['refusedBecause'] = _refusal_reason(report, _cotes)
    return result


def _refusal_reason(report, cotes):
    """Why the measured angles were not used, in the terms the guard applies.

    The engine refuses a measurement rather than projecting a view from the wrong angle,
    and each refusal has a reason that is already in the report. Saying which one it is
    turns a silent fallback to round angles into something the artist can act on — usually
    by re-shooting at eye level.
    """
    if report.get('decision') not in ('nominal', 'swap_sides'):
        return (f'The two profiles could not be placed with confidence (decision: '
                f'{report.get("decision", "unknown")}), so no angle is trusted either.')
    if report.get('le_dos_contredit_son_etiquette'):
        return 'The back view does not measure near 180 degrees; its label is trusted instead.'
    angles = report.get('angles') or {}
    worst = None
    for source in ('camera', 'rayon'):
        for role, value in (angles.get(source) or {}).items():
            elevation = abs(float(value.get('elevation', 0.0)))
            if worst is None or elevation > worst[2]:
                worst = (source, role, elevation)
    if worst and worst[2] > getattr(cotes, 'ELEVATION_MAX', 30.0):
        return (f'The "{worst[1]}" view measures {worst[2]:.1f} degrees of elevation, over the '
                f'{getattr(cotes, "ELEVATION_MAX", 30.0):.0f} degree limit: a turntable shot from '
                'above is not corrected by this measurement, so the round angles are used.')
    camera_angles = angles.get('camera') or {}
    ray_angles = angles.get('rayon') or {}
    for role in camera_angles:
        if role not in ray_angles:
            continue
        gap = abs((camera_angles[role]['lacet'] - ray_angles[role]['lacet'] + 180) % 360 - 180)
        if gap > getattr(cotes, 'DESACCORD_MAX', 15.0):
            return (f'The two heads disagree by {gap:.1f} degrees on the "{role}" view, over the '
                    f'{getattr(cotes, "DESACCORD_MAX", 15.0):.0f} degree tolerance.')
    return 'Two views measured too close to each other, or a value was not finite.'


def _contact_sheet(images, target, cell=256):
    from PIL import Image

    count = len(images)
    columns = min(4, count)
    rows = (count + columns - 1) // columns
    sheet = Image.new('RGBA', (columns * cell, rows * cell), (18, 29, 44, 255))
    for index, image in enumerate(images):
        thumb = image.copy()
        thumb.thumbnail((cell, cell))
        x = (index % columns) * cell + (cell - thumb.width) // 2
        y = (index // columns) * cell + (cell - thumb.height) // 2
        sheet.paste(thumb, (x, y), thumb if thumb.mode == 'RGBA' else None)
    sheet.save(target)
    return target


SIDE_ROLES = {'right': 'droite', 'left': 'gauche', 'back': 'dos'}


def _subject_images(parameters, reporter):
    """(front, {droite|gauche|dos: image}, notes): the cut-outs the texture model expects.

    A subject set from prepare_subject already holds them, cut at one common scale; a bare
    image is cut out here with the same BiRefNet and the same preparation.
    """
    import json

    from PIL import Image

    folder = (parameters.get('subject_set') or '').strip()
    if folder:
        root = Path(folder)
        document = root / 'subject.json' if root.is_dir() else root
        if not document.is_file():
            raise WorkerError('MissingInput', f'No subject.json in "{folder}"; run prepare_subject first.',
                              recoverable=True)
        data = json.loads(document.read_text('utf-8'))
        by_role = {view.get('role'): Path(view.get('file', '')) for view in data.get('views', [])}
        if 'front' not in by_role or not by_role['front'].is_file():
            raise WorkerError('InvalidInput', f'The subject set in "{folder}" carries no front view')
        front = Image.open(by_role['front'])
        front.load()
        sides = {}
        for role, french in SIDE_ROLES.items():
            if role in by_role and by_role[role].is_file():
                sides[french] = Image.open(by_role[role])
                sides[french].load()
        generated = set(data.get('generatedRoles') or [])
        note = f'Texture guided by the prepared subject set ({1 + len(sides)} view(s))'
        if generated:
            note += f'; generated views: {", ".join(sorted(generated))}'
        return front, sides, [note + '.']

    image = (parameters.get('image') or '').strip()
    if not image:
        raise WorkerError('MissingInput', 'Give the reference image, or a subject set from prepare_subject.')
    reporter.progress(4, 'Cutting out', 'BiRefNet')
    _patch_matting()
    from localmesh_engine import matting

    prepared, _geometry = matting.matter().preparer_avec_geometrie(Image.open(image))
    matting.liberer()
    return prepared, {}, ['Reference cut out with BiRefNet for this texture.']


def _aligned(low_positions, high_positions):
    """Do the two meshes sit in the same place? A normal bake between two that do not is noise."""
    import numpy as np

    low_min, low_max = low_positions.min(0), low_positions.max(0)
    high_min, high_max = high_positions.min(0), high_positions.max(0)
    diagonal = float(np.linalg.norm(high_max - high_min)) or 1.0
    drift = float(max(np.abs(low_min - high_min).max(), np.abs(low_max - high_max).max()))
    return drift / diagonal, drift / diagonal <= 0.05


def _texture_images(material):
    """(base colour, metallic-roughness) arrays of a loaded material, whatever its kind."""
    import numpy as np

    if material is None:
        return None, None
    base = getattr(material, 'baseColorTexture', None) or getattr(material, 'image', None)
    mr = getattr(material, 'metallicRoughnessTexture', None)
    return (np.asarray(base) if base is not None else None,
            np.asarray(mr) if mr is not None else None)


def texture_mesh(request, reporter):
    """Give a remeshed model a texture made for its own topology.

    ``generate`` asks TRELLIS.2 for a texture generated on this very mesh, conditioned on the
    reference picture, which is what LocalMesh does to its own decimated mesh; ``transfer``
    re-projects the texture of a detailed model instead, with no model at all. In both cases a
    detailed model, when given, is also baked into a normal map, so the relief the remesh
    removed still answers the light. The polygons of the input are kept in the OBJ.
    """
    import json
    import random
    import time

    import numpy as np
    import torch
    import trimesh
    from PIL import Image

    import quadtex

    parameters = dict(request.get('parameters') or {})
    workspace = Path(request['workspace'])
    _prepare_environment(parameters)
    if not torch.cuda.is_available():
        raise WorkerError('MissingGPU', 'No CUDA GPU is available for the TRELLIS.2 engine',
                          recoverable=True)
    started = time.monotonic()
    outputs = inside(workspace, 'outputs/.keep').parent
    notes = []

    size = int(parameters.get('texture_size') or 4096)
    mode = parameters.get('texture_source', 'generate')
    seed = int(parameters.get('seed', -1))
    if seed < 0:
        seed = random.randint(0, 2 ** 31 - 1)

    reporter.progress(2, 'Unwrapping', 'keeping the polygons of the input')
    target = Path(parameters['mesh_file'])
    prepared = quadtex.prepare(target, padding=int(parameters.get('uv_padding', 4) or 4),
                               resolution=size)
    stats = prepared['stats']
    positions = prepared['vertex_positions']            # one per UV vertex, file coordinates
    faces = prepared['indices']
    uvs = prepared['uvs']
    if stats['split_by_seam']:
        notes.append(f'{stats["split_by_seam"]} polygon(s) crossed by a UV seam were written as '
                     f'triangles; {stats["kept"]} kept whole.')

    # The texture model reads a Y-up mesh facing like LocalMesh's output.
    model_positions = positions.copy()
    if parameters.get('up_axis', 'y') == 'z':
        model_positions[:, 1], model_positions[:, 2] = positions[:, 2], -positions[:, 1]

    detail = None
    detail_path = (parameters.get('detail_mesh') or '').strip()
    if detail_path:
        detail = quadtex.load_mesh(detail_path)
        drift, aligned = _aligned(positions, np.asarray(detail.vertices))
        if not aligned:
            notes.append(f'The detailed model does not overlap this mesh ({drift:.0%} of its size '
                         'apart); it was not used for the normal map or the transfer.')
            detail = None

    peak = 0.0
    base_array = mr_array = None
    if mode == 'transfer':
        if detail is None:
            raise WorkerError('InvalidInput', 'texture_source "transfer" needs the detailed model '
                              '(detail_mesh) whose texture is re-projected, aligned with this mesh.')
        detail_uv = getattr(getattr(detail, 'visual', None), 'uv', None)
        base_array, mr_array = _texture_images(getattr(getattr(detail, 'visual', None), 'material', None))
        if detail_uv is None or base_array is None:
            raise WorkerError('InvalidInput', 'The detailed model carries no UV texture to transfer.')
    else:
        front, sides, image_notes = _subject_images(parameters, reporter)
        notes.extend(image_notes)
        from localmesh_engine import remaillage, vrammetre

        reporter.progress(8, 'Loading', 'TRELLIS.2 texture model')
        engine = _engine()
        pipe = engine.load(lambda stage, fraction: reporter.progress(8 + 7 * float(fraction), stage),
                           model='trellis2')
        mesh_for_model = trimesh.Trimesh(vertices=model_positions, faces=faces, process=False,
                                         visual=trimesh.visual.TextureVisuals(uv=uvs))

        def milestone(stage, fraction):
            reporter.progress(15 + 60 * min(max(float(fraction), 0.0), 1.0), str(stage))

        common = dict(seed=seed, resolution=int(parameters.get('resolution') or 1024),
                      texture_size=size, steps=int(parameters.get('steps') or 16),
                      guidance=float(parameters.get('guidance') or 5.0), jalon=milestone)
        reporter.progress(15, 'Texturing', f'{size} px atlas')
        with vrammetre.Metre() as metre:
            if sides and parameters.get('multiview_texture'):
                if len(sides) < 3:
                    raise WorkerError('InvalidInput', 'Multi-view texturing needs the right, left '
                                      'and back views in the subject set.')
                _, base_image, mr_image = remaillage.texturer_multivue(pipe, mesh_for_model, front,
                                                                       sides, **common)
                notes.append('Texture guided by the four views (experimental upstream path).')
            else:
                _, base_image, mr_image = remaillage.texturer(pipe, mesh_for_model, front, **common)
        peak = float(metre.pic_gb)
        base_array, mr_array = np.asarray(base_image), np.asarray(mr_image)

    normal_array = None
    moved = {}
    if detail is not None:
        from localmesh_engine import normalbake

        reporter.progress(80, 'Baking', 'normal map from the detailed model')
        transfer = None
        high_uv = None
        if mode == 'transfer':
            transfer = {'baseColorTexture': base_array}
            if mr_array is not None:
                transfer['metallicRoughnessTexture'] = mr_array
            high_uv = torch.as_tensor(np.asarray(detail.visual.uv), dtype=torch.float32)
        normal_array, bake_report, moved = normalbake.bake(
            torch.as_tensor(np.asarray(detail.vertices), dtype=torch.float32),
            torch.as_tensor(np.asarray(detail.faces), dtype=torch.int32),
            torch.as_tensor(positions, dtype=torch.float32),
            torch.as_tensor(faces, dtype=torch.int32),
            torch.as_tensor(uvs, dtype=torch.float32),
            size=size, high_uv=high_uv, transfer=transfer)
        if bake_report is not None:
            notes.append(f'Normal map {size} px baked from {bake_report.faces_high:,} faces of '
                         'the detailed model.')
        if mode == 'transfer':
            if 'baseColorTexture' not in moved:
                raise WorkerError('BackendFailure', 'The texture of the detailed model could not be '
                                  're-projected onto this mesh.')
            base_array = moved.get('baseColorTexture', base_array)
            mr_array = moved.get('metallicRoughnessTexture', mr_array)
            notes.append('Texture re-projected from the detailed model; no model was run.')
        torch.cuda.empty_cache()

    reporter.progress(90, 'Writing', 'GLB, OBJ and maps')
    base = Image.fromarray(np.asarray(base_array).astype(np.uint8))
    maps = {'base_color': 'base_color.png'}
    base.save(outputs / maps['base_color'])
    mr = None
    if mr_array is not None:
        mr = Image.fromarray(np.asarray(mr_array).astype(np.uint8)).convert('RGB')
        mr.save(outputs / 'metallic_roughness.png')
        roughness = Image.fromarray(np.asarray(mr)[..., 1])
        maps['roughness'] = 'roughness.png'
        roughness.save(outputs / maps['roughness'])
    normal = None
    if normal_array is not None:
        normal = Image.fromarray(np.asarray(normal_array).astype(np.uint8))
        maps['normal'] = 'normal.png'
        normal.save(outputs / maps['normal'])

    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=base, metallicRoughnessTexture=mr, normalTexture=normal,
        baseColorFactor=np.array([255, 255, 255, 255], dtype=np.uint8),
        metallicFactor=1.0, roughnessFactor=1.0, alphaMode='OPAQUE', doubleSided=False)
    textured = trimesh.Trimesh(vertices=positions, faces=faces, process=False,
                               visual=trimesh.visual.TextureVisuals(uv=uvs, material=material))
    _ = textured.vertex_normals        # cached, hence written to the glTF
    glb_path = outputs / 'textured.glb'
    textured.export(str(glb_path))
    obj_path, mtl_path = quadtex.write_obj(outputs / 'textured.obj', prepared['positions'], uvs,
                                           prepared['obj_faces'], maps=maps)

    texels = (size * size) / max(len(faces), 1)
    report = {'target': str(target), 'detail': detail_path, 'source': mode, 'seed': seed,
              'textureSize': size, 'texelsPerTriangle': round(texels, 1), 'polygons': stats,
              'peakVramGb': round(peak, 2), 'seconds': round(time.monotonic() - started, 1),
              'notes': notes}
    report_path = outputs / 'texture-report.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    reporter.progress(100, 'Done', f'{stats["kept"]} polygons kept, {size} px')
    return {
        'file': str(glb_path.resolve()), 'obj_file': str(obj_path.resolve()),
        'base_color_file': str((outputs / maps['base_color']).resolve()),
        'normal_file': str((outputs / 'normal.png').resolve()) if normal is not None else '',
        'roughness_file': str((outputs / 'roughness.png').resolve()) if mr is not None else '',
        'report': str(report_path.resolve()), 'seed': seed, 'faces': int(len(faces)),
        'polygons': int(stats['polygons']), 'polygons_kept': int(stats['kept']),
        'polygons_split': int(stats['split_by_seam']), 'texture_size': size,
        'texels_per_triangle': round(texels, 1), 'peak_vram_gb': round(peak, 2),
        'seconds': round(time.monotonic() - started, 1), 'notes': notes,
    }


def refine_mesh(request, reporter):
    """Regenerate the detail of an existing mesh with TRELLIS.2, keeping its overall shape.

    The vendored pipeline's ``refine_mesh`` encodes the mesh, takes the occupancy of its
    latent as the sparse structure — so the silhouette and the parts stay those of the input —
    and samples the shape latent again on that structure, conditioned on the reference picture,
    up to the 1536 grid. The result then goes through LocalMesh's own cleaning chain (holes,
    remesh, debris, decimation to the budget), with the same face ceiling that protects the
    card, and is put back in the frame and at the scale of the input.

    This path is not used by LocalMesh itself; it comes with the vendored TRELLIS.2 tree.
    Geometry only: texture the result with ``texture_mesh``.
    """
    import json
    import random
    import time

    import numpy as np
    import torch
    import trimesh

    import quadtex

    parameters = dict(request.get('parameters') or {})
    workspace = Path(request['workspace'])
    _prepare_environment(parameters)
    if not torch.cuda.is_available():
        raise WorkerError('MissingGPU', 'No CUDA GPU is available for the TRELLIS.2 engine',
                          recoverable=True)
    from localmesh_engine import config as engine_config
    from localmesh_engine import pipeline as engine_pipeline
    from localmesh_engine import remaillage, vrammetre

    started = time.monotonic()
    outputs = inside(workspace, 'outputs/.keep').parent
    notes = []
    grid = int(parameters.get('resolution') or 1536)
    card = engine_config.gpu_report()
    if grid >= 1536 and card.total_vram_gb + 0.5 < 24.0:
        raise WorkerError('InsufficientVRAM', f'Refining on the 1536 grid needs a 24 GB card; '
                          f'{card.name} has {card.total_vram_gb:.1f} GB. Choose 1024.', recoverable=True)
    seed = int(parameters.get('seed', -1))
    if seed < 0:
        seed = random.randint(0, 2 ** 31 - 1)

    source = quadtex.load_mesh(parameters['mesh_file'])
    original = np.asarray(source.vertices, dtype=np.float64)
    if parameters.get('up_axis', 'y') == 'z':
        original = original.copy()
        original[:, 1], original[:, 2] = original[:, 2].copy(), -original[:, 1].copy()
    # The same normalisation preprocess_mesh applies, kept to put the result back afterwards.
    low, high = original.min(axis=0), original.max(axis=0)
    center = (low + high) / 2
    scale = 0.99999 / float((high - low).max())
    mesh_in = trimesh.Trimesh(vertices=original, faces=np.asarray(source.faces), process=False)

    front, sides, image_notes = _subject_images(parameters, reporter)
    notes.extend(image_notes)
    images = [front] + ([sides[k] for k in ('droite', 'gauche', 'dos') if k in sides]
                        if parameters.get('use_all_views') else [])

    reporter.progress(6, 'Loading', 'TRELLIS.2 shape model')
    engine = _engine()
    pipe = engine.load(lambda stage, fraction: reporter.progress(6 + 6 * float(fraction), stage),
                       model='trellis2')

    torch.cuda.empty_cache()
    free, _total = torch.cuda.mem_get_info()
    available = (free + torch.cuda.memory_reserved()) / 1024 ** 3
    token_cap = min(engine_pipeline._plafond_de_tokens(), max(8_192, int(2_600 * available)))
    sampler = {'steps': int(parameters.get('steps') or 16)}
    if float(parameters.get('guidance') or 0) > 0:
        sampler['guidance_strength'] = float(parameters['guidance'])

    reporter.progress(12, 'Refining', f'{grid} grid, {token_cap:,} tokens at most')
    with vrammetre.Metre() as metre:
        with torch.inference_mode():
            meshes, latent = pipe.refine_mesh(
                mesh_in, images if len(images) > 1 else front, seed=seed,
                shape_slat_sampler_params=sampler, resolution=grid, max_num_tokens=token_cap,
                generate_texture_slat=False, return_latent=True, use_tiled=True,
                max_views=len(images), sampler='euler')
        used_grid = int(latent[2])
        mesh = meshes[0]
        faces_raw = int(len(mesh.faces))
        ceiling = engine_pipeline._plafond_de_faces()
        if faces_raw > ceiling:
            raise WorkerError('InsufficientVRAM',
                              f'The refined shape has {faces_raw:,} faces, over the {ceiling:,} this '
                              'card can clean safely. Refine on the 1024 grid.', recoverable=True)
        recipe = engine_config.recette('max' if used_grid >= 1536 else 'high')
        target = int(parameters.get('target_faces') or recipe.faces)
        reporter.progress(70, 'Cleaning', 'holes, remesh, debris, budget')
        remaillage.nettoyer(mesh, dc_resolution=recipe.dc_resolution, cible_triangles=target,
                            perimetre_bouchage=engine_config.BOUCHAGE_PERIMETRE,
                            perimetre_fermeture=engine_config.FERMETURE_PERIMETRE,
                            ratio_aire=engine_config.DEBRIS_RATIO_AIRE,
                            distance_mini=engine_config.DEBRIS_DISTANCE_MINI,
                            part_maxi=engine_config.DEBRIS_PART_MAXI,
                            jalon=lambda stage, fraction: reporter.progress(
                                70 + 20 * float(fraction), str(stage)),
                            notes=notes)
        refined = remaillage.vers_trimesh(mesh)
        remaillage.purger()
    peak = float(metre.pic_gb)

    # Back to the frame and the scale of the input.
    vertices = np.asarray(refined.vertices, dtype=np.float64) / scale + center
    if parameters.get('up_axis', 'y') == 'z':
        vertices[:, 1], vertices[:, 2] = -vertices[:, 2].copy(), vertices[:, 1].copy()
    result = trimesh.Trimesh(vertices=vertices, faces=np.asarray(refined.faces), process=False)
    _ = result.vertex_normals
    glb_path = outputs / 'refined.glb'
    result.export(str(glb_path))

    if used_grid < grid:
        notes.insert(0, f'Refined on a {used_grid} grid instead of {grid}: the shape needed more '
                        f'tokens than the ceiling of {token_cap:,} ({available:.1f} GB available).')
    else:
        notes.insert(0, f'Refined on the {used_grid} grid.')
    report = {'input': str(parameters['mesh_file']), 'seed': seed, 'requestedGrid': grid,
              'grid': used_grid, 'tokenCap': token_cap, 'facesDecoded': faces_raw,
              'faces': int(len(result.faces)), 'vertices': int(len(result.vertices)),
              'peakVramGb': round(peak, 2), 'seconds': round(time.monotonic() - started, 1),
              'notes': notes}
    report_path = outputs / 'refine-report.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    reporter.progress(100, 'Done', f'{len(result.faces):,} faces on the {used_grid} grid')
    return {'file': str(glb_path.resolve()), 'report': str(report_path.resolve()), 'seed': seed,
            'grid_resolution': used_grid, 'token_cap': token_cap, 'faces': int(len(result.faces)),
            'vertices': int(len(result.vertices)), 'peak_vram_gb': round(peak, 2),
            'seconds': round(time.monotonic() - started, 1), 'notes': notes}


def release_session(request, reporter):
    key = str(request.get('session') or '')
    released = SESSIONS.release(key)
    if released:
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()
    return {'session': key, 'released': released, 'remaining': SESSIONS.keys()}


def diagnose(request, reporter):
    parameters = dict(request.get('parameters') or {})
    _prepare_environment(parameters)
    report = {'python': sys.version.split()[0], 'extensions': {}, 'modelsRoot': '', 'offline': True}
    try:
        report['modelsRoot'] = str(models_root())
    except WorkerError as exc:
        report['modelsRoot'] = str(exc)
    try:
        import torch
        report['torch'] = torch.__version__
        report['cuda'] = torch.version.cuda or ''
        report['cudaAvailable'] = bool(torch.cuda.is_available())
        report['gpu'] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ''
    except Exception as exc:
        report['torch'] = f'{type(exc).__name__}: {exc}'
    for name in ('cumesh', 'flex_gemm', 'o_voxel', 'natten'):
        try:
            module = __import__(name)
            report['extensions'][name] = getattr(module, '__version__', True)
            if name == 'natten':
                report['extensions']['natten_cuda'] = bool(getattr(module, 'HAS_LIBNATTEN', False))
        except Exception as exc:
            report['extensions'][name] = f'{type(exc).__name__}: {exc}'
    try:
        from localmesh_engine import Engine  # noqa: F401
        report['extensions']['localmesh_engine'] = True
    except Exception as exc:
        report['extensions']['localmesh_engine'] = f'{type(exc).__name__}: {exc}'
    expected = ['TRELLIS.2-4B/pipeline.json', 'microsoft/TRELLIS-image-large',
                'BiRefNet_HR', 'facebook/dinov3-vitl16-pretrain-lvd1689m', 'multivue']
    try:
        root = models_root()
        report['models'] = {item: (root / item).exists() for item in expected}
    except WorkerError:
        report['models'] = {}
    report['residentSessions'] = SESSIONS.keys()
    return report


if __name__ == '__main__':
    raise SystemExit(serve({'generate': generate, 'prepare_subject': prepare_subject,
                            'texture_mesh': texture_mesh, 'refine_mesh': refine_mesh,
                            'release_session': release_session,
                            'diagnose': diagnose}))
