"""View records: normalised canvases, weights, provenance and classical segmentation."""
import cv2
import numpy as np
from .cameras import Camera, label_for, wrap

WORK = 384      # silhouette / fitting canvas
TEXTURE = 1024  # colour canvas sampled by the texture baker


class View:
    def __init__(self, name, image, mask, camera, weight=1.0, kind='real', source_views=None,
                 depth=None, confidence=1.0, partial=False, pose_source='default'):
        self.name, self.image, self.mask, self.camera = name, image, mask, camera
        self.weight, self.kind, self.depth = float(weight), kind, depth
        self.source_views = list(source_views or [])
        self.confidence, self.partial, self.pose_source = float(confidence), bool(partial), pose_source
        self.requested = None
        self.pixel_ratio = None     # generated views: canvas pixels per source pixel (shared-camera calibration)
        self.coverage = None

    @property
    def is_real(self): return self.kind == 'real'
    @property
    def is_generated(self): return self.kind == 'generated'

    def mirrored(self, axis, confidence):
        flip = 0 if axis == 'y' else 1
        twin = View(self.name + '~mirror', np.ascontiguousarray(np.flip(self.image, flip)),
                    np.ascontiguousarray(np.flip(self.mask, flip)), self.camera.mirrored(axis),
                    self.weight * confidence, 'mirrored', [self.name],
                    None if self.depth is None else np.ascontiguousarray(np.flip(self.depth, flip)),
                    self.confidence * confidence, self.partial, 'symmetry')
        return twin

    def to_json(self):
        cam = self.camera
        value = {'name': self.name, 'IsReal': self.is_real, 'IsGenerated': self.is_generated,
                 'kind': self.kind, 'Azimuth': round(wrap(cam.azimuth) % 360, 2),
                 'Elevation': round(cam.elevation, 2), 'Roll': round(cam.roll, 2), 'FOV': round(cam.fov, 2),
                 'View': label_for(cam.azimuth, cam.elevation), 'Confidence': round(self.confidence, 3),
                 'Weight': round(self.weight, 3), 'SourceViews': self.source_views,
                 'poseSource': self.pose_source, 'partial': self.partial, 'hasDepth': self.depth is not None,
                 'silhouetteCoverage': None if self.coverage is None else round(self.coverage, 4),
                 'camera': cam.to_json()}
        if self.requested:
            value['RequestedAzimuth'], value['RequestedElevation'] = self.requested
        return value


def classical_mask(rgba):
    """Alpha channel when meaningful, otherwise border-colour background model + GrabCut.
    Returns (mask, method, confidence). Intended for concept images on plain backgrounds."""
    h, w = rgba.shape[:2]
    if rgba.shape[2] == 4:
        alpha = rgba[..., 3] > 127
        if 0.01 < alpha.mean() < 0.98:
            return _largest(alpha), 'alpha', 0.98
    rgb = np.ascontiguousarray(rgba[..., :3])
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    b = max(2, min(h, w) // 40)
    border = np.concatenate([lab[:b].reshape(-1, 3), lab[-b:].reshape(-1, 3),
                             lab[:, :b].reshape(-1, 3), lab[:, -b:].reshape(-1, 3)])
    median = np.median(border, 0)
    spread = float(np.median(np.linalg.norm(border - median, axis=1)))
    distance = np.linalg.norm(lab - median, axis=2)
    threshold = max(10.0, 3.5 * spread + 6.0)
    rough = distance > threshold
    rough = cv2.morphologyEx(rough.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    uniform = spread < 12.0
    if not uniform or not 0.01 < rough.mean() < 0.95:
        # Cluttered background: central rectangle prior refined by GrabCut.
        grab = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
        grab[h // 8:h - h // 8, w // 8:w - w // 8] = cv2.GC_PR_FGD
        grab[:b], grab[-b:], grab[:, :b], grab[:, -b:] = cv2.GC_BGD, cv2.GC_BGD, cv2.GC_BGD, cv2.GC_BGD
        method, confidence = 'grabcut-center', 0.35
    else:
        grab = np.where(rough, cv2.GC_PR_FGD, cv2.GC_BGD).astype(np.uint8)
        sure = cv2.erode(rough.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        grab[sure] = cv2.GC_FGD
        near = cv2.dilate(rough.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        grab[near & ~rough] = cv2.GC_PR_BGD
        method, confidence = 'border-colour+grabcut', 0.8
    scale = min(1.0, 512.0 / max(h, w))
    small = cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gsmall = cv2.resize(grab, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
    try:
        if (gsmall == cv2.GC_FGD).any() or (gsmall == cv2.GC_PR_FGD).any():
            cv2.grabCut(small, gsmall, None, np.zeros((1, 65)), np.zeros((1, 65)), 3, cv2.GC_INIT_WITH_MASK)
        result = np.isin(gsmall, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
        mask = cv2.resize(result, (w, h), interpolation=cv2.INTER_LINEAR) > 0
    except cv2.error:
        mask = rough
    if uniform:
        mask |= cv2.erode(rough.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return _largest(_fill(mask)), method, confidence


def _fill(mask):
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros(mask.shape, np.uint8)
    cv2.drawContours(out, contours, -1, 1, cv2.FILLED)
    return out > 0


def _largest(mask, keep=0.08):
    """Keep the main component and any detached piece larger than `keep` of it."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if count <= 2: return mask.astype(bool)
    areas = stats[1:, cv2.CC_STAT_AREA]
    wanted = [i + 1 for i, a in enumerate(areas) if a >= keep * areas.max()]
    return np.isin(labels, wanted)


def normalise(rgba, mask, margin=0.12):
    """Crop a square around the mask and resample to the working and texture canvases."""
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    if len(xs) < 16:
        raise ValueError('Empty object mask')
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    partial = bool(x0 <= 1 or y0 <= 1 or x1 >= w - 1 or y1 >= h - 1)
    side = max(x1 - x0, y1 - y0) * (1 + 2 * margin)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    def warp(source, size, interpolation):
        s = size / side
        matrix = np.array([[s, 0, size / 2 - cx * s], [0, s, size / 2 - cy * s]], np.float32)
        return cv2.warpAffine(source, matrix, (size, size), flags=interpolation, borderMode=cv2.BORDER_REPLICATE)
    rgb = np.ascontiguousarray(rgba[..., :3])
    image = warp(rgb, TEXTURE, cv2.INTER_AREA if side > TEXTURE else cv2.INTER_CUBIC)
    small = warp(mask.astype(np.uint8) * 255, WORK, cv2.INTER_AREA) > 127
    crop = {'centerX': float(cx), 'centerY': float(cy), 'side': float(side), 'sourceWidth': int(w), 'sourceHeight': int(h)}
    return image, small, partial, crop


def warp_like(array, crop, size=WORK):
    s = size / crop['side']
    matrix = np.array([[s, 0, size / 2 - crop['centerX'] * s], [0, s, size / 2 - crop['centerY'] * s]], np.float32)
    return cv2.warpAffine(array.astype(np.float32), matrix, (size, size), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def initial_camera(mask, azimuth, elevation, roll, fov, extent=0.75):
    """Camera whose scale maps the mask's largest half extent to `extent` world units."""
    ys, xs = np.nonzero(mask)
    half = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2.0 + 1e-6
    center = ((xs.min() + xs.max()) / 2.0 + .5, (ys.min() + ys.max()) / 2.0 + .5)
    return Camera(azimuth, elevation, roll, fov, half / extent, mask.shape[0], center)
