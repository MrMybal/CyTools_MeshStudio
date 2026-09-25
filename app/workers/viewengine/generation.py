"""Planning and execution of multi-view generation.

Two rules drive everything here:

* a real photograph is never silently replaced by a synthetic view; when a requested
  viewpoint is already covered by a real image the planner reuses that image and says so;
* a backend is only asked for poses it can actually reach, and the pose that was really
  produced is reported next to the pose that was requested, with their angular error.
"""
import numpy as np

import viewsets
from . import imaging, segment
from .backends import base

#: A requested view within this angle of a real photograph reuses the photograph.
REUSE_TOLERANCE = 15.0
#: Below this consistency score a generated view is flagged rather than accepted.
LOW_CONFIDENCE = 0.55


def neutralise(rgb, mask, size=224):
    """Crop the object onto a constant background so two views can be compared."""
    cropped_rgb, cropped_mask = imaging.crop_to_object(rgb, mask, margin=0.06)
    alpha = (cropped_mask > 127)[:, :, None].astype(np.float32)
    flat = np.zeros_like(cropped_rgb, dtype=np.float32)
    flat[:, :] = imaging.NEUTRAL
    blended = np.clip(cropped_rgb.astype(np.float32) * alpha + flat * (1 - alpha), 0, 255)
    return imaging.resize(blended.astype(np.uint8), (size, size))


def tile_mask(tile, alpha=None):
    """Mask of a generated tile: the matted alpha when present, else a background cut."""
    if alpha is not None:
        return segment.refine(imaging.binary_mask(alpha))
    values = np.asarray(tile).astype(np.int16)
    border = np.concatenate([values[0, :], values[-1, :], values[:, 0], values[:, -1]])
    background = np.median(border, axis=0)
    distance = np.abs(values - background).sum(axis=2)
    return segment.refine((distance > 38).astype(np.uint8) * 255)


def build_ring(backend, reference, parameters, *, progress=None, cancel=None):
    """Render the complete set of poses the backend reaches from one reference view."""
    from .backends import zero123plus
    condition = zero123plus.prepare_condition(
        reference['rgb'], reference['mask'],
        ratio=float(parameters.get('condition_ratio', 0.95)))
    result = backend.generate(condition, parameters, progress=progress, cancel=cancel)
    alphas = result.get('alphas')
    samples = []
    for index, (azimuth, elevation) in enumerate(backend.offsets):
        alpha = None if alphas is None else alphas[index]
        samples.append({
            'index': index,
            'relativeAzimuth': float(azimuth),
            'elevation': float(elevation),
            'rgb': np.asarray(result['views'][index]),
            'alpha': None if alpha is None else np.asarray(alpha),
            'mask': tile_mask(result['views'][index], alpha),
            'normal': None if result.get('normals') is None else np.asarray(result['normals'][index]),
        })
    return samples, result


def reachable_poses(backend, reference_view):
    """Absolute poses the backend reaches from a reference whose pose is known."""
    poses = []
    for index, (azimuth, elevation) in enumerate(backend.offsets):
        absolute_elevation = elevation if backend.elevation_absolute \
            else reference_view['elevation'] + elevation
        poses.append({'index': index,
                      'azimuth': viewsets.wrap180(reference_view['azimuth'] + azimuth),
                      'elevation': viewsets.clamp_elevation(absolute_elevation)})
    return poses


