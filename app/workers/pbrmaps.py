"""Deterministic UV-space rasterisation and PBR channel derivation. NumPy only, no mesh library.

Texel convention: column = u * resolution, row = (1 - v) * resolution, matching the UV
orientation trimesh uses for sampling and for glTF export.
"""
import numpy as np
from pbr_config import (CAVITY_GAIN, DETAIL_GAIN, DETAIL_RADIUS, DETAIL_SCALE, LUMINANCE_GAIN,
                    METAL_LUMINANCE_HIGH, METAL_LUMINANCE_LOW, METAL_SATURATION_HIGH, METAL_SATURATION_LOW)

NEIGHBOURS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))


def shift(array, dy, dx, fill):
    """array shifted so that result[y, x] == array[y + dy, x + dx]; outside reads become fill."""
    height, width = array.shape[:2]
    out = np.full_like(array, fill)
    out[max(0, -dy):height - max(0, dy), max(0, -dx):width - max(0, dx)] = \
        array[max(0, dy):height - max(0, -dy), max(0, dx):width - max(0, -dx)]
    return out


def smoothstep(edge0, edge1, values):
    """Monotonic 0..1 ramp; edge0 > edge1 produces a descending ramp."""
    t = np.clip((values - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def rasterize(uv, faces, resolution):
    """Return (face_index, barycentric): the covering triangle and weights of every texel.

    Overlapping UV islands are resolved by the last triangle written, as in a plain scanline bake.
    """
    face_index = np.full((resolution, resolution), -1, np.int32)
    barycentric = np.zeros((resolution, resolution, 3), np.float32)
    px = np.asarray(uv[:, 0], np.float64) * resolution - 0.5
    py = (1.0 - np.asarray(uv[:, 1], np.float64)) * resolution - 0.5
    faces = np.asarray(faces, np.int64)
    limit = resolution - 1
    for index in range(len(faces)):
        a, b, c = faces[index]
        ax, bx, cx = px[a], px[b], px[c]
        ay, by, cy = py[a], py[b], py[c]
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if det == 0.0:
            continue
        x0, x1 = max(0, int(np.floor(min(ax, bx, cx)))), min(limit, int(np.ceil(max(ax, bx, cx))))
        y0, y1 = max(0, int(np.floor(min(ay, by, cy)))), min(limit, int(np.ceil(max(ay, by, cy))))
        if x1 < x0 or y1 < y0:
            continue
        gx = np.arange(x0, x1 + 1, dtype=np.float64)[None, :]
        gy = np.arange(y0, y1 + 1, dtype=np.float64)[:, None]
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not inside.any():
            continue
        window = face_index[y0:y1 + 1, x0:x1 + 1]
        window[inside] = index
        weights = barycentric[y0:y1 + 1, x0:x1 + 1]
        weights[inside] = np.stack(np.broadcast_arrays(w0, w1, w2), axis=-1)[inside]
    return face_index, barycentric


def stamp_missing_faces(uv, faces, face_index, barycentric):
    """Give every triangle at least one texel; sub-texel triangles otherwise vanish."""
    resolution = face_index.shape[0]
    present = np.zeros(len(faces), bool)
    covered = face_index[face_index >= 0]
    if covered.size:
        present[np.unique(covered)] = True
    missing = np.flatnonzero(~present)
    if not missing.size:
        return 0
    centroid = np.asarray(uv, np.float64)[np.asarray(faces, np.int64)[missing]].mean(axis=1)
    column = np.clip((centroid[:, 0] * resolution).astype(np.int64), 0, resolution - 1)
    row = np.clip(((1.0 - centroid[:, 1]) * resolution).astype(np.int64), 0, resolution - 1)
    face_index[row, column] = missing
    barycentric[row, column] = 1.0 / 3.0
    return int(missing.size)


def grid_unwrap(faces, resolution, padding):
    """Give every triangle its own cell: no overlap ever, at the cost of texel efficiency.

    Returns (mapping, faces, uv) with the same shape contract as xatlas.parametrize, so the
    caller remaps per-vertex attributes identically. Each triangle is stretched onto the same
    right triangle, which distorts texel density but keeps barycentric interpolation exact.
    """
    count = len(faces)
    cells = int(np.ceil(np.sqrt(count)))
    step = 1.0 / cells
    inset = min(step * 0.25, (max(padding, 0) + 1.0) / max(resolution, 1))
    span = step - 2.0 * inset
    if span <= 0.0:
        raise ValueError('Too many triangles for this resolution; raise resolution or lower padding_pixels')
    index = np.arange(count)
    origin = np.stack([(index % cells) * step + inset, (index // cells) * step + inset], axis=1)
    corners = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]) * span
    return (np.asarray(faces, np.int64).ravel(), np.arange(count * 3, dtype=np.int64).reshape(count, 3),
            (origin[:, None, :] + corners[None, :, :]).reshape(-1, 2))


def interpolate(attributes, faces, face_index, barycentric):
    """Barycentric interpolation of a per-vertex attribute over the covered texels."""
    attributes = np.asarray(attributes, np.float32)
    covered = face_index >= 0
    out = np.zeros(face_index.shape + (attributes.shape[1],), np.float32)
    if covered.any():
        corners = np.asarray(faces, np.int64)[face_index[covered]]
        out[covered] = (attributes[corners] * barycentric[covered][:, :, None]).sum(axis=1)
    return out


def sample_image(image, uv):
    """Bilinear sample of a float image with glTF REPEAT wrapping; uv is (N, 2)."""
    height, width = image.shape[:2]
    x = (np.asarray(uv[:, 0], np.float64) % 1.0) * width - 0.5
    y = ((1.0 - np.asarray(uv[:, 1], np.float64)) % 1.0) * height - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    x0, x1 = x0 % width, (x0 + 1) % width
    y0, y1 = y0 % height, (y0 + 1) % height
    return ((image[y0, x0] * (1 - fx) + image[y0, x1] * fx) * (1 - fy) +
            (image[y1, x0] * (1 - fx) + image[y1, x1] * fx) * fy).astype(np.float32)


def nearest_fill(mask, iterations):
    """Flat index of the nearest covered texel, grown by exactly `iterations` texels.

    Each pass reads a snapshot, so one pass never grows the ring by more than one texel.
    """
    index = np.where(mask.ravel(), np.arange(mask.size, dtype=np.int32), np.int32(-1)).reshape(mask.shape)
    for _ in range(max(0, iterations)):
        if (index >= 0).all():
            break
        previous = index.copy()
        for dy, dx in NEIGHBOURS:
            source = shift(previous, dy, dx, np.int32(-1))
            take = (index < 0) & (source >= 0)
            if take.any():
                index[take] = source[take]
    return index


def pad_map(values, index):
    """Copy the nearest covered texel into the padding ring; texels never reached stay at 0."""
    flat = values.reshape(-1, values.shape[-1]) if values.ndim == 3 else values.reshape(-1, 1)
    filled = flat[np.maximum(index, 0).ravel()].reshape(index.shape + (flat.shape[1],))
    filled[index < 0] = 0.0
    return filled if values.ndim == 3 else filled[:, :, 0]


def box_statistics(values, radius, mask=None):
    """Windowed mean and standard deviation over a summed-area table (float64 accumulation).

    With a mask, only the selected texels contribute. Empty texels outside a UV island would
    otherwise read as black and inflate the local deviation along every island border.
    """
    values = np.asarray(values, np.float64)
    weights = np.ones_like(values) if mask is None else np.asarray(mask, np.float64)
    size = 2 * radius + 1

    def total(source):
        table = np.pad(np.pad(source, radius).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        return table[size:, size:] - table[:-size, size:] - table[size:, :-size] + table[:-size, :-size]

    count = np.maximum(total(weights), 1e-9)
    mean = total(values * weights) / count
    return mean, np.sqrt(np.maximum(total(values ** 2 * weights) / count - mean ** 2, 0.0))


def luminance(rgb):
    return (rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722).astype(np.float32)


def saturation(rgb):
    high = rgb[..., :3].max(axis=-1)
    return ((high - rgb[..., :3].min(axis=-1)) / np.maximum(high, 1e-6)).astype(np.float32)


def derive_roughness(rgb, roughness_value, mask=None):
    """Detail-driven roughness. A heuristic over albedo, never a measured material property."""
    detail = np.clip(box_statistics(luminance(rgb), DETAIL_RADIUS, mask)[1] / DETAIL_SCALE, 0.0, 1.0)
    bright = np.clip(luminance(rgb), 0.0, 1.0)
    return np.clip(roughness_value + DETAIL_GAIN * detail + LUMINANCE_GAIN * (0.5 - bright), 0.0, 1.0).astype(np.float32)


def derive_metallic(rgb, metallic_value):
    """Colour heuristic: desaturated and bright reads as metal. Verify it before trusting it."""
    score = (smoothstep(METAL_SATURATION_HIGH, METAL_SATURATION_LOW, saturation(rgb)) *
             smoothstep(METAL_LUMINANCE_LOW, METAL_LUMINANCE_HIGH, np.clip(luminance(rgb), 0.0, 1.0)))
    return np.clip(np.maximum(metallic_value, score), 0.0, 1.0).astype(np.float32)


def vertex_cavity(vertices, faces, normals):
    """Per-vertex concavity in [-1, 1]: positive inside cavities, negative on convex ridges."""
    vertices, faces = np.asarray(vertices, np.float64), np.asarray(faces, np.int64)
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.vstack([edges, edges[:, ::-1]])
    delta = vertices[edges[:, 1]] - vertices[edges[:, 0]]
    length = np.linalg.norm(delta, axis=1)
    keep = length > 1e-12
    edges, delta, length = edges[keep], delta[keep], length[keep]
    dot = (np.asarray(normals, np.float64)[edges[:, 0]] * (delta / length[:, None])).sum(axis=1)
    total, count = np.zeros(len(vertices)), np.zeros(len(vertices))
    np.add.at(total, edges[:, 0], dot)
    np.add.at(count, edges[:, 0], 1.0)
    return (total / np.maximum(count, 1.0)).astype(np.float32)


def apply_cavity_delight(rgb, cavity, strength):
    """Lift texels that sit in concave areas, where baked ambient shading accumulates."""
    gain = 1.0 + strength * CAVITY_GAIN * np.clip(cavity, 0.0, 1.0)
    return np.clip(rgb * gain[..., None], 0.0, 1.0).astype(np.float32)


def to_uint8(values):
    return np.clip(np.asarray(values, np.float32) * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
