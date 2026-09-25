"""UNDERSTAND -> FIT -> CONSTRUCT: cross-section lofts and primitives fitted to the support
volume, accepted progressively against every silhouette with an explicit complexity penalty."""
import math
import cv2
import numpy as np
from scipy import ndimage
from scipy.special import gamma
from . import raster
from .primitives import Loft, Extrusion, BOX_EXPONENT

PRESETS = {
    'UltraSimple': {'grid': 72, 'sections': 4, 'section_vertices': 6, 'parts': 4, 'polygon': 4, 'min_part': 0.025},
    'Simple': {'grid': 96, 'sections': 8, 'section_vertices': 8, 'parts': 8, 'polygon': 6, 'min_part': 0.010},
    'Medium': {'grid': 128, 'sections': 16, 'section_vertices': 12, 'parts': 16, 'polygon': 8, 'min_part': 0.004},
}
_EXPONENTS = np.array([1.0, 1.5, 2.0, 3.0, 4.0, 6.0, BOX_EXPONENT, 16.0])
_FILL = np.array([gamma(1 + 1 / n) ** 2 / gamma(1 + 2 / n) for n in _EXPONENTS])


def exponent_from_fill(ratio):
    return float(np.interp(np.clip(ratio, _FILL[0], _FILL[-1]), _FILL, _EXPONENTS))


# --------------------------------------------------------------------------- scoring
class Scorer:
    """FitScore = silhouette + depth + edge + multi-view + symmetry - complexity."""
    def __init__(self, views, weights, symmetry_confidence=0.0, size=192):
        self.views, self.w, self.size, self.symmetry = views, weights, size, symmetry_confidence
        self.masks, self.edges = [], []
        for v in views:
            m = cv2.resize(v.mask.astype(np.uint8), (size, size), interpolation=cv2.INTER_AREA) > 0
            self.masks.append(m)
            contour = m & ~ndimage.binary_erosion(m)
            self.edges.append((contour, ndimage.distance_transform_edt(~contour)))

    def _mesh(self, primitives):
        vs, fs, offset = [], [], 0
        for p in primitives:
            v, f = p.mesh(); vs.append(v); fs.append(f + offset); offset += len(v)
        return (np.vstack(vs), np.vstack(fs)) if vs else (np.zeros((0, 3)), np.zeros((0, 3), int))

    def silhouettes(self, primitives):
        v, f = self._mesh(primitives)
        return [raster.silhouette(view.camera, v, f, self.size) for view in self.views]

    def quick(self, primitives):
        """Cheap objective for coordinate descent: weighted IoU plus contour proximity."""
        total = weight = 0.0
        for view, mask, (contour, distance), sil in zip(self.views, self.masks, self.edges, self.silhouettes(primitives)):
            edge = sil & ~ndimage.binary_erosion(sil)
            d = distance[edge].mean() if edge.any() else self.size
            value = raster.iou(sil, mask) + 0.25 * math.exp(-d / (0.02 * self.size))
            total += view.weight * value; weight += view.weight
        return total / max(weight, 1e-9)

    def full(self, primitives, with_depth=True):
        v, f = self._mesh(primitives)
        ious, edges, depths, weights = [], [], [], []
        for view, mask, (contour, distance) in zip(self.views, self.masks, self.edges):
            sil = raster.silhouette(view.camera, v, f, self.size)
            ious.append(raster.iou(sil, mask)); weights.append(view.weight)
            edge = sil & ~ndimage.binary_erosion(sil)
            back = ndimage.distance_transform_edt(~edge)[contour].mean() if edge.any() and contour.any() else self.size
            forth = distance[edge].mean() if edge.any() else self.size
            edges.append(math.exp(-0.5 * (back + forth) / (0.02 * self.size)))
            if with_depth and view.depth is not None and view.is_real and len(f):
                z, _ = raster.zbuffer(view.camera, v, f, self.size)
                d = cv2.resize(view.depth.astype(np.float32), (self.size, self.size), interpolation=cv2.INTER_AREA)
                both = np.isfinite(z) & mask
                if both.sum() > 100 and d[both].std() > 1e-6:
                    depths.append(max(0.0, float(np.corrcoef(1.0 / z[both], d[both])[0, 1])))
        w = np.array(weights); w = w / w.sum()
        silhouette = float((np.array(ious) * w).sum())
        real = [i for i, view in zip(ious, self.views) if view.is_real] or ious
        terms = {'SilhouetteAgreement': silhouette, 'DepthAgreement': float(np.mean(depths)) if depths else None,
                 'EdgeAgreement': float((np.array(edges) * w).sum()), 'MultiViewAgreement': float(min(real)),
                 'SymmetryAgreement': self.symmetry if self.symmetry else None}
        triangles = int(len(f))
        penalty = self.w['complexity_primitive'] * len(primitives) + self.w['complexity_triangle'] * triangles / 100.0
        keys = {'SilhouetteAgreement': 'silhouette', 'DepthAgreement': 'depth', 'EdgeAgreement': 'edge',
                'MultiViewAgreement': 'multiview', 'SymmetryAgreement': 'symmetry'}
        used = {k: v for k, v in terms.items() if v is not None}
        norm = sum(self.w[keys[k]] for k in used) or 1.0
        score = sum(self.w[keys[k]] * v for k, v in used.items()) / norm - penalty
        return {'FitScore': round(score, 5), **{k: (None if v is None else round(v, 5)) for k, v in terms.items()},
                'ComplexityPenalty': round(penalty, 5), 'primitives': len(primitives), 'triangles': triangles,
                'perView': [{'view': view.name, 'iou': round(i, 4)} for view, i in zip(self.views, ious)]}


