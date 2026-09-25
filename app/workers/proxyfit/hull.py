"""Weighted visual-hull support volume. It is a fitting support, never the final mesh."""
import cv2
import numpy as np
from scipy import ndimage

EXTENT = 1.0


class Grid:
    def __init__(self, resolution):
        self.n = int(resolution)
        self.step = 2 * EXTENT / self.n
        axis = (np.arange(self.n) + .5) * self.step - EXTENT
        self.axis = axis
        x, y, z = np.meshgrid(axis, axis, axis, indexing='ij')
        self.points = np.stack([x.ravel(), y.ravel(), z.ravel()], -1)

    def index(self, points):
        return np.clip(((np.asarray(points) + EXTENT) / self.step).astype(int), 0, self.n - 1)


def _inside(view, points, dilate):
    mask = view.mask
    if dilate > 0:
        k = 2 * int(dilate) + 1
        mask = cv2.dilate(mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 0
    uv, depth = view.camera.project(points)
    px = np.floor(uv).astype(int)
    size = mask.shape[0]
    framed = (px[:, 0] >= 0) & (px[:, 1] >= 0) & (px[:, 0] < size) & (px[:, 1] < size)
    value = np.zeros(len(points), bool)
    value[framed] = mask[px[framed, 1], px[framed, 0]]
    if view.partial:
        value |= ~framed  # object cropped by the picture frame: outside the frame is unknown
    return value & (depth > 1e-4)


def carve(grid, views, real_tolerance=1, soft_tolerance=3, soft_threshold=0.75, check=None):
    """Real views carve strictly. Mirrored and generated views vote in two separate pools, by
    weight, so synthetic data can never tip a decision that belongs to real (mirrored) data."""
    occupied = np.ones(len(grid.points), bool)
    for view in (v for v in views if v.is_real):
        if check: check()
        occupied &= _inside(view, grid.points, real_tolerance)
    for kind in ('mirrored', 'generated'):
        pool = [v for v in views if v.kind == kind and v.weight > 0]
        if not pool: continue
        total = sum(v.weight for v in pool)
        votes = np.zeros(len(grid.points), np.float32)
        for view in pool:
            if check: check()
            votes += view.weight * _inside(view, grid.points, soft_tolerance)
        misses = max(1, int(round(0.12 * len(pool)))) if len(pool) > 1 else 0      # 6 views -> 1 miss, 16 views -> 2
        allowed = sum(sorted((v.weight for v in pool), reverse=True)[:misses])
        occupied &= votes >= min(soft_threshold * total, total - allowed) - 1e-6 if len(pool) <= 4 else votes >= total - allowed - 1e-6
    return occupied.reshape(grid.n, grid.n, grid.n)


def projection(grid, volume, view):
    """Silhouette of the occupied voxels in a view (splatted, then closed)."""
    points = grid.points[volume.ravel()]
    image = np.zeros(view.mask.shape, np.uint8)
    if len(points):
        uv, _ = view.camera.project(points)
        px = np.round(uv).astype(int)
        ok = (px[:, 0] >= 0) & (px[:, 1] >= 0) & (px[:, 0] < image.shape[1]) & (px[:, 1] < image.shape[0])
        image[px[ok, 1], px[ok, 0]] = 1
        k = max(3, int(np.ceil(view.camera.scale * grid.step * 1.6)) | 1)
        image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    return image > 0


def coverage(grid, volume, view):
    """Fraction of the mask explained by the support: silhouette coherence of this view."""
    area = view.mask.sum()
    return float((projection(grid, volume, view) & view.mask).sum() / area) if area else 0.0


def generated_votes(grid, views, tolerance=3):
    """Weighted fraction of the generated views that contain each voxel."""
    pool = [v for v in views if v.is_generated and v.weight > 0]
    votes = np.zeros(len(grid.points), np.float32)
    for view in pool:
        votes += view.weight * _inside(view, grid.points, tolerance)
    return votes / max(sum(v.weight for v in pool), 1e-9)


def protect_real_views(grid, views, check=None, gross=0.4, tolerance=0.02):
    """A synthetic view must never make the mesh contradict a real photograph.
    1. A generated view that, alone, would uncover more than `gross` of a real silhouette is garbage
       (wrong object, failed generation): it is excluded from geometry and texturing.
    2. The remaining generated views may shape the sides no real picture constrains, but every real
       pixel they would uncover is repaired: along that viewing ray the voxels of the real-only
       support that the generated views like best are put back. Real coverage is never reduced."""
    real = [v for v in views if v.is_real]
    trusted = [v for v in views if not v.is_generated]
    reference = carve(grid, trusted, check=check)
    notes = []
    if not any(v.is_generated and v.weight > 0 for v in views):
        return reference, notes
    baseline = {v.name: coverage(grid, reference, v) for v in real}
    for candidate in [v for v in views if v.is_generated and v.weight > 0]:
        alone = carve(grid, trusted + [candidate], check=check)
        loss = max(baseline[v.name] - coverage(grid, alone, v) for v in real)
        if loss > gross:
            notes.append({'view': candidate.name, 'action': 'excluded', 'reason': 'grossly contradicts a real silhouette',
                          'realCoverageLoss': round(float(loss), 4)})
            candidate.weight = 0.0; candidate.confidence = 0.0
    volume = carve(grid, views, check=check)
    if not any(v.is_generated and v.weight > 0 for v in views):
        return volume, notes
    votes = generated_votes(grid, views)
    flat, ref = volume.ravel().copy(), reference.ravel()
    distance = ndimage.distance_transform_edt(~volume) if volume.any() else np.zeros(volume.shape)
    restored = 0
    for view in real:
        if check: check()
        uv, _ = view.camera.project(grid.points)
        px = np.round(uv).astype(int); size = view.mask.shape[0]
        ok = (px[:, 0] >= 0) & (px[:, 1] >= 0) & (px[:, 0] < size) & (px[:, 1] < size)
        pixel = np.where(ok, px[:, 1] * size + px[:, 0], 0)
        kept = np.bincount(pixel[flat & ok], minlength=size * size) > 0
        candidates = ref & ~flat & ok & view.mask.ravel()[pixel] & ~kept[pixel]      # rays the synthetic views emptied
        if not candidates.any(): continue
        # Minimal repair: ONE voxel per emptied ray - the one the synthetic views like best and, among equals,
        # the closest to what they kept. Restoring whole rays would bring the fat real-only support back.
        index = np.nonzero(candidates)[0]
        priority = votes[index] - 1e-3 * distance.ravel()[index]
        order = np.lexsort((-priority, pixel[index]))
        first = np.unique(pixel[index][order], return_index=True)[1]
        chosen = index[order][first]
        flat[chosen] = True; restored += len(chosen)
    volume = flat.reshape(volume.shape)
    after = {v.name: coverage(grid, volume, v) for v in real}
    notes.append({'action': 'repaired', 'voxelsRestoredForRealSilhouettes': restored,
                  'realCoverageReference': {k: round(v, 4) for k, v in baseline.items()},
                  'realCoverageFinal': {k: round(v, 4) for k, v in after.items()}})
    if any(baseline[k] - after[k] > tolerance for k in baseline):      # should not happen; never trade real data for synthetic
        notes.append({'action': 'generated views ignored', 'reason': 'repair could not preserve the real silhouettes'})
        for v in views:
            if v.is_generated: v.weight = 0.0
        return reference, notes
    return volume, notes


def coherence(grid, views, check=None):
    """Mean silhouette coherence of the real/generated views for the current cameras."""
    volume = carve(grid, views, check=check)
    if not volume.any(): return 0.0
    return float(np.mean([coverage(grid, volume, v) for v in views if v.kind != 'mirrored']))


def sync_mirrors(views, axis):
    if not axis: return
    by_name = {v.name: v for v in views}
    for v in views:
        if v.kind == 'mirrored':
            v.camera = by_name[v.source_views[0]].camera.mirrored(axis)


def balance_scales(grid, views, iterations=5, check=None, axis=None, rounds=2):
    """Per-view scale and principal point are unknown after cropping. A quick bounding-box pass
    is followed by a coordinate descent that maximises the silhouette coherence.
    Real pictures are calibrated among themselves (generated views are ignored); each synthetic
    view is then fitted to that fixed frame, so a wrong generated view never moves a real camera."""
    trusted = [v for v in views if not v.is_generated]
    anchor = next((v for v in trusted if v.is_real), views[0])
    history = []
    for _ in range(iterations):
        volume = carve(grid, trusted, check=check)
        if not volume.any(): break
        change = 0.0
        for view in trusted:
            if view.kind == 'mirrored': continue
            proj = projection(grid, volume, view)
            if not proj.any(): continue
            py, px = np.nonzero(proj); my, mx = np.nonzero(view.mask)
            rw = (px.max() - px.min() + 1) / (mx.max() - mx.min() + 1)
            rh = (py.max() - py.min() + 1) / (my.max() - my.min() + 1)
            ratio = float(np.clip(min(rw, rh), 0.7, 1.0))
            if ratio < 0.97 and view is not anchor:
                view.camera.scale /= ratio; change = max(change, 1 - ratio)
            elif ratio < 0.97:
                for other in trusted:
                    if other is not anchor and other.kind != 'mirrored': other.camera.scale *= ratio
                change = max(change, 1 - ratio)
        sync_mirrors(views, axis)
        history.append(round(change, 4))
        if change < 0.03: break

    def descend(view, scope, scale=True):
        best = coherence(grid, scope, check)
        for big, small in ((0.08, 8.0), (0.03, 3.0), (0.012, 1.2)):
            for attribute in (('scale', 'cx', 'cy') if scale else ('cx', 'cy')):
                for sign in (1, -1):
                    while True:
                        cam = view.camera; saved = (cam.scale, cam.center.copy())
                        if attribute == 'scale': cam.scale *= 1 + sign * big
                        else: cam.center[0 if attribute == 'cx' else 1] += sign * small
                        sync_mirrors(views, axis)
                        value = coherence(grid, scope, check)
                        if value > best + 0.0015: best = value
                        else:
                            cam.scale, cam.center = saved; sync_mirrors(views, axis); break
        return best

    best = coherence(grid, trusted, check)
    for _ in range(rounds):
        before = best
        for view in trusted:
            if view.kind == 'real': best = descend(view, trusted, scale=view is not anchor)
        if best < before + 0.003: break
    generated = [v for v in views if v.is_generated and v.weight > 0]
    grouped = [v for v in generated if v.pixel_ratio]
    for view in generated:
        if not v_has_ratio(view): descend(view, trusted + [view])
    if grouped:
        history.append({'generatedGroup': calibrate_group(grid, trusted, grouped, check)})
    history.append({'coherence': round(best, 4)})
    return history


def v_has_ratio(view):
    return bool(getattr(view, 'pixel_ratio', None))


def calibrate_group(grid, trusted, group, check=None):
    """Views of one generator share a camera: a single scale (world units per source pixel) and a single
    3D offset of the look-at point are fitted for the whole group against the real-picture frame."""
    base = float(np.median([v.camera.scale / v.pixel_ratio for v in group]))
    origin = [v.camera.target.copy() for v in group]
    state = {'k': 1.0, 't': np.zeros(3)}
    def apply():
        for v, o in zip(group, origin):
            v.camera.scale = base * state['k'] * v.pixel_ratio
            v.camera.target = o + state['t']
    real = [v for v in trusted if v.is_real]
    def score():
        apply()
        volume = carve(grid, trusted + group, check=check)
        if not volume.any(): return 0.0
        kept = float(np.mean([coverage(grid, volume, v) for v in real]))
        fit = []
        for v in group:      # IoU, not coverage: a group placed too small would let the support overflow every synthetic mask
            proj = projection(grid, volume, v); union = (proj | v.mask).sum()
            fit.append((proj & v.mask).sum() / union if union else 0.0)
        return 0.5 * kept + 0.5 * float(np.mean(fit))
    best = score()
    for big, small in ((0.3, 0.3), (0.15, 0.16), (0.06, 0.06), (0.025, 0.025)):
        for key in ('k', 0, 1, 2):
            for sign in (1, -1):
                while True:
                    saved = (state['k'], state['t'].copy())
                    if key == 'k': state['k'] *= 1 + sign * big
                    else: state['t'][key] += sign * small
                    value = score()
                    if value > best + 0.0015: best = value
                    else:
                        state['k'], state['t'] = saved; break
    apply()
    return {'scaleFactor': round(state['k'], 4), 'targetOffset': [round(float(x), 4) for x in state['t']], 'coherence': round(best, 4)}


def refine_rig_azimuth(grid, views, axis, check=None, span=25, coarse=5):
    """Generated views are posed relative to their source picture, so source + generated views form a rigid
    rig. Turning the whole rig changes nothing between them; it only changes how the rig sits on the mirror
    plane. When the source azimuth is a mere estimate (depth axis, default), the rig angle that makes the
    mirrored pictures agree best with the synthetic views of the other side is a better estimate."""
    group = [v for v in views if v.is_generated and v.weight > 0 and v.source_views]
    if not axis or not group or not all(getattr(v, 'rig_refine', True) for v in group): return None
    by_name = {v.name: v for v in views}
    source = by_name.get(group[0].source_views[0])
    if source is None or source.pose_source.split('+')[0] in ('user', 'user-label', 'feature-registration'): return None
    rig = [source] + [v for v in group if v.source_views[0] == source.name]
    start = [v.camera.azimuth for v in rig]
    def score(delta):
        for v, a in zip(rig, start): v.camera.azimuth = a + delta
        sync_mirrors(views, axis)
        return coherence(grid, views, check)
    best, chosen = score(0.0), 0.0
    base = best
    for step, width in ((coarse, span), (1, coarse - 1)):
        centre = chosen
        for delta in np.arange(centre - width, centre + width + 0.1, step):
            value = score(float(delta))
            if value > best + 0.002: best, chosen = value, float(delta)
    score(chosen)
    if chosen: source.pose_source += '+synthetic-rig-refined'
    return {'source': source.name, 'azimuthCorrection': round(chosen, 1), 'coherenceBefore': round(base, 4), 'coherenceAfter': round(best, 4)}


def optimise_plane(grid, views, axis, check=None, span=0.3):
    """Slide the object across the mirror plane until real and mirrored silhouettes agree best."""
    i = 'xyz'.index(axis)
    real = [v for v in views if v.kind != 'mirrored']
    base = [v.camera.target[i] for v in real]
    best, chosen = -1.0, 0.0
    for width, count in ((span, 13), (span / 6, 7)):
        for offset in np.linspace(chosen - width, chosen + width, count):
            for v, b in zip(real, base): v.camera.target[i] = b + offset
            sync_mirrors(views, axis)
            value = coherence(grid, views, check)
            if value > best + 1e-4: best, chosen = value, float(offset)
    for v, b in zip(real, base): v.camera.target[i] = b + chosen
    sync_mirrors(views, axis)
    return {'offset': round(chosen, 4), 'coherence': round(best, 4)}


def refine_poses(grid, views, azimuth_range=20, elevation_range=10, step=5, check=None):
    """Coordinate search on views without a user pose: maximise mean silhouette coherence."""
    trusted = [v for v in views if not v.is_generated]
    def score(): return coherence(grid, trusted, check)
    free = [v for v in views if v.is_real and v.pose_source not in ('user', 'user-label')]
    if len([v for v in views if v.is_real]) < 2 or not free:
        return []
    log, best = [], score()
    for view in free:
        start = (view.camera.azimuth, view.camera.elevation)
        for attribute, span in (('azimuth', azimuth_range), ('elevation', elevation_range)):
            origin = getattr(view.camera, attribute); chosen = origin
            for delta in np.arange(-span, span + .1, step):
                if delta == 0: continue
                setattr(view.camera, attribute, origin + float(delta))
                value = score()
                if value > best + 0.004: best, chosen = value, origin + float(delta)
            setattr(view.camera, attribute, chosen)
        if (view.camera.azimuth, view.camera.elevation) != start:
            view.pose_source += '+silhouette-refined'
            log.append({'view': view.name, 'from': [round(start[0], 1), round(start[1], 1)],
                        'to': [round(view.camera.azimuth, 1), round(view.camera.elevation, 1)], 'coherence': round(best, 4)})
    return log


def orient_vertical_views(grid, views, candidates, check=None):
    """Top/bottom pictures have no natural 'up': try the four in-plane orientations."""
    log = []
    for view in candidates:
        results = []
        for azimuth in (0.0, 90.0, 180.0, 270.0):
            view.camera.azimuth = azimuth
            value = coherence(grid, [v for v in views if not v.is_generated], check)
            results.append((float(value), azimuth))
        best = max(results)
        view.camera.azimuth = best[1]; view.pose_source += '+orientation-search'
        log.append({'view': view.name, 'azimuth': best[1], 'coherence': round(best[0], 4)})
    return log


def recentre(grid, views, volume, fill=0.82, keep=None):
    """Move/scale all cameras so the support is centred and fills the working cube."""
    points = grid.points[volume.ravel()]
    if not len(points): return
    lo, hi = points.min(0), points.max(0)
    centre, half = (lo + hi) / 2, float((hi - lo).max() / 2) + grid.step
    if keep: centre['xyz'.index(keep)] = 0.0   # the mirror plane stays through the origin
    factor = fill * EXTENT / half
    for view in views:
        # x' = (x - centre) * factor keeps every projection identical.
        view.camera.target = (view.camera.target - centre) * factor
        view.camera.scale /= factor


def symmetry_score(volume, axis):
    """IoU between the support and its mirror image about the centred plane normal to axis."""
    mirrored = np.flip(volume, 'xyz'.index(axis))
    union = (volume | mirrored).sum()
    return float((volume & mirrored).sum() / union) if union else 0.0


def centre_on_plane(grid, views, volume, axis):
    """Shift cameras so the symmetry plane candidate passes through the support centroid."""
    i = 'xyz'.index(axis)
    points = grid.points[volume.ravel()]
    if not len(points): return
    shift = np.zeros(3); shift[i] = np.median(points[:, i])
    for view in views:
        view.camera.target = view.camera.target - shift


def depth_carve(grid, volume, views, margin=0.12, check=None):
    """Monocular depth as a low-confidence concavity cue: align each depth map to the support's
    own rendered depth (affine in inverse depth), then remove voxels clearly in front of it."""
    stats, votes, seen = [], np.zeros(volume.shape, np.float32), np.zeros(volume.shape, np.float32)
    flat = volume.ravel()
    points = grid.points[flat]
    for view in views:
        if view.depth is None or not view.is_real: continue
        if check: check()
        uv, z = view.camera.project(points)
        px = np.clip(np.round(uv).astype(int), 0, view.mask.shape[0] - 1)
        front = np.full(view.mask.shape, np.inf, np.float32)
        np.minimum.at(front, (px[:, 1], px[:, 0]), z.astype(np.float32))
        valid = np.isfinite(front) & view.mask
        if valid.sum() < 200: continue
        d = view.depth[valid].astype(np.float64)          # relative inverse depth, larger = closer
        target = 1.0 / front[valid].astype(np.float64)
        A = np.stack([d, np.ones_like(d)], 1)
        coeff = np.linalg.lstsq(A, target, rcond=None)[0]
        for _ in range(3):  # robust refit
            residual = np.abs(A @ coeff - target); keep = residual <= np.percentile(residual, 80)
            coeff = np.linalg.lstsq(A[keep], target[keep], rcond=None)[0]
        if coeff[0] <= 0:
            stats.append({'view': view.name, 'used': False, 'reason': 'depth anti-correlated with support'}); continue
        predicted = A @ coeff
        correlation = float(np.corrcoef(predicted, target)[0, 1])
        surface = np.full(view.mask.shape, np.nan, np.float32)
        surface[view.mask] = 1.0 / np.maximum(view.depth[view.mask] * coeff[0] + coeff[1], 1e-6)
        observed = surface[px[:, 1], px[:, 0]]
        inside_mask = view.mask[px[:, 1], px[:, 0]]
        gap = observed - z                                  # positive: voxel in front of the seen surface
        vote = (gap > margin * 2 * EXTENT) & inside_mask & np.isfinite(observed)
        # Never empty a viewing ray: the picture shows the object there, whatever the depth says.
        pixel = px[:, 1] * view.mask.shape[1] + px[:, 0]
        remaining = np.bincount(pixel, minlength=view.mask.size) - np.bincount(pixel[vote], minlength=view.mask.size)
        vote &= remaining[pixel] > 0
        weight = view.weight * max(correlation, 0.0)
        votes.ravel()[np.nonzero(flat)[0]] += weight * vote
        seen.ravel()[np.nonzero(flat)[0]] += weight * inside_mask
        stats.append({'view': view.name, 'used': True, 'correlation': round(correlation, 3),
                      'voxelsFlagged': int(vote.sum())})
    if not stats or not seen.any():
        return volume, stats
    carved = volume & ~((votes > 0.6 * np.maximum(seen, 1e-6)) & (votes > 0))
    # Keep the largest component; never let the cue remove more than 35 % of the support.
    labels, count = ndimage.label(carved)
    if count > 1:
        sizes = ndimage.sum(carved, labels, range(1, count + 1))
        carved = np.isin(labels, [i + 1 for i, s in enumerate(sizes) if s >= 0.05 * sizes.max()])
    if carved.sum() < 0.65 * volume.sum():
        stats.append({'rejected': 'depth cue would remove more than 35 % of the support'})
        return volume, stats
    for view in views:   # an auxiliary cue may never contradict a real silhouette
        if view.is_real and coverage(grid, carved, view) < coverage(grid, volume, view) - 0.015:
            stats.append({'rejected': 'depth cue would uncover part of the real silhouette of ' + view.name})
            return volume, stats
    return carved, stats


def bound_unconstrained(grid, volume, views, ratio=1.0, minimum=0.3):
    """No picture limits the object along an axis when the support runs through the whole working
    cube (single front view, two opposite views...). That extent is then an explicit, user-tunable
    assumption: `ratio` times the largest observed dimension, centred on the camera target."""
    notes, n = [], grid.n
    occupied = [np.nonzero(volume.any(axis=tuple(j for j in range(3) if j != a)))[0] for a in range(3)]
    from .cameras import direction
    # A camera looking along an axis says nothing about the extent on that axis: constraint = sin(angle).
    def constraint(a):
        return max((float(np.sqrt(max(0.0, 1.0 - direction(v.camera.azimuth, v.camera.elevation)[a] ** 2))) for v in views if v.weight > 0), default=0.0)
    open_axes = [a for a in range(3) if len(occupied[a]) and occupied[a][0] <= 1 and occupied[a][-1] >= n - 2 and constraint(a) < minimum]
    known = [int(occupied[a][-1] - occupied[a][0] + 1) for a in range(3) if a not in open_axes and len(occupied[a])]
    if not open_axes or not known: return volume, notes
    limit = max(2, min(n, int(round(ratio * max(known)))))
    for a in open_axes:
        lo = max(0, n // 2 - limit // 2); hi = min(n, lo + limit)
        keep = np.zeros(n, bool); keep[lo:hi] = True
        shape = [1, 1, 1]; shape[a] = n
        volume = volume & keep.reshape(shape)
        notes.append({'axis': 'XYZ'[a], 'assumedExtent': round(limit * grid.step, 4),
                      'reason': f'no view constrains this axis; assumed {ratio:g} x the largest observed dimension (unobserved_extent_ratio)'})
    return volume, notes


def clean(volume):
    volume = ndimage.binary_closing(volume, iterations=1) | volume
    labels, count = ndimage.label(volume)
    if count > 1:
        sizes = ndimage.sum(volume, labels, range(1, count + 1))
        volume = np.isin(labels, [i + 1 for i, s in enumerate(sizes) if s >= 0.02 * sizes.max()])
    return ndimage.binary_fill_holes(volume)
