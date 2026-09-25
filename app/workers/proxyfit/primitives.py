"""Proxy primitives. Every primitive yields a small closed mesh and an analytic inside test.

Two generators cover the whole family:
  Loft      - polygon cross-sections along an axis (LoftedPolygon, Box, OrientedBox,
              TaperedBox, Cylinder, TaperedCylinder).
  Extrusion - a 2D polygon with a small thickness (ExtrudedPolygon, Prism, Wedge, Plane).
A frame is (origin, axes) with axes rows = local x, y, z expressed in object space.
"""
import math
import numpy as np

BOX_EXPONENT = 8.0
TYPES = ['Plane', 'Box', 'OrientedBox', 'TaperedBox', 'Prism', 'Wedge', 'Cylinder',
         'TaperedCylinder', 'ExtrudedPolygon', 'LoftedPolygon']


def _outward(vertices, faces):
    v = vertices[faces]
    volume = np.einsum('ij,ij->i', v[:, 0], np.cross(v[:, 1], v[:, 2])).sum()
    return faces[:, ::-1].copy() if volume < 0 else faces


def _clean(vertices, faces):
    v = vertices[faces]
    area = np.linalg.norm(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1)
    return faces[area > 1e-10]


def section_points(a, b, n, count):
    """Polygon inscribed in the superellipse |w/a|^n + |v/b|^n = 1, symmetric in w and v."""
    if n >= BOX_EXPONENT and count == 4:
        return np.array([[b, a], [b, -a], [-b, -a], [-b, a]], dtype=float)  # (v, w)
    theta = 2 * math.pi * (np.arange(count) + .5) / count
    c, s = np.cos(theta), np.sin(theta)
    e = 2.0 / min(n, 4.0 if count > 4 else n)
    return np.stack([b * np.sign(s) * np.abs(s) ** e, a * np.sign(c) * np.abs(c) ** e], -1)


def triangulate(polygon):
    """Ear clipping for a simple polygon; returns index triples."""
    pts = np.asarray(polygon, dtype=float)
    idx = list(range(len(pts)))
    area = 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in idx)
    if area < 0: idx.reverse()
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    out, guard = [], 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            if cross(pts[i0], pts[i1], pts[i2]) <= 1e-12: continue
            if any(j not in (i0, i1, i2) and cross(pts[i0], pts[i1], pts[j]) >= 0 and
                   cross(pts[i1], pts[i2], pts[j]) >= 0 and cross(pts[i2], pts[i0], pts[j]) >= 0 for j in idx):
                continue
            out.append((i0, i1, i2)); idx.pop(k); break
        else:
            idx.pop(0)  # degenerate remainder: drop a vertex rather than loop forever
    if len(idx) == 3: out.append(tuple(idx))
    return np.array(out, dtype=np.int64).reshape(-1, 3)


class Primitive:
    kind = 'Primitive'
    def __init__(self, origin, axes, name='part', role='secondary'):
        self.origin = np.asarray(origin, dtype=float)
        self.axes = np.asarray(axes, dtype=float)
        self.name, self.role, self.mirror_of, self.score = name, role, None, None
    def local(self, points):
        return (np.asarray(points, dtype=float) - self.origin) @ self.axes.T
    def world(self, local):
        return np.asarray(local, dtype=float) @ self.axes + self.origin
    def reflected_frame(self, axis):
        m = np.ones(3); m['xyz'.index(axis)] = -1
        return self.origin * m, self.axes * m
    def describe(self):
        vertices, faces = self.mesh()
        return {'name': self.name, 'type': self.kind, 'role': self.role, 'mirrorOf': self.mirror_of,
                'origin': [round(float(x), 5) for x in self.origin],
                'axes': [[round(float(x), 5) for x in row] for row in self.axes],
                'vertices': int(len(vertices)), 'triangles': int(len(faces)), 'parameters': self.parameters()}