def expand(bases, axis):
    """Bases plus the mirrored twin of every off-plane primitive."""
    out = []
    for p in bases:
        out.append(p)
        if axis and getattr(p, 'twin', False):
            out.append(p.mirrored(axis, p.name.replace('right', 'left') if 'right' in p.name else p.name + '_mirror'))
    return out


# --------------------------------------------------------------------------- frames
def object_frame(main):
    """Local frame rows (along, up-ish, lateral) for a loft along object axis `main`."""
    e = np.eye(3)
    i = 'xyz'.index(main)
    up = e[1] if i != 1 else e[0]
    along = e[i]
    return np.stack([along, up, np.cross(along, up)])


def snap_direction(vector, angle):
    """Snap a unit vector to the nearest object axis when closer than `angle` degrees."""
    vector = vector / np.linalg.norm(vector)
    i = int(np.argmax(np.abs(vector)))
    if math.degrees(math.acos(min(1.0, abs(vector[i])))) <= angle:
        snapped = np.zeros(3); snapped[i] = np.sign(vector[i]); return snapped, True
    return vector, False


def frame_from_normal(normal, prefer=None):
    """Right-handed frame whose third row is `normal`, first row as axis-aligned as possible."""
    normal = normal / np.linalg.norm(normal)
    candidates = [np.eye(3)[i] for i in range(3)] if prefer is None else [prefer] + [np.eye(3)[i] for i in range(3)]
    best = max(candidates, key=lambda c: np.linalg.norm(c - normal * (c @ normal)) + (0.5 if prefer is not None and c is prefer else 0))
    x = best - normal * (best @ normal); x /= np.linalg.norm(x)
    return np.stack([x, np.cross(normal, x), normal])


# --------------------------------------------------------------------------- loft
def profile(points, axes, origin, step):
    """Slice statistics along local x: centre, half extents and superellipse exponent."""
    local = (points - origin) @ axes.T
    index = np.floor(local[:, 0] / step + 1e-6).astype(int)   # floor: voxel centres sit on half steps
    rows = []
    for i in np.unique(index):
        s = local[index == i]
        v0, v1, w0, w1 = s[:, 1].min(), s[:, 1].max(), s[:, 2].min(), s[:, 2].max()
        b, a = (v1 - v0 + step) / 2, (w1 - w0 + step) / 2
        fill = len(s) * step * step / (4 * a * b)
        rows.append(((i + .5) * step, (v0 + v1) / 2, (w0 + w1) / 2, a, b, exponent_from_fill(fill), len(s)))
    return np.array(rows)


def choose_knots(rows, limit, tolerance, mirrored=False):
    """Greedy piecewise-linear approximation of the width/height/centre profiles."""
    t = rows[:, 0]
    knots = [0, len(rows) - 1]
    def error():
        k = sorted(knots); worst, where = 0.0, None
        for c in (1, 2, 3, 4):
            approx = np.interp(t, t[k], rows[k, c]); diff = np.abs(approx - rows[:, c])
            j = int(np.argmax(diff))
            if diff[j] > worst: worst, where = float(diff[j]), j
        return worst, where
    trace = []
    while len(knots) < limit:
        worst, where = error()
        trace.append(round(worst, 5))
        if worst < tolerance or where is None or where in knots: break
        knots.append(where)
        if mirrored:
            twin = int(np.argmin(np.abs(t + t[where])))
            if twin not in knots and len(knots) < limit: knots.append(twin)
    return sorted(set(knots)), trace


