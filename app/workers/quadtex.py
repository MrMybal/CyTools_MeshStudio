"""Unwrap a remeshed model and write it back with its quads.

A quad remesh (QuadWild, AutoRemesher) is only worth something if the quads survive to the file
the artist opens. Two things destroy them on the way to a texture: every texture pipeline works
on triangles, and glTF cannot carry a quad at all. This module keeps the polygon faces aside,
triangulates them in a known order, unwraps the triangles with xatlas, and then rebuilds each
polygon with the UV of every one of its corners.

xatlas can place a seam across the diagonal of a quad; that quad then has two UVs at the same
corner and cannot stay a quad. It is written as its two triangles and counted, so the report says
exactly how many polygons were kept.

No GPU and no model here: this is tested on its own (app/tests/test_quadtex.py).
"""
from pathlib import Path

import numpy as np


def read_polygons(path):
    """(positions N×3 float64, list of polygons as tuples of vertex indices).

    An OBJ is parsed by hand because every mesh library triangulates it on load, which is the
    very thing this module exists to avoid. Any other format is read with trimesh, and its
    faces are then triangles.
    """
    path = Path(path)
    if path.suffix.lower() == '.obj':
        positions, polygons = [], []
        with path.open('r', encoding='utf-8', errors='replace') as handle:
            for line in handle:
                if line.startswith('v '):
                    parts = line.split()
                    positions.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif line.startswith('f '):
                    corners = []
                    for token in line.split()[1:]:
                        index = int(token.split('/')[0])
                        corners.append(index - 1 if index > 0 else len(positions) + index)
                    if len(corners) >= 3:
                        polygons.append(tuple(corners))
        if not positions or not polygons:
            raise ValueError(f'{path.name} holds no geometry')
        return np.asarray(positions, dtype=np.float64), polygons

    import trimesh
    mesh = load_mesh(path)
    return np.asarray(mesh.vertices, dtype=np.float64), [tuple(face) for face in np.asarray(mesh.faces)]


def load_mesh(path):
    """One trimesh with the scene transforms applied; its visual is kept when there is one."""
    import trimesh
    loaded = trimesh.load(str(path), process=False)
    if isinstance(loaded, trimesh.Scene):
        geometries = loaded.dump() if hasattr(loaded, 'dump') else list(loaded.geometry.values())
        geometries = [item for item in geometries if isinstance(item, trimesh.Trimesh)]
        if not geometries:
            raise ValueError(f'{Path(path).name} holds no mesh')
        if len(geometries) == 1:
            return geometries[0]
        return trimesh.util.concatenate(geometries)
    return loaded


def triangulate(polygons):
    """Fan-triangulate every polygon. Returns (triangles T×3, owner polygon of each triangle)."""
    triangles, owner = [], []
    for index, polygon in enumerate(polygons):
        for k in range(1, len(polygon) - 1):
            triangles.append((polygon[0], polygon[k], polygon[k + 1]))
            owner.append(index)
    return np.asarray(triangles, dtype=np.uint32), np.asarray(owner, dtype=np.int64)


def unwrap(positions, triangles, padding=4, resolution=0):
    """xatlas on the triangles: (vmapping, indices T×3, uvs V×2).

    ``indices`` follows the order of ``triangles``, and ``vmapping[i]`` is the input vertex
    output vertex ``i`` was made from — which is what lets the polygons be rebuilt.
    """
    import xatlas

    atlas = xatlas.Atlas()
    atlas.add_mesh(positions.astype(np.float32), triangles.astype(np.uint32))
    chart_options = xatlas.ChartOptions()
    pack_options = xatlas.PackOptions()
    pack_options.padding = int(padding)
    if resolution:
        pack_options.resolution = int(resolution)
    atlas.generate(chart_options, pack_options)
    vmapping, indices, uvs = atlas[0]
    return np.asarray(vmapping), np.asarray(indices, dtype=np.int64), np.asarray(uvs, dtype=np.float64)


