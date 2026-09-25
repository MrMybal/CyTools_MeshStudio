"""Camera pose analysis: roll, field of view, elevation and relative azimuth.

The estimator is deliberately classical and measurable. Nothing here predicts an
absolute azimuth from a single image with a learned prior; what it does is:

* ``intrinsics``        line segments, vanishing points, roll, focal length and camera
                        pitch, with a confidence derived from the line support.
* ``relative_rotation`` masked SIFT correspondences between two real views, an
                        essential matrix and ``recoverPose``, giving the relative
                        rotation and therefore the azimuth/elevation difference.
* ``solve_azimuths``    a least-squares fit over the graph of pairwise differences.
* ``silhouette_prior``  a coarse, low-confidence fallback when two views share too
                        few correspondences to be related geometrically.

The absolute origin of the azimuth axis is not observable from an unknown object,
so it is either supplied by the caller (``anchor``) or chosen by the most bilaterally
symmetric silhouette; both cases are reported in ``anchorMethod``.
"""
import math
import numpy as np

from . import imaging

DEFAULT_FOV = 50.0
MIN_MATCHES = 12


def _detector():
    import cv2
    return cv2.SIFT_create(nfeatures=4000)


def line_segments(gray):
    """Line segments as an ``(n, 4)`` array, from LSD when available."""
    import cv2
    try:
        detector = cv2.createLineSegmentDetector()
        lines = detector.detect(gray)[0]
        if lines is not None and len(lines):
            return lines.reshape(-1, 4)
    except cv2.error:
        pass
    edges = cv2.Canny(gray, 60, 160, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 360, threshold=70,
                            minLineLength=max(20, gray.shape[0] // 20), maxLineGap=6)
    return np.zeros((0, 4)) if lines is None else lines.reshape(-1, 4).astype(np.float64)


def _homogeneous(segments):
    points_a = np.column_stack([segments[:, 0], segments[:, 1], np.ones(len(segments))])
    points_b = np.column_stack([segments[:, 2], segments[:, 3], np.ones(len(segments))])
    lines = np.cross(points_a, points_b)
    norm = np.linalg.norm(lines[:, :2], axis=1, keepdims=True)
    return lines / np.maximum(norm, 1e-9)


def vanishing_point(segments, lines, *, iterations=400, threshold=0.004, seed=7):
    """RANSAC over segment intersections. Returns ``(point, inliers)`` or ``None``."""
    if len(segments) < 6:
        return None
    rng = np.random.default_rng(seed)
    lengths = np.hypot(segments[:, 2] - segments[:, 0], segments[:, 3] - segments[:, 1])
    weights = lengths / max(lengths.sum(), 1e-9)
    best_point, best_mask, best_score = None, None, 0.0
    for _ in range(iterations):
        pair = rng.choice(len(segments), size=2, replace=False, p=weights)
        point = np.cross(lines[pair[0]], lines[pair[1]])
        if abs(point[2]) < 1e-9:
            point = point / max(np.linalg.norm(point[:2]), 1e-9)
        else:
            point = point / point[2]
        residual = np.abs(lines @ point) / max(np.linalg.norm(point), 1e-9)
        mask = residual < threshold
        score = float(lengths[mask].sum())
        if score > best_score:
            best_point, best_mask, best_score = point, mask, score
    if best_point is None or int(best_mask.sum()) < 4:
        return None
    return best_point, best_mask


def intrinsics(gray):
    """Roll, horizontal FOV and camera pitch from vertical/horizontal vanishing points."""
    height, width = gray.shape[:2]
    centre = np.array([width / 2.0, height / 2.0])
    segments = line_segments(gray)
    result = {'roll': 0.0, 'rollConfidence': 0.0, 'fov': None, 'fovConfidence': 0.0,
              'pitch': None, 'pitchConfidence': 0.0, 'lineSegments': int(len(segments)),
              'notes': []}
    if len(segments) < 8:
        result['notes'].append('Too few line segments for a vanishing point estimate.')
        return result
    angles = np.degrees(np.arctan2(segments[:, 3] - segments[:, 1], segments[:, 2] - segments[:, 0]))
    lengths = np.hypot(segments[:, 2] - segments[:, 0], segments[:, 3] - segments[:, 1])
    # Roll from segments close to vertical: their tilt is the image rotation.
    vertical = np.abs(np.abs(angles) - 90.0) < 30.0
    if vertical.sum() >= 4:
        tilt = np.where(angles[vertical] > 0, angles[vertical] - 90.0, angles[vertical] + 90.0)
        weight = lengths[vertical]
        median = float(np.average(tilt, weights=weight))
        spread = float(np.sqrt(np.average((tilt - median) ** 2, weights=weight)))
        result['roll'] = round(median, 3)
        result['rollConfidence'] = round(float(np.clip(1.0 - spread / 18.0, 0.0, 0.9)), 3)
    lines = _homogeneous(segments)
    vertical_lines = vanishing_point(segments[vertical], lines[vertical]) if vertical.sum() >= 6 else None
    horizontal = ~vertical
    horizontal_lines = vanishing_point(segments[horizontal], lines[horizontal]) if horizontal.sum() >= 6 else None
    focal = None
    if horizontal_lines is not None:
        point, mask = horizontal_lines
        remaining = np.where(horizontal)[0][~mask]
        if len(remaining) >= 6:
            second = vanishing_point(segments[remaining], lines[remaining], seed=13)
            if second is not None and abs(point[2]) > 1e-9 and abs(second[0][2]) > 1e-9:
                first_xy = point[:2] / point[2] - centre
                second_xy = second[0][:2] / second[0][2] - centre
                value = -float(first_xy @ second_xy)
                if value > 1.0:
                    candidate = math.sqrt(value)
                    angle = math.degrees(2 * math.atan(width / (2 * candidate)))
                    # Outside this range the "orthogonal" pair is almost certainly two
                    # spurious vanishing points, so the field of view stays unmeasured.
                    if 10.0 <= angle <= 120.0:
                        focal = candidate
                        result['fov'] = round(angle, 3)
                        result['fovConfidence'] = round(float(np.clip(
                            (mask.sum() + second[1].sum()) / 30.0, 0.05, 0.6)), 3)
                    else:
                        result['notes'].append(
                            'A vanishing point pair implied a %.0f degree field of view, which '
                            'is outside the plausible range, so it was rejected.' % angle)
    if focal is None:
        focal = (width / 2.0) / math.tan(math.radians(DEFAULT_FOV / 2.0))
        result['notes'].append('No orthogonal vanishing point pair; the field of view falls '
                               'back to %.0f degrees and is not measured.' % DEFAULT_FOV)
    if vertical_lines is not None:
        point, mask = vertical_lines
        if abs(point[2]) > 1e-9:
            offset = point[1] / point[2] - centre[1]
            if abs(offset) > 1e-6:
                # A camera pitched down by t puts the vertical vanishing point at
                # cy + f / tan(t); positive pitch therefore means looking down.
                pitch = math.degrees(math.atan2(focal, offset))
                pitch = pitch - 180.0 if pitch > 90.0 else pitch
                result['pitch'] = round(pitch, 3)
                result['pitchConfidence'] = round(float(np.clip(mask.sum() / 25.0, 0.05, 0.6)), 3)
        else:
            result['pitch'] = 0.0
            result['pitchConfidence'] = round(float(np.clip(mask.sum() / 25.0, 0.05, 0.5)), 3)
            result['notes'].append('Vertical lines are parallel: the camera is level.')
    result['focal'] = None if focal is None else round(float(focal), 2)
    return result


def symmetry_score(mask):
    """Best bilateral symmetry of the silhouette and the axis that achieves it."""
    binary = (mask > 127).astype(np.float32)
    box = imaging.bounding_box(mask)
    if box is None:
        return 0.0, None
    x, y, width, height = box
    crop = binary[y:y + height, x:x + width]
    best, axis = 0.0, x + width / 2.0
    for shift in np.linspace(-0.12, 0.12, 25):
        offset = int(round(shift * width))
        rolled = np.roll(crop, offset, axis=1)
        mirrored = rolled[:, ::-1]
        union = np.logical_or(rolled > 0.5, mirrored > 0.5).sum()
        if union == 0:
            continue
        score = float(np.logical_and(rolled > 0.5, mirrored > 0.5).sum()) / float(union)
        if score > best:
            best, axis = score, x + width / 2.0 - offset / 2.0
    return round(best, 4), round(float(axis), 2)


def silhouette_metrics(mask):
    """Scale-free silhouette descriptors used for priors and consistency checks."""
    import cv2
    box = imaging.bounding_box(mask)
    binary = (mask > 127).astype(np.uint8)
    area = float(binary.sum())
    if box is None or area <= 0:
        return {'aspect': 0.0, 'fill': 0.0, 'symmetry': 0.0, 'solidity': 0.0,
                'relativeArea': 0.0, 'hu': [0.0] * 7}
    x, y, width, height = box
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    solidity = 0.0
    if contours:
        largest = max(contours, key=cv2.contourArea)
        hull = cv2.contourArea(cv2.convexHull(largest))
        solidity = float(cv2.contourArea(largest) / hull) if hull > 0 else 0.0
    moments = cv2.moments(binary, binaryImage=True)
    hu = cv2.HuMoments(moments).reshape(-1)
    hu = [float(-np.sign(v) * np.log10(abs(v) + 1e-30)) for v in hu]
    return {'aspect': round(width / float(height), 4),
            'fill': round(area / float(width * height), 4),
            'symmetry': symmetry_score(mask)[0],
            'solidity': round(solidity, 4),
            'relativeArea': round(area / float(binary.size), 5),
            'hu': [round(v, 4) for v in hu]}


def masked_keypoints(gray, mask):
    detector = _detector()
    region = None if mask is None else (mask > 127).astype(np.uint8)
    return detector.detectAndCompute(gray, region)


def match_features(first, second, ratio=0.75):
    """Lowe ratio test over the two masked descriptor sets."""
    import cv2
    keypoints_a, descriptors_a = first
    keypoints_b, descriptors_b = second
    if descriptors_a is None or descriptors_b is None or len(keypoints_a) < 8 or len(keypoints_b) < 8:
        return np.zeros((0, 2)), np.zeros((0, 2))
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = matcher.knnMatch(descriptors_a, descriptors_b, k=2)
    points_a, points_b = [], []
    for pair in pairs:
        if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance:
            points_a.append(keypoints_a[pair[0].queryIdx].pt)
            points_b.append(keypoints_b[pair[0].trainIdx].pt)
    return np.array(points_a, dtype=np.float64), np.array(points_b, dtype=np.float64)


def relative_rotation(first, second, size_a, size_b, focal_a, focal_b):
    """Relative camera rotation between two views of the same object.

    Returns degrees of azimuth/elevation/roll difference with the inlier statistics
    that justify them. A wide baseline with too few correspondences returns ``None``.
    """
    import cv2
    points_a, points_b = match_features(first, second)
    if len(points_a) < MIN_MATCHES:
        return None
    centre_a = np.array([size_a[0] / 2.0, size_a[1] / 2.0])
    centre_b = np.array([size_b[0] / 2.0, size_b[1] / 2.0])
    focal = math.sqrt(max(focal_a, 1.0) * max(focal_b, 1.0))
    normalised_a = (points_a - centre_a) / focal
    normalised_b = (points_b - centre_b) / focal
    essential, mask = cv2.findEssentialMat(normalised_a, normalised_b, np.eye(3),
                                           method=cv2.RANSAC, prob=0.999, threshold=2.0 / focal)
    if essential is None or essential.shape != (3, 3):
        return None
    count, rotation, _, mask = cv2.recoverPose(essential, normalised_a, normalised_b,
                                               np.eye(3), mask=mask)
    inliers = int(mask.sum()) if mask is not None else 0
    if count < MIN_MATCHES or inliers < MIN_MATCHES:
        return None
    vector = cv2.Rodrigues(rotation)[0].reshape(-1)
    # Image y points down, so a rotation of the camera around the world up axis
    # appears as a negative y component of the rotation vector.
    azimuth = math.degrees(-vector[1])
    elevation = math.degrees(-vector[0])
    roll = math.degrees(vector[2])
    ratio = inliers / float(max(len(points_a), 1))
    confidence = float(np.clip(0.15 + 0.5 * ratio + min(inliers, 120) / 300.0, 0.0, 0.95))
    return {'azimuth': round(azimuth, 3), 'elevation': round(elevation, 3),
            'roll': round(roll, 3), 'matches': int(len(points_a)), 'inliers': inliers,
            'inlierRatio': round(ratio, 3), 'confidence': round(confidence, 3)}


def solve_angles(count, relative, absolute):
    """Least squares over angle constraints.

    ``relative`` holds ``(i, j, value_j - value_i, weight)`` and ``absolute`` holds
    ``(i, value_i, weight)``. Differences are used as supplied, so the caller must
    already have unwrapped them to the shortest arc. Returns the solved angles and,
    per index, the total constraint weight that supports it.
    """
    rows, values, weights = [], [], []
    for i, j, delta, weight in relative:
        row = np.zeros(count)
        row[j], row[i] = 1.0, -1.0
        rows.append(row)
        values.append(float(delta))
        weights.append(float(weight))
    for index, value, weight in absolute:
        row = np.zeros(count)
        row[index] = 1.0
        rows.append(row)
        values.append(float(value))
        weights.append(float(weight))
    if not rows:
        return [0.0] * count, [0.0] * count
    # A tiny pull towards zero keeps disconnected components determined.
    for index in range(count):
        row = np.zeros(count)
        row[index] = 1.0
        rows.append(row)
        values.append(0.0)
        weights.append(1e-3)
    matrix = np.array(rows) * np.array(weights)[:, None]
    target = np.array(values) * np.array(weights)
    solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    support = []
    for index in range(count):
        total = sum(w for i, j, _, w in relative if index in (i, j))
        total += sum(w for i, _, w in absolute if i == index)
        support.append(round(float(total), 4))
    return [float(v) for v in solution], support


def silhouette_prior(metrics):
    """Very coarse |azimuth| hint from the silhouette. Low confidence by construction."""
    symmetry, aspect = metrics['symmetry'], metrics['aspect']
    if symmetry >= 0.9:
        return 0.0, 0.25, 'High bilateral symmetry: a frontal or rear view. Front and rear ' \
                          'cannot be separated from the silhouette alone.'
    if symmetry >= 0.8:
        return 20.0, 0.15, 'Nearly symmetric silhouette: close to a frontal or rear view.'
    if aspect <= 0.55:
        return 90.0, 0.15, 'Narrow silhouette: close to a profile view; the side is not ' \
                           'determined by the silhouette alone.'
    return 45.0, 0.1, 'Asymmetric silhouette: a three-quarter view is likely; the exact ' \
                      'angle is not measured.'
