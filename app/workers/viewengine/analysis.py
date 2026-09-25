"""Analysis of the supplied images: segmentation, identity, viewpoints and coverage.

Viewpoints are **declared first**. A caller who supplies photographs normally knows
which one is the front or the left side, and a declared pose is exact. When a pose is
not declared the automatic estimator runs and reports what it could actually measure:

* roll and field of view from line segments and vanishing points, with their support;
* a relative azimuth between two images only when the baseline is narrow enough for an
  essential matrix to mean something, which excludes front-against-rear pairs;
* otherwise a coarse silhouette prior, or an explicit statement that the azimuth was
  not measured.

Why there is no learned absolute-pose predictor here is recorded in
``app/Docs/CapabilityCoverage.md`` together with the measurement that rejected the
analysis-by-synthesis variant.
"""
import math
from pathlib import Path

import numpy as np

import viewsets
from . import identity, imaging, pose, segment

#: An essential matrix is only trusted for baselines up to this angle.
GEOMETRIC_MAX_ANGLE = 60.0
GEOMETRIC_MIN_INLIERS = 20
GEOMETRIC_MIN_RATIO = 0.35


def declared_pose(source):
    """Return the declared ``(azimuth, elevation, roll, fov)`` or ``None``."""
    view = (source.get('view') or '').strip()
    if view and view.lower() not in ('auto', ''):
        if view not in viewsets.PRESETS:
            raise ValueError('Unknown preset view "%s". Use one of: %s, or Auto.'
                             % (view, ', '.join(viewsets.PRESET_NAMES)))
        azimuth, elevation = viewsets.preset_pose(view)
        return (azimuth, elevation, float(source.get('roll') or 0.0),
                source.get('fov'), 'declared-preset')
    if source.get('azimuth') is not None or source.get('elevation') is not None:
        return (float(source.get('azimuth') or 0.0), float(source.get('elevation') or 0.0),
                float(source.get('roll') or 0.0), source.get('fov'), 'declared-angles')
    return None


def trust_geometric(relation):
    """Accept a relative rotation only where an essential matrix is meaningful."""
    if relation is None:
        return False, 'Fewer than %d ratio-test correspondences survived.' % pose.MIN_MATCHES
    if relation['inliers'] < GEOMETRIC_MIN_INLIERS:
        return False, 'Only %d inliers supported the essential matrix.' % relation['inliers']
    if relation['inlierRatio'] < GEOMETRIC_MIN_RATIO:
        return False, 'The inlier ratio of %.2f is too low to trust the relative rotation.' \
            % relation['inlierRatio']
    if abs(relation['azimuth']) > GEOMETRIC_MAX_ANGLE:
        return False, ('The recovered rotation of %.0f degrees exceeds the %.0f degree limit '
                       'where two views of an unknown object still share enough surface.'
                       % (abs(relation['azimuth']), GEOMETRIC_MAX_ANGLE))
    return True, ''


def default_focal(width):
    return (width / 2.0) / math.tan(math.radians(pose.DEFAULT_FOV / 2.0))