def rebuild_polygons(polygons, owner, indices, vmapping):
    """Give every polygon corner its UV vertex; split the polygons a seam cuts through.

    Returns (faces, kept, split): ``faces`` is a list of tuples of (position index, UV index)
    per corner, ready for an OBJ; ``kept`` counts polygons written whole, ``split`` those
    written as their triangles.
    """
    by_polygon = {}
    for triangle, polygon in enumerate(owner):
        by_polygon.setdefault(int(polygon), []).append(triangle)

    faces, kept, split = [], 0, 0
    for index, polygon in enumerate(polygons):
        triangles = by_polygon.get(index, [])
        corner_uv = {}
        consistent = True
        for triangle in triangles:
            for uv_vertex in indices[triangle]:
                position = int(vmapping[uv_vertex])
                previous = corner_uv.setdefault(position, int(uv_vertex))
                if previous != int(uv_vertex):
                    consistent = False
        if consistent and len(polygon) > 3 and all(corner in corner_uv for corner in polygon):
            faces.append(tuple((corner, corner_uv[corner]) for corner in polygon))
            kept += 1
            continue
        if len(polygon) > 3:
            split += 1
        else:
            kept += 1
        for triangle in triangles:
            faces.append(tuple((int(vmapping[uv_vertex]), int(uv_vertex))
                               for uv_vertex in indices[triangle]))
    return faces, kept, split


def write_obj(path, positions, uvs, faces, material_name='material', maps=None):
    """OBJ with one ``vt`` per UV vertex and ``f v/vt`` corners, plus its MTL.

    ``maps`` names the texture files next to it: base_color, normal, roughness, metallic.
    The MTL uses the PBR extension (``map_Pr``, ``map_Pm``, ``norm``) that Blender and most
    DCC importers read; ``map_Kd`` carries the base colour for the others.
    """
    path = Path(path)
    maps = maps or {}
    mtl = path.with_suffix('.mtl')
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write('# CyTools_MeshStudio - quads kept, UV per corner\n')
        handle.write(f'mtllib {mtl.name}\n')
        for x, y, z in positions:
            handle.write(f'v {x:.7g} {y:.7g} {z:.7g}\n')
        for u, v in uvs:
            handle.write(f'vt {u:.7g} {v:.7g}\n')
        handle.write(f'usemtl {material_name}\n')
        for face in faces:
            handle.write('f ' + ' '.join(f'{p + 1}/{t + 1}' for p, t in face) + '\n')
    lines = [f'newmtl {material_name}', 'Ka 1 1 1', 'Kd 1 1 1', 'Ks 0 0 0', 'd 1', 'illum 2']
    if maps.get('base_color'):
        lines.append(f'map_Kd {maps["base_color"]}')
    if maps.get('roughness'):
        lines.append(f'map_Pr {maps["roughness"]}')
    if maps.get('metallic'):
        lines.append(f'map_Pm {maps["metallic"]}')
    if maps.get('normal'):
        lines.append(f'norm {maps["normal"]}')
        lines.append(f'map_Bump -bm 1 {maps["normal"]}')
    mtl.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path, mtl


def prepare(path, padding=4, resolution=0):
    """Everything texturing needs from a remeshed file, in one call.

    Returns a dict with the triangle mesh that goes to the texture model (``positions``,
    ``triangles``, ``uvs`` per output vertex, ``vertex_positions`` per output vertex) and
    what the OBJ writer needs to put the polygons back.
    """
    positions, polygons = read_polygons(path)
    triangles, owner = triangulate(polygons)
    vmapping, indices, uvs = unwrap(positions, triangles, padding=padding, resolution=resolution)
    faces, kept, split = rebuild_polygons(polygons, owner, indices, vmapping)
    sides = [len(polygon) for polygon in polygons]
    return {
        'positions': positions, 'polygons': polygons, 'triangles': triangles, 'owner': owner,
        'vmapping': vmapping, 'indices': indices, 'uvs': uvs,
        'vertex_positions': positions[vmapping], 'obj_faces': faces,
        'stats': {'polygons': len(polygons), 'quads': sum(1 for n in sides if n == 4),
                  'triangles_in': sum(1 for n in sides if n == 3),
                  'ngons': sum(1 for n in sides if n > 4),
                  'kept': kept, 'split_by_seam': split,
                  'triangles_textured': int(len(indices)), 'uv_vertices': int(len(uvs))},
    }