class Loft(Primitive):
    """Sections are dicts t, cv, cw, a (half width on local z), b (half height on local y), n."""
    def __init__(self, origin, axes, sections, count=8, name='body', role='main', kind=None, tip=0.12):
        super().__init__(origin, axes, name, role)
        self.sections = sorted((dict(s) for s in sections), key=lambda s: s['t'])
        self.count, self.tip = int(count), tip
        self.kind = kind or self.classify()

    def classify(self):
        s = self.sections
        if len(s) > 2: return 'LoftedPolygon'
        same = all(abs(s[0][k] - s[1][k]) <= .06 * max(abs(s[0][k]), abs(s[1][k]), 1e-6) for k in ('a', 'b')) and \
            all(abs(s[0][k] - s[1][k]) < .03 * max(s[0]['a'], s[0]['b']) for k in ('cv', 'cw'))
        boxy = min(x['n'] for x in s) >= BOX_EXPONENT and self.count == 4
        if boxy:
            aligned = np.allclose(np.abs(self.axes).max(1), 1.0, atol=1e-3)
            return ('Box' if aligned else 'OrientedBox') if same else 'TaperedBox'
        return 'Cylinder' if same else 'TaperedCylinder'

    def parameters(self):
        return {'sectionVertices': self.count,
                'sections': [{k: round(float(v), 5) for k, v in s.items()} for s in self.sections]}

    def mesh(self):
        k, rings, vertices = self.count, [], []
        largest = max(max(s['a'], s['b']) for s in self.sections)
        for i, s in enumerate(self.sections):
            end = i in (0, len(self.sections) - 1)
            if end and max(s['a'], s['b']) < self.tip * largest:
                rings.append([len(vertices)]); vertices.append([s['t'], s['cv'], s['cw']])
                continue
            p = section_points(s['a'], s['b'], s['n'], k)
            rings.append(list(range(len(vertices), len(vertices) + k)))
            vertices += [[s['t'], s['cv'] + v, s['cw'] + w] for v, w in p]
        faces = []
        for r0, r1 in zip(rings[:-1], rings[1:]):
            for j in range(k):
                a0, a1 = r0[j % len(r0)], r0[(j + 1) % len(r0)]
                b0, b1 = r1[j % len(r1)], r1[(j + 1) % len(r1)]
                if a0 != a1: faces.append((a0, a1, b0 if len(r1) == 1 else b1))
                if b0 != b1: faces.append((a0, b1, b0))
        for ring, flip in ((rings[0], False), (rings[-1], True)):
            for j in range(1, len(ring) - 1):
                faces.append((ring[0], ring[j + 1], ring[j]) if flip else (ring[0], ring[j], ring[j + 1]))
        vertices = self.world(np.array(vertices, dtype=float))
        faces = _clean(vertices, np.array(faces, dtype=np.int64))
        return vertices, _outward(vertices, faces)

    def contains(self, points):
        p = self.local(points)
        t = np.array([s['t'] for s in self.sections])
        inside = (p[:, 0] >= t[0]) & (p[:, 0] <= t[-1])
        i = np.clip(np.searchsorted(t, p[:, 0], side='right') - 1, 0, len(t) - 2)
        f = np.clip((p[:, 0] - t[i]) / np.maximum(t[i + 1] - t[i], 1e-9), 0, 1)
        def lerp(key):
            values = np.array([s[key] for s in self.sections]); return values[i] * (1 - f) + values[i + 1] * f
        a, b, n = np.maximum(lerp('a'), 1e-9), np.maximum(lerp('b'), 1e-9), lerp('n')
        dv, dw = np.abs(p[:, 1] - lerp('cv')) / b, np.abs(p[:, 2] - lerp('cw')) / a
        boxy = n >= BOX_EXPONENT
        value = np.where(boxy, np.maximum(dv, dw), (dv ** np.minimum(n, 8) + dw ** np.minimum(n, 8)))
        return inside & (value <= 1.0)

    def mirrored(self, axis, name):
        origin, axes = self.reflected_frame(axis)
        twin = Loft(origin, axes, self.sections, self.count, name, self.role, self.kind, self.tip)
        twin.mirror_of = self.name
        return twin


class Extrusion(Primitive):
    """Polygon in the local (x, y) plane, thickness along local z centred on the origin."""
    def __init__(self, origin, axes, polygon, thickness, name='panel', role='thin', kind=None):
        super().__init__(origin, axes, name, role)
        self.polygon, self.thickness = np.asarray(polygon, dtype=float), float(thickness)
        self.kind = kind or ('Prism' if len(self.polygon) == 3 else 'ExtrudedPolygon')

    def parameters(self):
        return {'thickness': round(self.thickness, 5),
                'polygon': [[round(float(x), 5), round(float(y), 5)] for x, y in self.polygon]}

    def mesh(self):
        n, tris = len(self.polygon), triangulate(self.polygon)
        if self.kind == 'Plane':
            vertices = self.world(np.column_stack([self.polygon, np.zeros(n)]))
            return vertices, tris
        h = self.thickness / 2
        vertices = np.vstack([np.column_stack([self.polygon, np.full(n, h)]),
                              np.column_stack([self.polygon, np.full(n, -h)])])
        faces = [tuple(t) for t in tris] + [(a + n, c + n, b + n) for a, b, c in tris]
        for j in range(n):
            k = (j + 1) % n
            faces += [(j, j + n, k + n), (j, k + n, k)]
        vertices = self.world(vertices)
        faces = _clean(vertices, np.array(faces, dtype=np.int64))
        return vertices, _outward(vertices, faces)

    def contains(self, points):
        p = self.local(points)
        inside = np.abs(p[:, 2]) <= max(self.thickness / 2, 1e-9)
        x, y, poly, odd = p[:, 0], p[:, 1], self.polygon, np.zeros(len(p), bool)
        for j in range(len(poly)):
            (x0, y0), (x1, y1) = poly[j], poly[(j + 1) % len(poly)]
            cross = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / ((y1 - y0) if y1 != y0 else 1e-12) + x0)
            odd ^= cross
        return inside & odd

    def mirrored(self, axis, name):
        origin, axes = self.reflected_frame(axis)
        twin = Extrusion(origin, axes, self.polygon, self.thickness, name, self.role, self.kind)
        twin.mirror_of = self.name
        return twin


