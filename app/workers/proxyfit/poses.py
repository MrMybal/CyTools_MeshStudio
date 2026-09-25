"""View pose estimation, real-view registration, same-object checks and coverage scores."""
import math
import cv2
import numpy as np
from .cameras import COVERAGE_ORDER, LABELS, angular_distance, direction, label_for, wrap

DEFAULT_AZIMUTH, DEFAULT_ELEVATION, DEFAULT_FOV = 35.0, 12.0, 35.0


def azimuth_from_depth(mask, depth, fov, elevation):
    """Long-axis direction of the back-projected relative depth cloud.
    Relative depth has no metric scale: the depth range is assumed comparable to the image
    extent, so the result is a hypothesis with moderate confidence. The near end of the long
    axis is taken as the front (usual three-quarter presentation)."""
    ys, xs = np.nonzero(mask)
    if len(xs) < 500: return None
    d = depth[ys, xs].astype(np.float64)
    lo, hi = np.percentile(d, [2, 98])
    if hi - lo < 1e-6: return None
    near = np.clip((d - lo) / (hi - lo), 0, 1)                 # 1 = closest
    size = mask.shape[0]
    half = max(np.ptp(xs), np.ptp(ys)) / 2.0
    x, y = (xs - xs.mean()) / half, -(ys - ys.mean()) / half
    z = (0.5 - near) * 2.0                                     # +z away from the camera, range about [-1, 1]
    cloud = np.stack([x, y, z], 1)
    values, vectors = np.linalg.eigh(np.cov(cloud.T))
    axis = vectors[:, int(np.argmax(values))]
    elong = float(values.max() / max(np.sort(values)[1], 1e-9))
    e = math.radians(elevation)                                # remove the camera tilt from the depth slope
    axis = np.array([axis[0], axis[1] * math.cos(e) - axis[2] * math.sin(e), axis[1] * math.sin(e) + axis[2] * math.cos(e)])
    if axis[2] > 0: axis = -axis                               # point the axis towards the camera = front
    horizontal = math.hypot(axis[0], axis[2])
    if horizontal < 1e-6: return None
    # Front on the image right means the camera stands on the object's right side (azimuth > 0).
    azimuth = math.degrees(math.atan2(axis[0], -axis[2]))
    confidence = float(np.clip(0.25 + 0.1 * math.log(max(elong, 1.0)), 0.25, 0.55))
    return wrap(azimuth), confidence, {'axisCamera': [round(float(a), 4) for a in axis], 'elongation': round(elong, 3)}


def camera_matrix(azimuth, elevation, roll):
    """World -> OpenCV camera rotation (x right, y down, z forward)."""
    a = math.radians(azimuth)
    forward = -direction(azimuth, elevation)
    right = np.array([math.sin(a), 0.0, -math.cos(a)])
    up = np.cross(right, forward)
    r = math.radians(roll)
    right, up = math.cos(r) * right + math.sin(r) * up, math.cos(r) * up - math.sin(r) * right
    return np.stack([right, -up, forward])


def angles_from_matrix(R):
    forward, right = R[2], R[0]
    d = -forward
    elevation = math.degrees(math.asin(float(np.clip(d[1], -1, 1))))
    azimuth = math.degrees(math.atan2(d[2], d[0]))
    a = math.radians(azimuth)
    base_right = np.array([math.sin(a), 0.0, -math.cos(a)])
    base_up = np.cross(base_right, forward)
    roll = math.degrees(math.atan2(float(right @ base_up), float(right @ base_right)))
    return wrap(azimuth), elevation, roll


