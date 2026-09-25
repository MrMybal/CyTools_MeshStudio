"""The quad-keeping unwrap, on the CPU: no model, no GPU.

Run it with an engine interpreter that carries xatlas (trellis or geometry):

    runtime/engines/trellis/Scripts/python.exe app/tests/test_quadtex.py
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / 'workers'))

import quadtex  # noqa: E402

PASSED, FAILED = [], []


def check(title, condition, detail=''):
    (PASSED if condition else FAILED).append(title)
    print(f'{"ok  " if condition else "FAIL"} {title}' + (f'  [{detail}]' if detail and not condition else ''))


def quad_cube(divisions=6):
    """A closed cube made of quads only, written as an OBJ the way QuadWild writes one."""
    positions, index, polygons = [], {}, []

    def vertex(point):
        key = tuple(round(value, 6) for value in point)
        if key not in index:
            index[key] = len(positions)
            positions.append(key)
        return index[key]

    steps = np.linspace(-0.5, 0.5, divisions + 1)
    for axis in range(3):
        for sign in (-1.0, 1.0):
            u_axis, v_axis = [a for a in range(3) if a != axis]
            for i in range(divisions):
                for j in range(divisions):
                    corners = []
                    for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        point = [0.0, 0.0, 0.0]
                        point[axis] = 0.5 * sign
                        point[u_axis] = steps[i + di]
                        point[v_axis] = steps[j + dj]
                        corners.append(vertex(point))
                    if sign < 0:
                        corners.reverse()
                    polygons.append(tuple(corners))
    return np.asarray(positions), polygons


def main():
    folder = Path(tempfile.mkdtemp(prefix='quadtex-'))
    try:
        positions, polygons = quad_cube(6)
        source = folder / 'quads.obj'
        with source.open('w', encoding='utf-8') as handle:
            for x, y, z in positions:
                handle.write(f'v {x} {y} {z}\n')
            for polygon in polygons:
                handle.write('f ' + ' '.join(str(corner + 1) for corner in polygon) + '\n')

        read_positions, read_polygons = quadtex.read_polygons(source)
        check('an OBJ is read without being triangulated',
              len(read_polygons) == len(polygons) and all(len(p) == 4 for p in read_polygons),
              len(read_polygons))

        prepared = quadtex.prepare(source)
        stats = prepared['stats']
        triangles, indices, vmapping = prepared['triangles'], prepared['indices'], prepared['vmapping']
        check('two triangles per quad go to the texture model',
              len(indices) == 2 * len(polygons), len(indices))
        same_order = all(tuple(int(vmapping[k]) for k in indices[t]) == tuple(int(c) for c in triangles[t])
                         for t in range(len(triangles)))
        check('xatlas keeps the order of the triangles and says where each corner came from',
              same_order)
        uvs = prepared['uvs']
        check('every UV lies inside the atlas',
              bool(np.all(uvs >= -1e-6) and np.all(uvs <= 1 + 1e-6)))
        check('every polygon is accounted for',
              stats['kept'] + stats['split_by_seam'] == len(polygons), stats)
        check('most quads survive the unwrap', stats['kept'] >= 0.8 * len(polygons), stats)

        out = folder / 'textured.obj'
        quadtex.write_obj(out, prepared['positions'], uvs, prepared['obj_faces'],
                          maps={'base_color': 'base_color.png', 'normal': 'normal.png',
                                'roughness': 'roughness.png'})
        again_positions, again_polygons = quadtex.read_polygons(out)
        quads_written = sum(1 for polygon in again_polygons if len(polygon) == 4)
        check('the written OBJ holds the kept quads as quads',
              quads_written == stats['kept'], f'{quads_written} vs {stats["kept"]}')
        check('the written OBJ keeps the original positions',
              np.allclose(again_positions, positions))
        mtl = out.with_suffix('.mtl').read_text('utf-8')
        check('the MTL names the base colour, roughness and normal maps',
              'map_Kd base_color.png' in mtl and 'map_Pr roughness.png' in mtl
              and 'norm normal.png' in mtl, mtl)
        corners_ok = True
        with out.open('r', encoding='utf-8') as handle:
            vt_count = sum(1 for line in handle if line.startswith('vt '))
        with out.open('r', encoding='utf-8') as handle:
            for line in handle:
                if line.startswith('f '):
                    for token in line.split()[1:]:
                        v, t = (int(x) for x in token.split('/'))
                        if not (1 <= v <= len(positions) and 1 <= t <= vt_count):
                            corners_ok = False
        check('every face corner points at a real position and a real UV', corners_ok)

        # a seam across a quad diagonal must split that quad, never produce a wrong face
        faces, kept, split = quadtex.rebuild_polygons(
            [(0, 1, 2, 3)], np.asarray([0, 0]),
            np.asarray([[0, 1, 2], [3, 4, 5]]), np.asarray([0, 1, 2, 0, 2, 3]))
        check('a quad cut by a seam is written as its two triangles',
              kept == 0 and split == 1 and len(faces) == 2 and all(len(f) == 3 for f in faces),
              (faces, kept, split))
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    print(json.dumps({'passed': len(PASSED), 'failed': len(FAILED)}))
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