def frame(origin=(0, 0, 0), x=(1, 0, 0), y=(0, 1, 0)):
    x = np.asarray(x, float) / np.linalg.norm(x)
    y = np.asarray(y, float) - x * (np.asarray(y, float) @ x); y /= np.linalg.norm(y)
    return np.asarray(origin, float), np.stack([x, y, np.cross(x, y)])


# Explicit constructors so every advertised primitive can be built and tested directly.
def box(origin, size, axes=None, name='box'):
    o, ax = frame(origin) if axes is None else (np.asarray(origin, float), np.asarray(axes, float))
    l, h, w = np.asarray(size, float) / 2
    s = [{'t': -l, 'cv': 0, 'cw': 0, 'a': w, 'b': h, 'n': BOX_EXPONENT}, {'t': l, 'cv': 0, 'cw': 0, 'a': w, 'b': h, 'n': BOX_EXPONENT}]
    return Loft(o, ax, s, 4, name, 'secondary')

def tapered_box(origin, length, start, end, axes=None, name='tapered_box'):
    o, ax = frame(origin) if axes is None else (np.asarray(origin, float), np.asarray(axes, float))
    s = [{'t': -length / 2, 'cv': 0, 'cw': 0, 'a': start[1] / 2, 'b': start[0] / 2, 'n': BOX_EXPONENT},
         {'t': length / 2, 'cv': 0, 'cw': 0, 'a': end[1] / 2, 'b': end[0] / 2, 'n': BOX_EXPONENT}]
    return Loft(o, ax, s, 4, name, 'secondary')

def cylinder(origin, length, radius, end_radius=None, axes=None, sides=8, name='cylinder'):
    o, ax = frame(origin) if axes is None else (np.asarray(origin, float), np.asarray(axes, float))
    r1 = radius if end_radius is None else end_radius
    s = [{'t': -length / 2, 'cv': 0, 'cw': 0, 'a': radius, 'b': radius, 'n': 2.0},
         {'t': length / 2, 'cv': 0, 'cw': 0, 'a': r1, 'b': r1, 'n': 2.0}]
    return Loft(o, ax, s, sides, name, 'secondary', tip=0.0)

def extruded_polygon(origin, polygon, thickness, axes=None, name='panel'):
    o, ax = frame(origin) if axes is None else (np.asarray(origin, float), np.asarray(axes, float))
    return Extrusion(o, ax, polygon, thickness, name)

def prism(origin, triangle, thickness, axes=None, name='prism'):
    return extruded_polygon(origin, np.asarray(triangle, float)[:3], thickness, axes, name)

def wedge(origin, length, height, width, axes=None, name='wedge'):
    o, ax = frame(origin) if axes is None else (np.asarray(origin, float), np.asarray(axes, float))
    tri = [[-length / 2, -height / 2], [length / 2, -height / 2], [-length / 2, height / 2]]
    return Extrusion(o, ax, tri, width, name, 'secondary', 'Wedge')

def plane(origin, size, axes=None, name='plane'):
    o, ax = frame(origin) if axes is None else (np.asarray(origin, float), np.asarray(axes, float))
    l, w = size[0] / 2, size[1] / 2
    return Extrusion(o, ax, [[-l, -w], [l, -w], [l, w], [-l, w]], 0.0, name, 'thin', 'Plane')

def lofted_polygon(origin, sections, axes=None, count=8, name='loft'):
    o, ax = frame(origin) if axes is None else (np.asarray(origin, float), np.asarray(axes, float))
    return Loft(o, ax, sections, count, name, 'main')
