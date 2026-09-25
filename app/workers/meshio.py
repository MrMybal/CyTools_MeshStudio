"""Strict OBJ reading and writing, shared by the geometry workers.

Ported from the ``mesh.py`` of CyTools_AutoRemesher and CyTools_QuadWild: the native
programs of those two engines only accept a geometry-only OBJ, and a malformed file makes
them fail late and unhelpfully. Validating here gives a useful error before anything is
launched. trimesh is used for the richer formats; this module stays dependency free so it
also works in the light application interpreter.
"""
import math
from pathlib import Path

MAX_BYTES = 256 * 1024 ** 2
MAX_VERTICES = 4_000_000
MAX_FACES = 4_000_000


class MeshError(ValueError):
    pass


def read_obj(path, check=lambda: None, max_bytes=MAX_BYTES):
    """Vertices and faces of a geometry-only OBJ, with every index validated."""
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise MeshError(f'OBJ larger than {max_bytes // 1024 ** 2} MiB')
    vertices, faces = [], []
    with path.open(encoding='utf-8-sig') as stream:
        for line_number, line in enumerate(stream, 1):
            if line_number % 4096 == 0:
                check()
            if len(line) > 16384:
                raise MeshError(f'Line {line_number} is too long for an OBJ')
            words = line.split('#', 1)[0].split()
            if not words:
                continue
            if words[0] == 'v':
                if len(words) < 4:
                    raise MeshError(f'Incomplete vertex on line {line_number}')
                point = tuple(float(x) for x in words[1:4])
                if not all(math.isfinite(x) and abs(x) <= 1e12 for x in point):
                    raise MeshError(f'Non finite or out of range coordinate on line {line_number}')
                vertices.append(point)
                if len(vertices) > MAX_VERTICES:
                    raise MeshError('Too many vertices')
            elif words[0] == 'f':
                if not 4 <= len(words) <= 65:
                    raise MeshError(f'Face with {len(words) - 1} corners on line {line_number} (3 to 64 expected)')
                face = []
                for token in words[1:]:
                    index = int(token.split('/')[0])
                    if index == 0:
                        raise MeshError(f'Zero index on line {line_number}')
                    index = index - 1 if index > 0 else len(vertices) + index
                    if index < 0 or index >= len(vertices):
                        raise MeshError(f'Index out of range on line {line_number}')
                    face.append(index)
                if len(set(face)) != len(face):
                    raise MeshError(f'Degenerate face on line {line_number}')
                faces.append(face)
                if len(faces) > MAX_FACES:
                    raise MeshError('Too many faces')
    if not vertices or not faces:
        raise MeshError('The OBJ carries no usable geometry')
    check()
    return vertices, faces


def write_obj(path, vertices, faces, comment='CyTools_MeshStudio - geometry only'):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='ascii') as stream:
        stream.write(f'# {comment}\n')
        for vertex in vertices:
            stream.write('v ' + ' '.join(format(x, '.12g') for x in vertex) + '\n')
        for face in faces:
            stream.write('f ' + ' '.join(str(index + 1) for index in face) + '\n')
    return path


def statistics(vertices, faces):
    quads = sum(len(face) == 4 for face in faces)
    triangles = sum(len(face) == 3 for face in faces)
    return {'vertices': len(vertices), 'faces': len(faces), 'quads': quads,
            'triangles': triangles, 'nonQuads': len(faces) - quads,
            'quadRatio': quads / len(faces) if faces else 0.0}


def statistics_of(path):
    vertices, faces = read_obj(path)
    return statistics(vertices, faces)


def normalise_obj(source, destination, check=lambda: None, require_triangles=False, max_bytes=MAX_BYTES):
    """Rewrite an OBJ without material references or external dependencies."""
    vertices, faces = read_obj(source, check, max_bytes=max_bytes)
    if require_triangles and any(len(face) != 3 for face in faces):
        raise MeshError('The input must be triangulated')
    write_obj(destination, vertices, faces)
    return vertices, faces