def register(images, masks, fovs, check=None):
    """Classical pairwise registration (SIFT + essential matrix) restricted to the object."""
    sift = cv2.SIFT_create(nfeatures=4000)
    feats = []
    for image, mask in zip(images, masks):
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        region = cv2.resize(mask.astype(np.uint8) * 255, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_NEAREST)
        feats.append(sift.detectAndCompute(gray, region))
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = {}
    for i in range(len(images)):
        for j in range(i + 1, len(images)):
            if check: check()
            (ka, da), (kb, db) = feats[i], feats[j]
            entry = {'a': i, 'b': j, 'matches': 0, 'inliers': 0, 'usable': False}
            if da is not None and db is not None and len(ka) >= 8 and len(kb) >= 8:
                good = [m for m, n in (p for p in matcher.knnMatch(da, db, k=2) if len(p) == 2) if m.distance < 0.75 * n.distance]
                entry['matches'] = len(good)
                if len(good) >= 12:
                    pa = np.float32([ka[m.queryIdx].pt for m in good]); pb = np.float32([kb[m.trainIdx].pt for m in good])
                    size = images[i].shape[0]
                    f = (size / 2) / math.tan(math.radians(max(fovs[i], 5.0)) / 2)
                    K = np.array([[f, 0, size / 2], [0, f, size / 2], [0, 0, 1]])
                    E, inl = cv2.findEssentialMat(pa, pb, K, method=cv2.RANSAC, prob=0.999, threshold=1.5)
                    if E is not None and E.shape == (3, 3) and inl is not None:
                        count, R, t, _ = cv2.recoverPose(E, pa, pb, K, mask=inl.copy())
                        entry.update(inliers=int(count), usable=bool(count >= 20), rotation=R.tolist(),
                                     angle=round(math.degrees(math.acos(float(np.clip((np.trace(R) - 1) / 2, -1, 1)))), 2))
            pairs[(i, j)] = entry
    return pairs


def colour_similarity(images, masks):
    """Histogram correlation of the object pixels (Lab a/b): weak same-object evidence."""
    hists = []
    for image, mask in zip(images, masks):
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        region = cv2.resize(mask.astype(np.uint8) * 255, (lab.shape[1], lab.shape[0]), interpolation=cv2.INTER_NEAREST)
        h = cv2.calcHist([lab], [1, 2], region, [24, 24], [0, 256, 0, 256]); cv2.normalize(h, h)
        hists.append(h)
    out = {}
    for i in range(len(hists)):
        for j in range(i + 1, len(hists)):
            out[(i, j)] = float(cv2.compareHist(hists[i], hists[j], cv2.HISTCMP_CORREL))
    return out


def sphere(count=600):
    i = np.arange(count) + .5
    phi, theta = np.arccos(1 - 2 * i / count), math.pi * (1 + 5 ** .5) * i
    return np.stack([np.cos(theta) * np.sin(phi), np.cos(phi), np.sin(theta) * np.sin(phi)], 1)


def coverage_map(views, full=30.0, zero=75.0):
    """Per-direction status and the Real Coverage Score (mean over the view sphere)."""
    dirs = sphere()
    def field(selection, weighted):
        best = np.zeros(len(dirs))
        for v in selection:
            angle = np.degrees(np.arccos(np.clip(dirs @ direction(v.camera.azimuth, v.camera.elevation), -1, 1)))
            value = np.clip((zero - angle) / (zero - full), 0, 1) * (0.6 if v.partial else 1.0)
            best = np.maximum(best, value * (v.weight if weighted else v.confidence ** 0.5))
        return best
    real = [v for v in views if v.is_real]
    table = {}
    for name in COVERAGE_ORDER:
        az, el = LABELS[name]
        status, source, nearest = 'MISSING', None, None
        for kind, word in (('real', 'REAL'), ('mirrored', 'MIRRORED'), ('generated', 'GENERATED')):
            group = [v for v in views if v.kind == kind]
            if not group: continue
            v = min(group, key=lambda x: angular_distance(az, el, x.camera.azimuth, x.camera.elevation))
            angle = angular_distance(az, el, v.camera.azimuth, v.camera.elevation)
            if angle <= full:
                status, source, nearest = ('PARTIAL' if kind == 'real' and v.partial else word), v.name, angle; break
            if angle <= 55 and kind == 'real' and status == 'MISSING':
                status, source, nearest = 'PARTIAL', v.name, angle
        table[name] = {'status': status, 'view': source, 'angularDistance': None if nearest is None else round(nearest, 1)}
    real_score = float(field(real, False).mean()) if real else 0.0
    effective = float(np.maximum(field(real, False), field([v for v in views if not v.is_real], True)).mean())
    return table, real_score, effective


def expected_confidence(real_score, effective, views, coherence):
    real = [v for v in views if v.is_real]
    pose = float(np.mean([v.confidence for v in real])) if real else 0.0
    value = 0.45 * real_score + 0.2 * effective + 0.2 * pose + 0.15 * coherence
    if len(real) == 1: value = min(value, 0.5)   # a single picture is a volume hypothesis
    return float(np.clip(value, 0, 1)), {'formula': '0.45*RealCoverage + 0.20*EffectiveCoverage + 0.20*MeanPoseConfidence + 0.15*SilhouetteCoherence; capped at 0.5 for a single real image',
                                          'meanPoseConfidence': round(pose, 4), 'silhouetteCoherence': round(coherence, 4)}