def analyse(sources, *, segmentation_backend, model_dirs, device, progress=None, cancel=None,
            estimate_unknown=True):
    """Segment, compare and place every supplied image, then report the coverage."""
    def step(percent, message):
        if progress:
            progress(percent, message)
        if cancel:
            cancel()

    items, records, declared = [], [], []
    for index, source in enumerate(sources):
        step(5 + 30.0 * index / max(len(sources), 1), 'Segmenting %s' % source['name'])
        rgb, alpha, native = imaging.load_rgb(source['path'])
        result = segment.segment(rgb, alpha, backend=segmentation_backend,
                                 model_dir=model_dirs.get('sam2'), device=device)
        item = identity.prepare(rgb, result['mask'], name=source['name'])
        item.update(path=str(source['path']), native=native, segmentation=result)
        items.append(item)
        declared.append(declared_pose(source))
        records.append({'name': source['name'], 'path': str(source['path']),
                        'width': native[0], 'height': native[1],
                        'segmentation': {k: v for k, v in result.items() if k != 'mask'}})

    step(40, 'Comparing the supplied images')
    embeddings = None
    if model_dirs.get('dinov2'):
        embeddings = identity.embed([x['cropped'] for x in items], model_dirs['dinov2'], device)
    verdict = identity.same_object(items, embeddings)

    step(50, 'Measuring camera intrinsics')
    intrinsic_values = [pose.intrinsics(item['gray']) for item in items]

    relations, relative_azimuth, relative_elevation = [], [], []
    unknown = [i for i, value in enumerate(declared) if value is None]
    if estimate_unknown and unknown:
        step(60, 'Matching the images whose viewpoint was not declared')
        for position, i in enumerate(range(len(items))):
            for j in range(i + 1, len(items)):
                if cancel:
                    cancel()
                if i not in unknown and j not in unknown:
                    continue
                focal_i = intrinsic_values[i].get('focal') or default_focal(items[i]['native'][0])
                focal_j = intrinsic_values[j].get('focal') or default_focal(items[j]['native'][0])
                relation = pose.relative_rotation(items[i]['keypoints'], items[j]['keypoints'],
                                                  items[i]['native'], items[j]['native'],
                                                  focal_i, focal_j)
                trusted, reason = trust_geometric(relation)
                record = {'first': items[i]['name'], 'second': items[j]['name'],
                          'used': trusted, 'reason': reason}
                if relation:
                    record.update(relation)
                relations.append(record)
                if trusted:
                    relative_azimuth.append((i, j, relation['azimuth'], relation['confidence']))
                    relative_elevation.append((i, j, relation['elevation'], relation['confidence']))

    step(70, 'Placing the viewpoints')
    absolute_azimuth, absolute_elevation = [], []
    for index, value in enumerate(declared):
        if value is not None:
            absolute_azimuth.append((index, value[0], 20.0))
            absolute_elevation.append((index, value[1], 20.0))
    for index, values in enumerate(intrinsic_values):
        if declared[index] is None and values['pitch'] is not None \
                and values['pitchConfidence'] > 0.1:
            absolute_elevation.append((index, values['pitch'], values['pitchConfidence']))
    azimuths, azimuth_support = pose.solve_angles(len(items), relative_azimuth, absolute_azimuth)
    elevations, elevation_support = pose.solve_angles(len(items), relative_elevation,
                                                      absolute_elevation)

    views = []
    for index, item in enumerate(items):
        values = intrinsic_values[index]
        metrics = item['metrics']
        notes = list(values['notes'])
        declaration = declared[index]
        if declaration is not None:
            azimuth, elevation, roll = declaration[0], declaration[1], declaration[2]
            fov = declaration[3] if declaration[3] is not None else values['fov']
            source_kind = declaration[4]
            azimuth_confidence = elevation_confidence = 1.0
        else:
            azimuth, elevation = azimuths[index], elevations[index]
            roll = values['roll'] if values['rollConfidence'] > 0.1 else 0.0
            fov = values['fov']
            azimuth_confidence = float(np.clip(azimuth_support[index] / 2.0, 0.0, 0.9))
            elevation_confidence = float(np.clip(elevation_support[index] / 2.0, 0.0, 0.9))
            source_kind = 'estimated-geometric' if azimuth_support[index] > 0 else 'unmeasured'
            if azimuth_support[index] <= 0.0:
                prior = pose.silhouette_prior(metrics)
                azimuth, azimuth_confidence, source_kind = 0.0, prior[1], 'silhouette-prior'
                notes.append('The azimuth of this image was not measured. ' + prior[2]
                             + ' Declare its viewpoint to place it exactly.')
            if elevation_support[index] <= 0.0:
                notes.append('The elevation of this image was not measured; zero is assumed.')
        confidence = round(float(np.clip(
            0.5 * azimuth_confidence + 0.15 * elevation_confidence
            + 0.2 * item['segmentation']['confidence']
            + 0.15 * min(1.0, verdict['sameObjectConfidence']), 0.0, 1.0)), 4)
        view = viewsets.make_view(
            azimuth=azimuth, elevation=elevation, roll=roll, fov=fov, is_real=True,
            name=item['name'], image=str(item['path']), confidence=confidence,
            method=source_kind, notes=notes,
            extra={'poseSource': source_kind,
                   'azimuthConfidence': round(azimuth_confidence, 4),
                   'elevationConfidence': round(elevation_confidence, 4),
                   'rollConfidence': values['rollConfidence'],
                   'fovConfidence': values['fovConfidence'],
                   'fovMeasured': values['fov'] is not None,
                   'silhouetteMetrics': metrics,
                   'symmetry': metrics['symmetry'],
                   'sharpness': round(item['sharpness'], 2),
                   'lineSegments': values['lineSegments'],
                   'nativeWidth': item['native'][0], 'nativeHeight': item['native'][1],
                   'segmentation': records[index]['segmentation']})
        views.append(view)
        records[index]['view'] = view

    report = viewsets.coverage(views)
    step(80, 'Analysing coverage')
    declared_count = sum(1 for value in declared if value is not None)
    notes = []
    if declared_count < len(items):
        notes.append('%d of %d viewpoints were not declared. Automatic azimuth estimation is '
                     'only reliable for narrow baselines; declare the viewpoint of each '
                     'photograph for exact poses.' % (len(items) - declared_count, len(items)))
    return {
        'items': items,
        'images': records,
        'views': views,
        'coverage': report,
        'recommendations': viewsets.recommendations(report),
        'sameObject': verdict,
        'relations': relations,
        'declaredViewpoints': declared_count,
        'estimatedViewpoints': len(items) - declared_count,
        'notes': notes,
        'embeddings': embeddings,
    }
