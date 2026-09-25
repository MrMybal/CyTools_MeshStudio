"""Orchestration: views -> poses -> coverage -> support volume -> fitted proxy -> textured GLB."""
import json
import math
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from . import ENGINE_VERSION, fitting, hull, poses, texture
from .cameras import LABELS, canonical_label, label_for, wrap
from .views import View, classical_mask, initial_camera, normalise, warp_like, WORK

WEIGHTS = {'silhouette': 1.0, 'depth': 0.25, 'edge': 0.35, 'multiview': 0.4, 'symmetry': 0.15,
           'complexity_primitive': 0.004, 'complexity_triangle': 0.002}
DEFAULTS = {
    'complexity': 'Simple', 'symmetry': 'Auto', 'main_axis': 'Auto',
    'real_view_weight': 1.0, 'generated_view_weight': 0.45, 'mirrored_view_weight': 0.8,
    'single_view_symmetry_confidence': 0.5, 'symmetry_threshold': 0.93,
    'use_depth': True, 'depth_margin': 0.12, 'register_views': True, 'refine_poses': True,
    'snap_angle': 8.0, 'thin_as_planes': False, 'body_window': 0.35, 'min_thickness_ratio': 0.04, 'unobserved_extent_ratio': 1.0, 'min_gain': 0.004,
    'split_below': 0.5, 'part_triangle_penalty': 0.0015, 'refine_passes': 2,
    'texture_resolution': 1024, 'texture_padding': 4, 'texture_blend': 'best', 'blend_views': 3,
    'visibility_resolution': 384, 'min_facing': 0.12, 'real_view_bonus': 1.0, 'mirrored_view_bonus': 0.55,
    'generated_view_bonus': 0.3, 'target_size': 1.0, 'weld_tolerance': 1e-4,
    'default_fov': poses.DEFAULT_FOV, 'default_azimuth': poses.DEFAULT_AZIMUTH, 'default_elevation': poses.DEFAULT_ELEVATION,
}
SYMMETRY_AXES = {'Off': None, 'Auto': 'auto', 'Force X': 'x', 'Force Y': 'y', 'Force Z': 'z'}


def resolve_options(parameters):
    options = dict(DEFAULTS)
    options.update({k: v for k, v in parameters.items() if k in DEFAULTS and v is not None})
    preset = dict(fitting.PRESETS[options['complexity']])
    for key, name in (('grid', 'grid_resolution'), ('sections', 'max_sections'), ('section_vertices', 'section_vertices'),
                      ('parts', 'max_primitives'), ('polygon', 'max_polygon_vertices'), ('min_part', 'min_part_volume')):
        if parameters.get(name) is not None: preset[key] = parameters[name]
    options.update(preset)
    options['weights'] = {**WEIGHTS, **{k: v for k, v in (parameters.get('fit_weights') or {}).items() if k in WEIGHTS}}
    return options