def fit_loft(points, axes, origin, step, limit, vertices, symmetric_w, name='body', role='main', mirrored_t=False,
             force_round=None):
    rows = profile(points, axes, origin, step)
    if len(rows) < 2:
        return None, {}
    rows = rows[rows[:, 6] >= max(1, 0.02 * rows[:, 6].max())] if len(rows) > 4 else rows
    if symmetric_w: rows[:, 2] = 0.0
    core = rows[rows[:, 6] >= 0.35 * rows[:, 6].max()]
    exponent = float(np.median(core[:, 5]))
    boxy = exponent >= 5.0 if force_round is None else not force_round
    count = 4 if boxy else vertices
    n = BOX_EXPONENT if boxy else float(np.clip(exponent, 1.6, 4.0))
    knots, trace = choose_knots(rows, max(2, limit), 0.75 * step, mirrored_t)
    # A polygon inscribed in the superellipse is smaller than the slice: compensate the area.
    gain = 1.0 if boxy else math.sqrt((math.pi / count) / math.sin(math.pi / count)) if n <= 2.5 else 1.03
    sections = [{'t': rows[k, 0] + (-step / 2 if k == 0 else step / 2 if k == len(rows) - 1 else 0),
                 'cv': rows[k, 1], 'cw': rows[k, 2], 'a': rows[k, 3] * gain, 'b': rows[k, 4] * gain, 'n': n} for k in knots]
    loft = Loft(origin, axes, sections, count, name, role)
    return loft, {'sliceCount': int(len(rows)), 'medianExponent': round(exponent, 2), 'knotErrors': trace,
                  'sectionShape': 'box' if boxy else 'rounded'}


def body_envelope(points, axes, step, window):
    """Boolean mask of the points belonging to the main body (see build())."""
    local = points @ axes.T
    index = np.floor(local[:, 0] / step + 1e-6).astype(int); index -= index.min()
    n = index.max() + 1
    centre = np.array([np.median(local[:, 1]), np.median(local[:, 2])])
    extents = np.zeros((4, n))
    for i in range(n):
        s = local[index == i]
        if not len(s): continue
        extents[:, i] = [s[:, 1].max() - centre[0] + step / 2, centre[0] - s[:, 1].min() + step / 2,
                         s[:, 2].max() - centre[1] + step / 2, centre[1] - s[:, 2].min() + step / 2]
    size = max(3, int(round(window * n)) | 1)
    opened = np.array([ndimage.grey_opening(np.maximum(e, 0), size=size, mode='constant', cval=0.0) for e in extents])
    limit = np.minimum(np.maximum(extents, 0), opened * 1.08 + step)
    v, w = local[:, 1] - centre[0], local[:, 2] - centre[1]
    return (v <= limit[0, index]) & (-v <= limit[1, index]) & (w <= limit[2, index]) & (-w <= limit[3, index])


