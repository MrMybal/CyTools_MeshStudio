"""Mesh assembly, xatlas UVs and camera projection baking with real occlusion tests."""
import cv2
import numpy as np
from scipy import ndimage
from . import raster

NEUTRAL = np.array([128, 128, 128], np.uint8)
SOURCES = ['real', 'mirrored', 'generated', 'extrapolated', 'neutral']


def assemble(primitives):
    """Concatenate parts and flag the faces buried inside another part (no CSG needed)."""
    vertices, faces, owner, offset = [], [], [], 0
    meshes = [p.mesh() for p in primitives]
    for i, (v, f) in enumerate(meshes):
        vertices.append(v); faces.append(f + offset); owner += [i] * len(f); offset += len(v)
    vertices, faces, owner = np.vstack(vertices), np.vstack(faces), np.array(owner)
    tri = vertices[faces]
    centroid = tri.mean(1)
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    samples = np.concatenate([centroid[:, None], 0.8 * tri + 0.2 * centroid[:, None]], 1)   # centroid + 3 inner points
    hidden = np.zeros(len(faces), bool)
    for i, p in enumerate(primitives):
        others = owner != i
        if not others.any(): continue
        pts = (samples[others] + 1e-4 * normal[others, None]).reshape(-1, 3)
        inside = p.contains(pts).reshape(-1, 4).all(1)
        hidden[np.nonzero(others)[0][inside]] = True
    return vertices, faces, owner, hidden, normal


def weld(vertices, faces, tolerance):
    """Merge close vertices and drop degenerate triangles (geometry-only output)."""
    key = np.round(vertices / max(tolerance, 1e-9)).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    f = inverse[faces]
    keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    f = f[keep]
    v = vertices[first]
    area = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
    return v, f[area > 1e-10]


def unwrap(vertices, faces, resolution, padding):
    import xatlas
    atlas = xatlas.Atlas()
    atlas.add_mesh(vertices.astype(np.float32), faces.astype(np.uint32))
    chart, pack = xatlas.ChartOptions(), xatlas.PackOptions()
    pack.resolution, pack.padding, pack.bilinear, pack.create_image = int(resolution), int(padding), True, False
    atlas.generate(chart_options=chart, pack_options=pack, verbose=False)
    mapping, new_faces, uv = atlas[0]
    return mapping, new_faces.astype(np.int64), uv.astype(np.float64), int(atlas.get_mesh_chart_count(0))


def face_views(vertices, faces, normals, views, options, check=None):
    """TextureViewScore = CameraFacing x PixelDensity x ViewConfidence x Visibility x RealViewBonus."""
    size = options['visibility_resolution']
    bonus = {'real': options['real_view_bonus'], 'mirrored': options['mirrored_view_bonus'],
             'generated': options['generated_view_bonus']}
    centroid = vertices[faces].mean(1)
    scores = np.zeros((len(views), len(faces)), np.float32)
    visible_fraction = np.zeros((len(views), len(faces)), np.float32)
    for i, view in enumerate(views):
        if check: check()
        _, index = raster.zbuffer(view.camera, vertices, faces, size)
        seen = np.bincount(index[index >= 0], minlength=len(faces)).astype(np.float32)
        uv, z = view.camera.project(vertices)
        p = uv[faces] * (size / view.camera.size)
        area = 0.5 * np.abs((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1]) - (p[:, 1, 1] - p[:, 0, 1]) * (p[:, 2, 0] - p[:, 0, 0]))
        visibility = np.clip(seen / np.maximum(area, 1.0), 0, 1)
        visibility[seen < 2] = 0
        to_camera = view.camera.position - centroid
        to_camera /= np.maximum(np.linalg.norm(to_camera, axis=1, keepdims=True), 1e-12)
        if view.camera.fov <= 0: to_camera = np.broadcast_to(-view.camera.basis()[2], centroid.shape)
        facing = np.clip(np.einsum('ij,ij->i', normals, to_camera), 0, 1)
        world = 0.5 * np.linalg.norm(np.cross(vertices[faces][:, 1] - vertices[faces][:, 0],
                                              vertices[faces][:, 2] - vertices[faces][:, 0]), axis=1)
        density = np.sqrt(area / np.maximum(world, 1e-12)); density /= max(float(density.max()), 1e-9)
        # The picture must actually show the object where the face lands.
        cu = np.clip(np.round(uv[faces].mean(1)).astype(int), 0, view.camera.size - 1)
        on_object = np.where(view.mask[cu[:, 1], cu[:, 0]], 1.0, 0.5)
        scores[i] = facing * (0.35 + 0.65 * density) * view.confidence * visibility * bonus[view.kind] * on_object
        scores[i][facing < options['min_facing']] = 0
        visible_fraction[i] = visibility
    return scores, visible_fraction