def read_image(path):
    image = Image.open(path)
    image.load()
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGBA' if 'A' in image.getbands() or image.mode == 'P' else 'RGB')
    array = np.asarray(image)
    if max(array.shape[:2]) > 4096:
        scale = 4096 / max(array.shape[:2])
        array = cv2.resize(array, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(array)


def load_views(spec, options, note):
    """Build View records. Masks and depth come from the AI stage when present, otherwise the
    classical segmentation is used and no depth cue exists."""
    views, records = [], []
    for index, item in enumerate(spec['views']):
        note(2 + 10 * index / max(len(spec['views']), 1), 'Loading and segmenting ' + item['name'])
        rgba = read_image(item['image'])
        if item.get('mask'):
            mask = np.asarray(Image.open(item['mask']).convert('L').resize((rgba.shape[1], rgba.shape[0]))) > 127
            method, mask_conf = item.get('maskMethod', 'provided'), float(item.get('maskConfidence', 0.9))
        else:
            mask, method, mask_conf = classical_mask(rgba)
        if rgba.shape[2] == 4:   # flatten transparency on neutral grey for texturing
            alpha = rgba[..., 3:4].astype(np.float32) / 255
            rgba = np.concatenate([(rgba[..., :3] * alpha + 128 * (1 - alpha)).astype(np.uint8), rgba[..., 3:]], 2)
        image, small, partial, crop = normalise(rgba, mask)
        depth = None
        if item.get('depth') and options['use_depth']:
            raw = np.load(item['depth']).astype(np.float32)
            raw = cv2.resize(raw, (rgba.shape[1], rgba.shape[0]), interpolation=cv2.INTER_LINEAR)
            depth = warp_like(raw, crop)
        kind = item.get('kind', 'real')
        cue_record = item.get('cameraCue') or {}
        cue = cue_record if cue_record.get('usable', True) else {}     # an unusable cue is reported, never applied
        fov = item.get('fov', cue.get('fov', options['default_fov']))
        roll = item.get('roll', cue.get('roll', 0.0))
        label = canonical_label(item['label']) if item.get('label') else None
        source, confidence, detail = 'default', 0.2, {}
        elevation = item.get('elevation', cue.get('elevation'))
        azimuth = item.get('azimuth')
        if azimuth is not None:
            source, confidence = 'user', 0.95
            if elevation is None: elevation = LABELS[label][1] if label else options['default_elevation']
        elif label:
            azimuth, label_elevation = LABELS[label]; source, confidence = 'user-label', 0.9
            elevation = label_elevation if label in ('Top', 'Bottom') else (0.0 if elevation is None else elevation)
        else:
            if elevation is None: elevation = options['default_elevation']
            estimate = azimuth_estimate(small, depth, fov, elevation) if depth is not None else None
            if estimate:
                azimuth, confidence, detail = estimate; source = 'depth-axis'
            else:
                azimuth = options['default_azimuth']
        if kind == 'generated':
            source, confidence = 'synthesis-pose', float(item.get('confidence', options['generated_view_weight']))
        weight = float(item.get('weight') or (options['real_view_weight'] if kind == 'real' else options['generated_view_weight']))
        if fov > 0:   # a crop of a perspective picture is a narrower camera
            focal = (max(rgba.shape[:2]) / 2) / math.tan(math.radians(fov) / 2) * (WORK / crop['side'])
            canvas_fov = math.degrees(2 * math.atan((WORK / 2) / focal))
        else:
            canvas_fov = 0.0
        camera = initial_camera(small, azimuth, elevation, roll, canvas_fov)
        ratio = None
        if kind == 'generated':
            # A novel-view generator renders every view with ONE camera: object centre on the optical axis (picture
            # centre), same distance, same field of view. Keep that knowledge instead of re-centring on each mask.
            ratio = WORK / crop['side']
            camera.center = np.array([(rgba.shape[1] / 2 - crop['centerX']) * ratio + WORK / 2,
                                      (rgba.shape[0] / 2 - crop['centerY']) * ratio + WORK / 2])
        view = View(item['name'], image, small, camera, weight, kind, item.get('sourceViews'), depth,
                    min(confidence, mask_conf) if kind == 'real' else confidence, partial, source)
        if item.get('requested'): view.requested = item['requested']
        view.pixel_ratio = ratio
        view.rig_refine = bool(item.get('rigRefine', True))
        views.append(view)
        records.append({'name': item['name'], 'source': str(item['image']), 'segmentation': method,
                        'segmentationConfidence': round(mask_conf, 3), 'maskAreaRatio': round(float(mask.mean()), 4),
                        'crop': crop, 'sourceFov': fov, 'poseDetail': detail, 'cameraCue': cue_record or None,
                        'cameraCueApplied': sorted(k for k in ('fov', 'roll', 'elevation') if k in cue and item.get(k) is None)})
    return views, records


def azimuth_estimate(mask, depth, fov, elevation):
    return poses.azimuth_from_depth(mask, depth, fov, elevation)


def apply_registration(views, options, check):
    """Use classical feature registration to pose real views that have no user pose."""
    real = [v for v in views if v.is_real]
    if len(real) < 2 or not options['register_views']:
        return {'pairs': [], 'note': 'fewer than two real views or registration disabled'}
    small = [cv2.resize(v.image, (768, 768), interpolation=cv2.INTER_AREA) for v in real]
    pairs = poses.register(small, [v.mask for v in real], [v.camera.fov or 35.0 for v in real], check)
    similarity = poses.colour_similarity(small, [v.mask for v in real])
    anchored = {i for i, v in enumerate(real) if v.pose_source in ('user', 'user-label')} or {0}
    changed = True
    while changed:
        changed = False
        for (i, j), entry in sorted(pairs.items(), key=lambda kv: -kv[1]['inliers']):
            if not entry['usable']: continue
            for a, b, R in ((i, j, np.array(entry['rotation'])), (j, i, np.array(entry['rotation']).T)):
                if a in anchored and b not in anchored:
                    ca = real[a].camera
                    az, el, roll = poses.angles_from_matrix(R @ poses.camera_matrix(ca.azimuth, ca.elevation, ca.roll))
                    cam = real[b].camera; cam.azimuth, cam.elevation, cam.roll = az, el, roll
                    real[b].pose_source = 'feature-registration'
                    real[b].confidence = float(np.clip(0.4 + entry['inliers'] / 200.0, 0.4, 0.9))
                    anchored.add(b); changed = True
    out = []
    for (i, j), entry in pairs.items():
        out.append({'a': real[i].name, 'b': real[j].name, 'matches': entry['matches'], 'inliers': entry['inliers'],
                    'usable': entry['usable'], 'relativeRotationDegrees': entry.get('angle'),
                    'colourSimilarity': round(similarity[(i, j)], 3)})
    return {'pairs': out, 'method': 'OpenCV SIFT + essential matrix (RANSAC), object pixels only'}


def decide_symmetry(grid, views, options, check):
    mode = SYMMETRY_AXES[options['symmetry']]
    real = [v for v in views if v.is_real]
    if mode is None:
        return None, 0.0, {'mode': 'Off'}
    if mode != 'auto':
        return mode, 1.0, {'mode': options['symmetry'], 'source': 'user'}
    separation = max((poses.angular_distance(a.camera.azimuth, a.camera.elevation, b.camera.azimuth, b.camera.elevation)
                      for a in real for b in real), default=0.0)
    if len(real) < 2 or separation < 40:
        return 'z', options['single_view_symmetry_confidence'], {
            'mode': 'Auto', 'source': 'assumed', 'note': 'Bilateral symmetry cannot be verified from the available real views; it is a hypothesis.'}
    # A symmetric object seen from azimuth a looks like its flipped picture seen from -a: the
    # mirrored views must stay coherent with the real ones if the bilateral hypothesis holds.
    base = hull.coherence(grid, real, check)
    saved = [v.camera.copy() for v in views]
    trial = real + [v.mirrored('z', options['mirrored_view_weight']) for v in real]
    plane = hull.optimise_plane(grid, trial, 'z', check)
    ratio = plane['coherence'] / max(base, 1e-6)
    for v, cam in zip(views, saved): v.camera = cam
    info = {'mode': 'Auto', 'source': 'measured', 'coherenceWithoutMirrors': round(base, 4),
            'coherenceWithMirrors': plane['coherence'], 'ratio': round(ratio, 4), 'threshold': options['symmetry_threshold']}
    confidence = float(np.clip((ratio - 0.8) / 0.2, 0.0, 1.0))
    return ('z', confidence, info) if ratio >= options['symmetry_threshold'] else (None, 0.0, info)


def prepare(spec, options, note, check):
    views, records = load_views(spec, options, note)
    if not any(v.is_real for v in views):
        raise ValueError('At least one real image is required')
    note(14, 'Registering real views')
    registration = apply_registration(views, options, check)
    # Generated views are posed relative to their source view.
    by_name = {v.name: v for v in views}
    for item, view in zip(spec['views'], views):
        if view.is_generated and item.get('relativeAzimuth') is not None and view.source_views:
            base = by_name[view.source_views[0]].camera
            view.camera.azimuth = wrap(base.azimuth + item['relativeAzimuth'])
            if item.get('relativeElevation') is not None:     # generators working in the frame of the input view
                view.camera.elevation = float(np.clip(base.elevation + item['relativeElevation'], -89.0, 89.0))
            view.requested = [round(wrap(view.camera.azimuth) % 360, 2), round(view.camera.elevation, 2)]
    coarse = hull.Grid(56)
    note(18, 'Balancing view scales')
    scale_history = hull.balance_scales(coarse, views, check=check)
    orientation = hull.orient_vertical_views(coarse, views, [v for v, item in zip(views, spec['views'])
                                             if abs(v.camera.elevation) > 60 and item.get('azimuth') is None], check)
    if orientation: scale_history += hull.balance_scales(coarse, views, check=check)
    refinement = hull.refine_poses(coarse, views, check=check) if options['refine_poses'] else []
    if refinement: hull.balance_scales(coarse, views, check=check)
    note(26, 'Analysing symmetry')
    axis, sym_conf, sym_info = decide_symmetry(coarse, views, options, check)
    plane = None
    if axis:
        mirrors = [v.mirrored(axis, sym_conf * options['mirrored_view_weight']) for v in views if v.is_real]
        views = views + mirrors
        plane = hull.optimise_plane(coarse, [v for v in views if not v.is_generated], axis, check)
        for v in views:   # synthetic views live in the same world: they follow the plane shift
            if v.is_generated: v.camera.target['xyz'.index(axis)] += plane['offset']
        hull.sync_mirrors(views, axis)
        scale_history += hull.balance_scales(coarse, views, iterations=1, check=check, axis=axis)
        rig = hull.refine_rig_azimuth(coarse, views, axis, check)
        if rig:
            sym_info['syntheticRigRefinement'] = rig
            scale_history += hull.balance_scales(coarse, views, iterations=1, check=check, axis=axis)
        sym_info['planeSearch'] = plane
    volume = hull.carve(coarse, [v for v in views if not v.is_generated], check=check)
    if not volume.any():
        raise ValueError('The silhouettes are inconsistent: no common volume. Check the view labels or angles.')
    hull.recentre(coarse, views, volume, keep=axis)
    return views, records, registration, {'scaleBalancing': scale_history, 'verticalViewOrientation': orientation, 'poseRefinement': refinement}, axis, sym_conf, sym_info


def support(views, options, axis, note, check):
    grid = hull.Grid(options['grid'])
    note(32, 'Carving the weighted support volume')
    volume, protection = hull.protect_real_views(grid, views, check=check)
    volume, assumed = hull.bound_unconstrained(grid, volume, views, options['unobserved_extent_ratio'])
    depth_stats = [{'unconstrainedAxes': assumed}] if assumed else []
    if options['use_depth'] and any(v.depth is not None for v in views):
        note(38, 'Applying monocular depth as a low-confidence cue')
        volume, more = hull.depth_carve(grid, volume, views, options['depth_margin'], check); depth_stats += more
    if axis:
        volume = volume & np.flip(volume, 'xyz'.index(axis))
    volume = hull.clean(volume)
    if volume.sum() < 50:
        raise ValueError('The support volume is empty: the views do not describe one consistent object.')
    for v in views: v.coverage = hull.coverage(grid, volume, v)
    return grid, volume, protection, depth_stats


def usable(views):
    """Views that still take part after the real-picture protection (weight 0 = excluded)."""
    return [v for v in views if v.weight > 0]


def verification(views, registration):
    real = [v for v in views if v.is_real]
    coherence = float(np.mean([v.coverage for v in real])) if real else 0.0
    pairs = registration.get('pairs', [])
    colour = float(np.mean([p['colourSimilarity'] for p in pairs])) if pairs else None
    matched = sum(1 for p in pairs if p['usable'])
    separation = [poses.angular_distance(a.camera.azimuth, a.camera.elevation, b.camera.azimuth, b.camera.elevation)
                  for i, a in enumerate(real) for b in real[i + 1:]]
    likelihood = coherence if colour is None else float(np.clip(0.6 * coherence + 0.25 * max(colour, 0) + 0.15 * (matched / len(pairs)), 0, 1))
    return {'sameObjectLikelihood': round(likelihood, 3), 'silhouetteCoherence': round(coherence, 4),
            'meanColourSimilarity': None if colour is None else round(colour, 3),
            'registeredPairs': matched, 'pairCount': len(pairs),
            'minViewSeparationDegrees': round(min(separation), 1) if separation else None,
            'posesSufficientlyDifferent': bool(separation and max(separation) >= 40) if len(real) > 1 else None,
            'silhouettesConsistent': bool(coherence >= 0.85),
            'correspondencesUsable': bool(matched > 0) if pairs else None,
            'warnings': [w for w in [
                'Low silhouette coherence: a view label/angle is probably wrong or the pictures show different objects.' if coherence < 0.85 else None,
                'Real views are close to each other: little new geometric information.' if separation and max(separation) < 40 else None,
                'Single real image: the result is a volume hypothesis.' if len(real) == 1 else None] if w]}


def analysis_report(views, records, registration, extra, axis, sym_conf, sym_info, options):
    table, real_score, effective = poses.coverage_map(views)
    check = verification(views, registration)
    confidence, detail = poses.expected_confidence(real_score, effective, views, check['silhouetteCoherence'])
    return {'views': [v.to_json() for v in views], 'inputs': records, 'registration': registration, **extra,
            'verification': check, 'coverage': table, 'RealCoverageScore': round(real_score, 4),
            'EffectiveCoverageScore': round(effective, 4), 'ExpectedReconstructionConfidence': round(confidence, 4),
            'confidenceDetail': detail,
            'symmetry': {**sym_info, 'axis': axis.upper() if axis else None, 'confidence': round(sym_conf, 4)},
            'isHypothesis': len([v for v in views if v.is_real]) == 1}


def contact_sheet(path, views, primitives=None, support=None):
    """Diagnostic picture: mask outline (green), support volume (yellow) and proxy outline (red)."""
    from . import raster
    tiles = []
    mesh = None
    if primitives:
        vs, fs, off = [], [], 0
        for p in primitives:
            v, f = p.mesh(); vs.append(v); fs.append(f + off); off += len(v)
        mesh = (np.vstack(vs), np.vstack(fs))
    for view in views:
        tile = cv2.resize(view.image, (WORK, WORK), interpolation=cv2.INTER_AREA).copy()
        contours, _ = cv2.findContours(view.mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(tile, contours, -1, (60, 220, 90), 1)
        if support:
            contours, _ = cv2.findContours(hull.projection(support[0], support[1], view).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cv2.drawContours(tile, contours, -1, (240, 210, 60), 1)
        if mesh:
            sil = raster.silhouette(view.camera, mesh[0], mesh[1], WORK)
            contours, _ = cv2.findContours(sil.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cv2.drawContours(tile, contours, -1, (235, 70, 60), 1)
        text = f"{view.name[:22]} | {view.kind} | {label_for(view.camera.azimuth, view.camera.elevation)} az{wrap(view.camera.azimuth) % 360:.0f} el{view.camera.elevation:.0f}"
        cv2.rectangle(tile, (0, 0), (WORK, 16), (20, 20, 20), -1)
        cv2.putText(tile, text, (4, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (240, 240, 240), 1, cv2.LINE_AA)
        tiles.append(tile)
    cols = min(4, len(tiles)); rows = math.ceil(len(tiles) / cols)
    sheet = np.full((rows * WORK, cols * WORK, 3), 32, np.uint8)
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols); sheet[r * WORK:(r + 1) * WORK, c * WORK:(c + 1) * WORK] = tile
    Image.fromarray(sheet).save(path)


def analyze(spec, output, note=None, check=None):
    note = note or (lambda *a, **k: None)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    options = resolve_options(spec.get('options', {}))
    options['grid'] = min(options['grid'], 72)
    started = time.monotonic()
    views, records, registration, extra, axis, sym_conf, sym_info = prepare(spec, options, note, check)
    grid, volume, protection, depth_stats = support(views, options, axis, note, check)
    report = analysis_report(views, records, registration, extra, axis, sym_conf, sym_info, options)
    report.update(engineVersion=ENGINE_VERSION, elapsedSeconds=round(time.monotonic() - started, 2))
    contact_sheet(output / 'views.png', views, None, (grid, volume))
    (output / 'analysis.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    note(100, 'Analysis complete')
    return {'report_file': str(output / 'analysis.json'), 'preview_file': str(output / 'views.png'), **summary(report)}


def summary(report):
    return {'real_view_count': sum(1 for v in report['views'] if v['IsReal']),
            'generated_view_count': sum(1 for v in report['views'] if v['IsGenerated']),
            'real_coverage_score': report['RealCoverageScore'],
            'expected_reconstruction_confidence': report['ExpectedReconstructionConfidence'],
            'symmetry_axis': report['symmetry']['axis'] or 'None', 'is_hypothesis': report['isHypothesis'],
            'missing_views': [k for k, v in report['coverage'].items() if v['status'] == 'MISSING']}


def construct(spec, output, note=None, check=None):
    note = note or (lambda *a, **k: None)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    options = resolve_options(spec.get('options', {}))
    started = time.monotonic()
    views, records, registration, extra, axis, sym_conf, sym_info = prepare(spec, options, note, check)
    grid, volume, protection, depth_stats = support(views, options, axis, note, check)
    report = analysis_report(views, records, registration, extra, axis, sym_conf, sym_info, options)
    note(44, 'Fitting cross-sections and primitives')
    excluded = [v.name for v in views if v.weight <= 0]
    all_views, views = views, usable(views)
    primitives, score, trace, diagnostics = fitting.build(grid, volume, views, options, axis, sym_conf, note, check)

    note(78, 'Assembling the proxy and unwrapping UVs (xatlas)')
    vertices, faces, owner, hidden, normals = texture.assemble(primitives)
    mapping, uv_faces, uv, charts = texture.unwrap(vertices, faces, options['texture_resolution'], options['texture_padding'])
    assert len(uv_faces) == len(faces), 'xatlas changed the face count'
    uv_vertices = vertices[mapping]
    note(82, 'Testing visibility and choosing the best camera per face')
    scores, _ = texture.face_views(uv_vertices, uv_faces, normals, views, options, check)
    scores[:, hidden] = 0
    note(88, 'Baking the BaseColor atlas')
    baked, known, face_source, face_view, _ = texture.bake(uv_vertices, uv_faces, uv, scores, views, options, check)
    atlas = texture.fill_unknown(baked, known, uv_vertices, uv_faces, uv, face_source, options)

    # Export: front = +Z, up = +Y (glTF convention); largest dimension = target_size.
    rotation = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], dtype=float)
    span = float((vertices.max(0) - vertices.min(0)).max())
    out_vertices = (uv_vertices @ rotation.T) * (options['target_size'] / max(span, 1e-9))
    visible = ~hidden
    names = [p.name for p in primitives]
    note(95, 'Writing GLB files and the report')
    mesh_file, parts_file = output / 'proxy.glb', output / 'proxy_parts.glb'
    texture.export_glb(mesh_file, out_vertices, uv_faces[visible], uv, atlas)
    texture.export_glb(parts_file, out_vertices, uv_faces, uv, atlas, names, owner)
    welded_v, welded_f = texture.weld((vertices @ rotation.T) * (options['target_size'] / max(span, 1e-9)),
                                      faces[visible], options['weld_tolerance'] * options['target_size'])
    geometry_file = output / 'proxy_geometry.obj'
    texture.export_obj(geometry_file, welded_v, welded_f)
    texture_file = output / 'basecolor.png'
    Image.fromarray(atlas).save(texture_file)
    contact_sheet(output / 'views.png', views, primitives, (grid, volume))

    world = 0.5 * np.linalg.norm(np.cross(uv_vertices[uv_faces][:, 1] - uv_vertices[uv_faces][:, 0],
                                          uv_vertices[uv_faces][:, 2] - uv_vertices[uv_faces][:, 0]), axis=1)
    area = world[visible].sum()
    sources = {name: round(float(world[visible & (face_source == i)].sum() / max(area, 1e-12)), 4)
               for i, name in enumerate(texture.SOURCES)}
    per_view = {}
    for i, view in enumerate(views):
        per_view[view.name] = round(float(world[visible & (face_view == i)].sum() / max(area, 1e-12)), 4)
    report.update({
        'engineVersion': ENGINE_VERSION, 'method': 'UNDERSTAND -> FIT -> CONSTRUCT (no dense mesh, no decimation)',
        'options': {k: v for k, v in options.items()}, 'supportVolume': {
            'gridResolution': grid.n, 'occupiedVoxels': int(volume.sum()), 'realViewProtection': protection,
            'excludedViews': excluded, 'depthCue': depth_stats},
        'analysis': diagnostics, 'FitScore': score, 'optimizationTrace': trace,
        'primitives': [p.describe() for p in primitives],
        'mesh': {'triangles': int(visible.sum()), 'trianglesSeparatedParts': int(len(uv_faces)),
                 'internalTrianglesRemoved': int(hidden.sum()), 'weldedVertices': int(len(welded_v)),
                 'weldedTriangles': int(len(welded_f)), 'uvVertices': int(len(uv_vertices)), 'uvCharts': charts,
                 'components': len(primitives), 'exportAxes': 'front +Z, up +Y, right -X (glTF)',
                 'largestDimension': options['target_size']},
        'texture': {'resolution': options['texture_resolution'], 'mode': options['texture_blend'],
                    'surfaceAreaBySource': sources, 'surfaceAreaByView': per_view,
                    'unknownOrder': ['generated view', 'mirrored real view', 'neighbouring texture extrapolation', 'neutral fallback']},
        'elapsedSeconds': round(time.monotonic() - started, 2)})
    report_file = output / 'report.json'
    report_file.write_text(json.dumps(report, indent=2, default=float), encoding='utf-8')
    note(100, 'Proxy mesh constructed')
    return {'mesh_file': str(mesh_file), 'parts_file': str(parts_file), 'geometry_file': str(geometry_file),
            'texture_file': str(texture_file), 'report_file': str(report_file), 'preview_file': str(output / 'views.png'),
            'triangles': int(visible.sum()), 'components': len(primitives), 'fit_score': score['FitScore'],
            'silhouette_agreement': score['SilhouetteAgreement'], **summary(report)}