# --------------------------------------------------------------------------- parts
def outline(points2d, step, max_vertices, snap_angle):
    """Few-vertex polygon around a 2D point set (voxel centres projected on a plane)."""
    lo = points2d.min(0) - 2 * step
    px = np.round((points2d - lo) / step).astype(int)
    image = np.zeros((px[:, 1].max() + 3, px[:, 0].max() + 3), np.uint8)
    image[px[:, 1], px[:, 0]] = 255
    image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    big = cv2.resize(image, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    contours, _ = cv2.findContours(big, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea)
    epsilon = 0.01 * cv2.arcLength(contour, True)
    poly = cv2.approxPolyDP(contour, epsilon, True)
    while len(poly) > max_vertices and epsilon < 1e4:
        epsilon *= 1.25; poly = cv2.approxPolyDP(contour, epsilon, True)
    if len(poly) < 3:
        x, y, w, h = cv2.boundingRect(contour); poly = np.array([[[x, y]], [[x + w, y]], [[x + w, y + h]], [[x, y + h]]])
    polygon = (poly[:, 0, :].astype(float) - 1.5) / 4.0 * step + lo
    target = cv2.contourArea(contour) / 16.0 * step * step
    polygon = snap_polygon(polygon, snap_angle)
    area = abs(_area(polygon))
    if area > 1e-12:  # simplification changes the area: keep the measured one
        c = polygon.mean(0); polygon = c + (polygon - c) * math.sqrt(max(target, 1e-12) / area)
    return polygon, target


def _area(poly):
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def snap_polygon(polygon, angle):
    """Make nearly axis-parallel edges exactly parallel to the part's local axes."""
    if angle <= 0: return polygon
    poly = polygon.copy(); n = len(poly)
    for _ in range(2):
        for i in range(n):
            j = (i + 1) % n
            d = poly[j] - poly[i]
            theta = math.degrees(math.atan2(abs(d[1]), abs(d[0])))
            if theta <= angle: poly[i, 1] = poly[j, 1] = (poly[i, 1] + poly[j, 1]) / 2
            elif theta >= 90 - angle: poly[i, 0] = poly[j, 0] = (poly[i, 0] + poly[j, 0]) / 2
    return poly


def voxel_iou(primitive, points, neighbourhood):
    inside = primitive.contains(neighbourhood['points'])
    target = neighbourhood['target']
    union = (inside | target).sum()
    return float((inside & target).sum() / union) if union else 0.0


def fit_part(points, step, grid, volume, options, central, symmetry_axis, name):
    """Try extrusions and two-section lofts along snapped PCA axes; keep the best 3D IoU
    after the complexity penalty. Returns (primitive, diagnostics)."""
    centroid = points.mean(0)
    cov = np.cov((points - centroid).T) + np.eye(3) * 1e-12
    values, vectors = np.linalg.eigh(cov)
    order = np.argsort(values)[::-1]
    axes = [snap_direction(vectors[:, i], options['snap_angle'])[0] for i in order]
    if central and symmetry_axis:
        e = np.eye(3)['xyz'.index(symmetry_axis)]
        axes = sorted([e] + [np.eye(3)[i] for i in range(3) if not np.allclose(np.eye(3)[i], e)],
                      key=lambda a: -np.ptp(points @ a))
    extents = [float(np.ptp(points @ a) + step) for a in axes]
    lo, hi = points.min(0) - 3 * step, points.max(0) + 3 * step
    gp = grid.points
    near = np.all((gp >= lo) & (gp <= hi), axis=1)
    member = np.zeros(len(gp), bool); member[grid_index(grid, points)] = True
    hood = {'points': gp[near], 'target': member[near]}
    candidates = []
    for normal in axes:                                       # extrusions
        f = frame_from_normal(normal)
        local = (points - centroid) @ f.T
        thickness = float(np.ptp(local[:, 2]) + step)
        try:
            polygon, area = outline(local[:, :2], step, options['polygon'], options['snap_angle'])
        except (cv2.error, ValueError):
            continue
        solid = len(points) * step ** 3 / max(area, 1e-9)
        thickness = float(np.clip(solid, step, thickness))
        origin = centroid + f[2] * float(np.median(local[:, 2]))
        if central and symmetry_axis:
            origin = origin.copy(); i = 'xyz'.index(symmetry_axis)
            if abs(normal[i]) > 0.99: origin[i] = 0.0
        kind = None
        spans = np.ptp(polygon, axis=0)
        if len(polygon) == 3:
            kind = 'Wedge' if thickness > 0.5 * spans.min() else 'Prism'
        if options.get('thin_as_planes') and thickness <= 1.2 * step: kind = 'Plane'
        part = Extrusion(origin, f, polygon, thickness, name, 'thin' if thickness < 0.4 * spans.min() else 'secondary', kind)
        candidates.append(part)
    for along in axes[:2]:                                    # two-section lofts
        others = [a for a in axes if a is not along]
        up = max(others, key=lambda a: abs(a[1]))
        f = np.stack([along, up - along * (up @ along), np.zeros(3)])
        f[1] /= np.linalg.norm(f[1]); f[2] = np.cross(f[0], f[1])
        rows = profile(points, f, centroid, step)
        if len(rows) < 3: continue
        t = rows[:, 0]; wts = rows[:, 6]
        sections = []
        for end in (t.min() - step / 2, t.max() + step / 2):
            s = {'t': float(end), 'n': BOX_EXPONENT}
            for key, col in (('cv', 1), ('cw', 2), ('a', 3), ('b', 4)):
                slope, intercept = np.polyfit(t, rows[:, col], 1, w=wts)
                s[key] = float(slope * end + intercept)
            s['a'], s['b'] = max(s['a'], step / 2), max(s['b'], step / 2)
            sections.append(s)
        exponent = float(np.median(rows[:, 5]))
        if exponent < 4.0:
            for s in sections: s['n'] = 2.0
            for s in sections: s['a'] *= 1.05; s['b'] *= 1.05
        part = Loft(centroid, f, sections, 4 if exponent >= 4.0 else options['section_vertices'], name, 'secondary', tip=0.0)
        candidates.append(part)
    if not candidates:
        return None, {'reason': 'no candidate'}
    scored = []
    for part in candidates:
        value = voxel_iou(part, points, hood)
        triangles = len(part.mesh()[1])
        scored.append((value - options['part_triangle_penalty'] * triangles, value, part))
    scored.sort(key=lambda item: -item[0])
    best = scored[0]
    return best[2], {'voxelIoU': round(best[1], 4), 'penalised': round(best[0], 4),
                     'extents': [round(x, 4) for x in extents],
                     'candidates': [{'type': p.kind, 'voxelIoU': round(v, 4), 'triangles': int(len(p.mesh()[1]))} for _, v, p in scored]}


def grid_index(grid, points):
    i = grid.index(points)
    return (i[:, 0] * grid.n + i[:, 1]) * grid.n + i[:, 2]


def split_component(points, step, snap_angle):
    """Error-driven split. A poorly fitted mass is usually several plates meeting at an angle
    (fin + tailplanes, roof + wall): peel the slab with the largest footprint (plane detection on
    the snapped axes), then let the remainder fall apart into connected pieces. Falls back to a
    cut across the axis of largest spread."""
    centroid = points.mean(0)
    values, vectors = np.linalg.eigh(np.cov((points - centroid).T) + np.eye(3) * 1e-12)
    normals = [np.eye(3)[i] for i in range(3)]
    for i in range(3):
        v, snapped = snap_direction(vectors[:, i], snap_angle)
        if not snapped: normals.append(v)
    best = None
    for n in normals:
        coord = points @ n
        bins = np.floor((coord - coord.min()) / step + 1e-6).astype(int)
        counts = np.bincount(bins)
        if len(counts) < 5: continue                      # already a slab along this normal
        window = np.convolve(counts, np.ones(3), mode='valid')
        k = int(np.argmax(window))
        if best is None or window[k] > best[0]:
            best = (float(window[k]), n, bins, counts, k)
    if best and best[0] >= 0.2 * len(points) and best[0] <= 0.85 * len(points):
        _, n, bins, counts, k = best
        lo, hi, peak = k, k + 2, counts[k:k + 3].max()
        while lo > 0 and counts[lo - 1] >= 0.5 * peak: lo -= 1
        while hi < len(counts) - 1 and counts[hi + 1] >= 0.5 * peak: hi += 1
        slab = (bins >= lo) & (bins <= hi)
        if 0.15 * len(points) <= slab.sum() <= 0.9 * len(points):
            pieces = [points[slab]]
            rest = points[~slab]
            origin = rest.min(0)
            ijk = np.round((rest - origin) / step).astype(int)
            block = np.zeros(ijk.max(0) + 1, bool); block[tuple(ijk.T)] = True
            labels, count = ndimage.label(block, structure=np.ones((3, 3, 3)))
            tags = labels[tuple(ijk.T)]
            pieces += [rest[tags == i] for i in range(1, count + 1)]
            return pieces, 'plate peeling'
    side = (points - centroid) @ vectors[:, int(np.argmax(values))] > 0
    return [points[side], points[~side]], 'principal-axis cut'


# --------------------------------------------------------------------------- driver
def build(grid, volume, views, options, symmetry_axis, symmetry_confidence, progress=None, check=None):
    step = grid.step
    note = progress or (lambda *a, **k: None)
    scorer = Scorer(views, options['weights'], symmetry_confidence)
    trace, bases = [], []
    points_all = grid.points[volume.ravel()]

    # Level 0 - one main bounding volume.
    lo, hi = points_all.min(0), points_all.max(0)
    centre, size = (lo + hi) / 2, hi - lo + step
    from .primitives import box
    bounding = box(centre, size, name='bounding_volume'); bounding.role = 'main'; bounding.twin = False
    trace.append({'step': 'bounding volume', **scorer.full([bounding], with_depth=False), 'accepted': True})

    # Main body: appendages are bumps of the width/height profiles along the main axis. A visual
    # hull cannot show that a wing hidden by the fuselage is thin, so a volumetric opening is not
    # reliable; the lower envelope of the four extent profiles is.
    main = options.get('main_axis', 'Auto')
    spans = points_all.max(0) - points_all.min(0)
    main = 'xyz'[int(np.argmax(spans))] if main == 'Auto' else main.lower()
    axes = object_frame(main)
    body_mask = body_envelope(points_all, axes, step, options['body_window'])
    body_points = points_all[body_mask]
    radius = 0.0
    values, vectors = np.linalg.eigh(np.cov((points_all - points_all.mean(0)).T))
    principal = vectors[:, int(np.argmax(values))]
    deviation = math.degrees(math.acos(min(1.0, abs(principal['xyz'.index(main)]))))
    symmetric_w = bool(symmetry_axis) and abs(axes[2]['xyz'.index(symmetry_axis)]) > 0.99
    mirrored_t = bool(symmetry_axis) and abs(axes[0]['xyz'.index(symmetry_axis)]) > 0.99
    origin = np.zeros(3)
    if check: check()

    # Level 1..n - loft with a growing number of sections while the error keeps dropping.
    chosen, chosen_score, loft_info = None, -1e9, {}
    for count in range(2, options['sections'] + 1):
        if check: check()
        loft, info = fit_loft(body_points, axes, origin, step, count, options['section_vertices'], symmetric_w,
                              mirrored_t=mirrored_t)
        if loft is None: break
        loft.twin = False
        if len(loft.sections) < count and chosen is not None: break
        result = scorer.full([loft], with_depth=False)
        gain = result['FitScore'] - chosen_score
        accepted = chosen is None or gain > options['min_gain']
        trace.append({'step': f'body loft with {len(loft.sections)} sections', **result, 'gain': round(gain, 5), 'accepted': accepted})
        if accepted: chosen, chosen_score, loft_info = loft, result['FitScore'], info
        elif count >= 4: break
        note(45 + 15 * count / max(options['sections'], 2), 'Fitting cross-sections')
    if chosen is None or chosen_score < trace[0]['FitScore'] - 0.05:
        chosen = bounding; chosen_score = trace[0]['FitScore']
    bases.append(chosen)

    # Residual masses outside the body, largest first.
    member = np.zeros(len(grid.points), bool)
    member[np.nonzero(volume.ravel())[0][body_mask]] = True
    inside_loft = member.reshape(volume.shape) | chosen.contains(grid.points).reshape(volume.shape)
    residual = volume & ~inside_loft
    labels, count = ndimage.label(residual, structure=np.ones((3, 3, 3)))
    total = volume.sum()
    components = []
    for i in range(1, count + 1):
        comp = labels == i
        if comp.sum() < options['min_part'] * total: continue
        components.append(grid.points[comp.ravel()])
    components.sort(key=lambda p: -len(p))
    parts_info, index = [], 0
    queue = [(p, 0) for p in components]
    while queue and len(bases) - 1 < options['parts']:
        if check: check()
        points, depth = queue.pop(0)
        centroid = points.mean(0)
        central = twin = False
        if symmetry_axis:
            c = centroid['xyz'.index(symmetry_axis)]
            spread = np.ptp(points[:, 'xyz'.index(symmetry_axis)])
            if c < -max(step, 0.15 * spread): continue      # covered by the mirror of its twin
            central = abs(c) <= max(step, 0.15 * spread)
            twin = not central
            if twin: points = points[points[:, 'xyz'.index(symmetry_axis)] > -step / 2]
        index += 1
        name = f'part_{index:02d}' + ('_right' if twin else '')
        part, info = fit_part(points, step, grid, volume, options, central, symmetry_axis, name)
        if part is None: continue
        if info['voxelIoU'] < options['split_below'] and depth < 2 and len(points) > 60:
            pieces, how = split_component(points, step, options['snap_angle'])
            minimum = max(20, 0.5 * options['min_part'] * total)
            queue = sorted([(p, depth + 1) for p in pieces if len(p) > minimum], key=lambda item: -len(item[0])) + queue
            parts_info.append({'name': name, 'action': 'split', 'how': how, **info}); index -= 1; continue
        part.twin = twin
        candidate = bases + [part]
        result = scorer.full(expand(candidate, symmetry_axis), with_depth=False)
        gain = result['FitScore'] - chosen_score
        accepted = gain > options['min_gain']
        trace.append({'step': f'add {part.kind} {name}' + (' + mirror' if twin else ''), **result,
                      'gain': round(gain, 5), 'accepted': accepted})
        parts_info.append({'name': name, 'type': part.kind, 'accepted': accepted, 'central': central, 'mirrored': twin, **info})
        if accepted: bases, chosen_score = candidate, result['FitScore']
        note(60 + 15 * min(1.0, index / max(len(components), 1)), 'Fitting primitives')

    refine(bases, scorer, symmetry_axis, options, check)
    primitives = expand(bases, symmetry_axis)
    names = iter(['main_body'] + [f'component_{i:02d}' for i in range(1, 200)])
    for p in bases:
        new = next(names)
        for q in primitives:
            if q.mirror_of == p.name: q.mirror_of = new; q.name = new + '_mirror'
        p.name = new
    final = scorer.full(primitives, with_depth=True)
    trace.append({'step': 'silhouette refinement (final)', **final, 'accepted': True})
    diagnostics = {'mainAxis': main.upper(), 'principalAxis': [round(float(x), 4) for x in principal],
                   'principalAxisDeviationDegrees': round(deviation, 2),
                   'objectCenter': [round(float(x), 4) for x in points_all.mean(0)],
                   'boundingDimensions': {k: round(float(v), 4) for k, v in zip('XYZ', size)},
                   'bodyVoxelRatio': round(float(body_mask.mean()), 4), 'loft': loft_info, 'parts': parts_info}
    return primitives, final, trace, diagnostics


def refine(bases, scorer, symmetry_axis, options, check=None):
    """Coordinate descent of the few parameters of each primitive against all silhouettes.
    Plates also get a line search on thickness and offset: a visual hull over-estimates the
    thickness of any surface hidden behind the body, so the thinnest plate that explains the
    silhouettes equally well is preferred (hard-surface prior)."""
    def evaluate(): return scorer.quick(expand(bases, symmetry_axis))
    best = evaluate()
    for _ in range(options['refine_passes']):
        improved = False
        for p in bases:
            if isinstance(p, Extrusion) and p.kind != 'Plane':
                floor = max(options['min_thickness_ratio'] * float(np.ptp(p.polygon, axis=0).max()), 1e-3)
                for _ in range(8):
                    moved = False
                    for factor in (0.6, 0.8, 1.2):
                        if check: check()
                        old = p.thickness; p.thickness = max(old * factor, floor)
                        value = evaluate()
                        if value > best + 1e-4 or (factor < 1 and p.thickness < old and value >= best - 3e-4):
                            best, moved, improved = max(best, value), True, True
                        else: p.thickness = old
                    for sign in (1, -1):
                        old = p.origin.copy(); p.origin = old + sign * 0.35 * p.thickness * p.axes[2]
                        if symmetry_axis and not getattr(p, 'twin', False):
                            p.origin['xyz'.index(symmetry_axis)] = old['xyz'.index(symmetry_axis)]
                        value = evaluate()
                        if value > best + 1e-4: best, moved, improved = value, True, True
                        else: p.origin = old
                    if not moved: break
            handles = []
            if isinstance(p, Loft):
                for s in p.sections:
                    handles += [(s, 'a', 'mul'), (s, 'b', 'mul'), (s, 'cv', 'add')]
            else:
                handles += [(p, 'polygon', 'scale')]
            for target, key, mode in handles:
                for delta in (0.06, -0.06, 0.03, -0.03):
                    if check: check()
                    old = target[key] if isinstance(target, dict) else getattr(target, key)
                    if mode == 'mul': new = old * (1 + delta)
                    elif mode == 'add': new = old + delta * 0.25
                    else:
                        c = old.mean(0); new = c + (old - c) * (1 + delta)
                    if isinstance(target, dict): target[key] = new
                    else: setattr(target, key, new)
                    value = evaluate()
                    if value > best + 1e-4:
                        best, improved = value, True
                    else:
                        if isinstance(target, dict): target[key] = old
                        else: setattr(target, key, old)
        if not improved: break
    return best