def bake(vertices, faces, uv, scores, views, options, check=None):
    """Rasterise faces in UV space, then colour every texel from its best (or blended) cameras."""
    res = options['texture_resolution']
    texture = np.zeros((res, res, 3), np.float32)
    weight = np.zeros((res, res), np.float32)
    source = np.full((res, res), -1, np.int8)
    order = np.argsort(-scores, axis=0)
    blend = options['texture_blend'] == 'blend'
    nearest = []
    for v in views:
        big = cv2.resize(v.mask.astype(np.uint8), (v.image.shape[1], v.image.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
        big = cv2.erode(big.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        _, idx = ndimage.distance_transform_edt(~big, return_indices=True)
        nearest.append(idx)
    face_source = np.full(len(faces), SOURCES.index('neutral'), np.int8)
    face_view = np.full(len(faces), -1, np.int32)
    for f, tri in enumerate(faces):
        if check and f % 64 == 0: check()
        ranked = [int(i) for i in order[:, f] if scores[i, f] > 0][: (options['blend_views'] if blend else 1)]
        if not ranked: continue
        p = uv[tri] * np.array([res, res]); p[:, 1] = res - p[:, 1]
        x0, y0 = np.floor(p.min(0)).astype(int) - 1; x1, y1 = np.ceil(p.max(0)).astype(int) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, res - 1), min(y1, res - 1)
        a, b, c = p
        area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(area) < 1e-9 or x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        w0 = ((b[0] - xs) * (c[1] - ys) - (b[1] - ys) * (c[0] - xs)) / area
        w1 = ((c[0] - xs) * (a[1] - ys) - (c[1] - ys) * (a[0] - xs)) / area
        w2 = 1 - w0 - w1
        margin = 1.5 / max(np.sqrt(abs(area)), 1.0)          # conservative: cover the chart border texels
        strict = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        # Border texels are only claimed when no face owns them yet: interiors are never smeared.
        inside = strict | ((w0 >= -margin) & (w1 >= -margin) & (w2 >= -margin) & (weight[y0:y1 + 1, x0:x1 + 1] == 0))
        if not inside.any(): continue
        bary = np.stack([np.clip(w0[inside], 0, 1), np.clip(w1[inside], 0, 1), np.clip(w2[inside], 0, 1)], -1)
        bary /= bary.sum(1, keepdims=True)
        points = bary @ vertices[tri]
        colour = np.zeros((len(points), 3), np.float32); total = np.zeros(len(points), np.float32)
        for i in ranked:
            view = views[i]
            pix, _ = view.camera.project(points)
            pix = pix * (view.image.shape[0] / view.camera.size)
            xi = np.clip(np.round(pix[:, 0]).astype(int), 0, view.image.shape[1] - 1)
            yi = np.clip(np.round(pix[:, 1]).astype(int), 0, view.image.shape[0] - 1)
            ny, nx = nearest[i][0][yi, xi], nearest[i][1][yi, xi]      # never sample the background
            wgt = float(scores[i, f]) ** 2
            colour += wgt * view.image[ny, nx].astype(np.float32); total += wgt
        ty, tx = ys[inside].astype(int), xs[inside].astype(int)
        texture[ty, tx] = colour / total[:, None]; weight[ty, tx] = 1
        face_source[f] = SOURCES.index(views[ranked[0]].kind); face_view[f] = ranked[0]
        source[ty, tx] = face_source[f]
    return texture, weight > 0, face_source, face_view, source


def fill_unknown(texture, known, vertices, faces, uv, face_source, options):
    """Unknown faces: neighbouring texture extrapolation, then a neutral fallback."""
    res = texture.shape[0]
    out = np.clip(texture, 0, 255).astype(np.uint8)
    unknown_faces = np.nonzero(face_source == SOURCES.index('neutral'))[0]
    if known.any() and len(unknown_faces):
        mean = out[known].reshape(-1, 3).mean(0)
        centroid = vertices[faces].mean(1)
        known_faces = np.nonzero(face_source != SOURCES.index('neutral'))[0]
        colours = {}
        for f in known_faces:
            p = uv[faces[f]].mean(0); x, y = int(p[0] * (res - 1)), int((1 - p[1]) * (res - 1))
            if known[y, x]: colours[f] = out[y, x].astype(np.float32)
        ids = np.array(list(colours)); table = np.array([colours[i] for i in ids]) if len(ids) else None
        for f in unknown_faces:
            if table is not None:
                d = np.linalg.norm(centroid[ids] - centroid[f], axis=1)
                near = np.argsort(d)[:4]; wts = 1.0 / np.maximum(d[near], 1e-6)
                colour = (table[near] * wts[:, None]).sum(0) / wts.sum()
                face_source[f] = SOURCES.index('extrapolated')
            else:
                colour = mean
            p = (uv[faces[f]] * np.array([res, res])); p[:, 1] = res - p[:, 1]
            cv2.fillConvexPoly(out, np.round(p).astype(np.int32), tuple(float(c) for c in colour))
            cv2.fillConvexPoly(known.view(np.uint8), np.round(p).astype(np.int32), 1)
    elif not known.any():
        out[:] = NEUTRAL
        return out
    # Gutter dilation so bilinear sampling never bleeds the empty atlas colour.
    mask = known.astype(np.uint8)
    for _ in range(options['texture_padding'] + 2):
        grown = cv2.dilate(mask, np.ones((3, 3), np.uint8))
        ring = (grown > 0) & (mask == 0)
        if not ring.any(): break
        blurred = cv2.blur(out.astype(np.float32) * mask[..., None], (3, 3))
        count = cv2.blur(mask.astype(np.float32), (3, 3))
        out[ring] = (blurred[ring] / np.maximum(count[ring], 1e-6)[:, None]).astype(np.uint8)
        mask = grown
    out[mask == 0] = NEUTRAL
    return out


def export_glb(path, vertices, faces, uv, texture, names=None, groups=None):
    """Write a textured GLB. `groups` (face -> part index) exports one named node per part."""
    import trimesh
    from PIL import Image
    image = Image.fromarray(texture)
    material = trimesh.visual.material.PBRMaterial(baseColorTexture=image, metallicFactor=0.0, roughnessFactor=0.85,
                                                   doubleSided=True, name='ProxyBaseColor')
    scene = trimesh.Scene()
    parts = [(None, np.arange(len(faces)))] if groups is None else \
        [(names[g], np.nonzero(groups == g)[0]) for g in np.unique(groups)]
    for name, idx in parts:
        f = faces[idx]; used, inverse = np.unique(f, return_inverse=True)
        mesh = trimesh.Trimesh(vertices[used], inverse.reshape(-1, 3), process=False,
                               visual=trimesh.visual.TextureVisuals(uv=uv[used], material=material))
        scene.add_geometry(mesh, node_name=name or 'proxy', geom_name=name or 'proxy')
    path.write_bytes(scene.export(file_type='glb'))


def export_obj(path, vertices, faces):
    with path.open('w', encoding='utf-8') as stream:
        stream.write('# CyTools_MeshConstruct welded proxy geometry (no UV)\n')
        for v in vertices: stream.write('v %.6f %.6f %.6f\n' % tuple(v))
        for f in faces + 1: stream.write('f %d %d %d\n' % tuple(f))