def plan(targets, real_views, generated_views, backend, references, *,
         reuse_tolerance=REUSE_TOLERANCE, allow_mirror=True, symmetry='auto',
         symmetry_scores=None, prefer_real=True):
    """Decide, for every requested pose, whether to reuse, mirror or generate.

    ``references`` maps a view name to the prepared image it was analysed from.
    Returns one plan entry per target, in the order the targets were requested.
    """
    entries = []
    available = list(real_views) + list(generated_views)
    for target in targets:
        pose = (target['azimuth'], target['elevation'])
        entry = {'target': {'azimuth': round(viewsets.wrap180(target['azimuth']), 3),
                            'elevation': round(viewsets.clamp_elevation(target['elevation']), 3),
                            'roll': round(viewsets.wrap180(target.get('roll', 0.0)), 3),
                            'name': target.get('name', '')},
                 'action': 'generate', 'reason': '', 'reference': '', 'sampleIndex': None,
                 'achieved': None, 'poseError': None, 'mirrorSource': ''}
        if prefer_real:
            match, distance = viewsets.existing_match(available, pose, reuse_tolerance, real_only=True)
            if match is not None:
                entry.update(action='reuse-real', reference=match['name'],
                             achieved={'azimuth': match['azimuth'], 'elevation': match['elevation']},
                             poseError=distance,
                             reason='A real photograph already covers this viewpoint within '
                                    '%.1f degrees; a real image is never replaced by a '
                                    'generated one.' % distance)
                entries.append(entry)
                continue
        if allow_mirror and symmetry != 'off':
            mirrored = viewsets.mirror_pose(target['azimuth'], target['elevation'],
                                            target.get('roll', 0.0))
            match, distance = viewsets.existing_match(real_views, mirrored[:2],
                                                      reuse_tolerance, real_only=True)
            score = (symmetry_scores or {}).get(match['name'] if match else '', 0.0)
            threshold = 0.82
            if match is not None and abs(viewsets.wrap180(target['azimuth'])) > 5.0 \
                    and (score >= threshold or symmetry == 'force'):
                entry.update(action='mirror', reference=match['name'], mirrorSource=match['name'],
                             achieved={'azimuth': viewsets.wrap180(-match['azimuth']),
                                       'elevation': match['elevation']},
                             poseError=distance,
                             reason='The opposite view exists and the silhouette symmetry score '
                                    'is %.3f; mirroring it is exact for a bilaterally symmetric '
                                    'object and costs no inference.' % score)
                entries.append(entry)
                continue
        if backend is None or not references:
            entry.update(action='unavailable',
                         reason='No generation backend is available for this viewpoint.')
            entries.append(entry)
            continue
        best = None
        for name, view in references.items():
            for candidate in reachable_poses(backend, view):
                error = viewsets.angular_distance(
                    (candidate['azimuth'], candidate['elevation']), pose)
                if best is None or error < best['poseError']:
                    best = {'reference': name, 'sampleIndex': candidate['index'],
                            'achieved': {'azimuth': candidate['azimuth'],
                                         'elevation': candidate['elevation']},
                            'poseError': round(error, 3)}
        entry.update(action='generate', **best)
        entry['reason'] = ('The backend reaches this viewpoint from "%s" with an angular error '
                           'of %.1f degrees.' % (best['reference'], best['poseError']))
        entries.append(entry)
    return entries


def compose_view(tile, mask, *, background, resolution, upscale):
    """Apply the requested background and output resolution to one generated tile."""
    notes = []
    native = (tile.shape[1], tile.shape[0])
    values, _ = imaging.compose_background(tile, mask, background)
    if resolution and resolution != native[0]:
        if resolution > native[0] and not upscale:
            notes.append('The backend renders %d pixels; the requested %d pixels were not '
                         'applied because resampling is disabled.' % (native[0], resolution))
        else:
            values = imaging.resize(values, (resolution, resolution))
            mask = imaging.resize(mask, (resolution, resolution), nearest=True)
            if resolution > native[0]:
                notes.append('Resampled from %d to %d pixels with a Lanczos filter. This is '
                             'resampling, not super resolution: no detail is added.'
                             % (native[0], resolution))
    return values, mask, native, notes


def evaluate(candidate_item, reference_items, embed, *, mirror_reference=None):
    """Consistency of one generated view against the real views of the same object."""
    from . import identity
    embeddings = None
    if embed is not None and reference_items:
        images = [candidate_item['cropped']] + [r['cropped'] for r in reference_items]
        embeddings = embed(images)
    return identity.consistency(candidate_item, reference_items, embeddings=embeddings,
                                mirror_reference=mirror_reference)


def confidence_of(consistency, pose_error, *, base_confidence=1.0):
    """Blend the consistency score with how far the achieved pose is from the request."""
    penalty = float(np.clip(1.0 - (pose_error or 0.0) / 90.0, 0.0, 1.0))
    value = 0.75 * consistency['confidence'] + 0.25 * penalty
    return round(float(np.clip(value * base_confidence, 0.0, 1.0)), 4)


def flag(confidence, notes):
    if confidence < LOW_CONFIDENCE:
        notes.append('Low confidence: the consistency checks did not confirm this view. '
                     'Review it before using it as a reconstruction input.')
        return 'LowConfidence'
    return 'Accepted'


def require_backend(backend_status):
    if not backend_status.get('implemented'):
        raise base.BackendUnavailable(
            'MissingBackend',
            'Backend "%s" has no adapter in this version.' % backend_status.get('id'))
    if not backend_status.get('available'):
        raise base.BackendUnavailable(
            'MissingModel',
            'Backend "%s" is not installed: %s. Open Installation to download it.'
            % (backend_status.get('id'), ', '.join(backend_status.get('missing', [])) or 'unknown'))
