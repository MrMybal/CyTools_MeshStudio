"""Small software rasteriser: silhouettes for fitting, z-buffer for occlusion tests."""
import cv2
import numpy as np


def silhouette(camera, vertices, faces, size=None):
    size = size or camera.size
    uv, depth = camera.project(vertices)
    if size != camera.size:
        uv = uv * (size / camera.size)
    image = np.zeros((size, size), np.uint8)
    visible = depth[faces].min(1) > 1e-4
    tris = np.round(uv[faces[visible]] * 16).astype(np.int32)
    for tri in tris:   # one call per triangle: fillPoly on a list applies the even-odd rule across faces
        cv2.fillConvexPoly(image, tri, 255, lineType=cv2.LINE_8, shift=4)
    return image > 0


def zbuffer(camera, vertices, faces, size=None):
    """Return (depth, face_index) images; background is inf / -1."""
    size = size or camera.size
    uv, z = camera.project(vertices)
    uv = uv * (size / camera.size)
    depth = np.full((size, size), np.inf, np.float32)
    index = np.full((size, size), -1, np.int32)
    for f, tri in enumerate(faces):
        zt = z[tri]
        if zt.min() <= 1e-4: continue
        p = uv[tri]
        x0, y0 = np.floor(p.min(0)).astype(int); x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0: continue
        a, b, c = p
        area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(area) < 1e-9: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        w0 = ((b[0] - xs) * (c[1] - ys) - (b[1] - ys) * (c[0] - xs)) / area
        w1 = ((c[0] - xs) * (a[1] - ys) - (c[1] - ys) * (a[0] - xs)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not inside.any(): continue
        # Perspective-correct depth: interpolate 1/z.
        zi = 1.0 / (w0 / zt[0] + w1 / zt[1] + w2 / zt[2]) if camera.fov > 0 else w0 * zt[0] + w1 * zt[1] + w2 * zt[2]
        region = depth[y0:y1 + 1, x0:x1 + 1]; labels = index[y0:y1 + 1, x0:x1 + 1]
        closer = inside & (zi < region)
        region[closer] = zi[closer]; labels[closer] = f
    return depth, index


def iou(a, b):
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 1.0
