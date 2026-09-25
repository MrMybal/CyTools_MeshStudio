"""Continuous view poses, human labels and projection."""
import math
import numpy as np

LABELS = {'Front': (0, 0), 'FrontRight': (45, 0), 'Right': (90, 0), 'RearRight': (135, 0),
          'Back': (180, 0), 'RearLeft': (225, 0), 'Left': (270, 0), 'FrontLeft': (315, 0),
          'Top': (0, 90), 'Bottom': (0, -90)}
ALIASES = {'rear': 'Back', 'back': 'Back', 'side': 'Right', 'threequarter': 'FrontRight',
           'backleft': 'RearLeft', 'backright': 'RearRight'}
COVERAGE_ORDER = ['Front', 'FrontRight', 'Right', 'RearRight', 'Back', 'RearLeft', 'Left',
                  'FrontLeft', 'Top', 'Bottom']


def canonical_label(text):
    key = ''.join(c for c in str(text).lower() if c.isalpha())
    for name in LABELS:
        if name.lower() == key:
            return name
    return ALIASES.get(key)


def wrap(angle):
    return (float(angle) + 180.0) % 360.0 - 180.0


def label_for(azimuth, elevation):
    if elevation >= 60: return 'Top'
    if elevation <= -60: return 'Bottom'
    names = COVERAGE_ORDER[:8]
    return names[int(round((azimuth % 360.0) / 45.0)) % 8]


def direction(azimuth, elevation):
    """Unit vector from the object centre towards the camera."""
    a, e = math.radians(azimuth), math.radians(elevation)
    return np.array([math.cos(e) * math.cos(a), math.sin(e), math.cos(e) * math.sin(a)])


def angular_distance(az1, el1, az2, el2):
    return math.degrees(math.acos(float(np.clip(direction(az1, el1) @ direction(az2, el2), -1, 1))))


class Camera:
    """Pinhole (fov > 0) or orthographic (fov == 0) camera looking at `target`.

    `size` is the square working canvas in pixels. `scale` is pixels per world unit at
    the target depth, so perspective and orthographic views share one size parameter.
    """
    def __init__(self, azimuth=0.0, elevation=0.0, roll=0.0, fov=35.0, scale=100.0,
                 size=384, center=None, target=None):
        self.azimuth, self.elevation, self.roll, self.fov = float(azimuth), float(elevation), float(roll), float(fov)
        self.scale, self.size = float(scale), int(size)
        self.center = np.array(center if center is not None else (size / 2.0, size / 2.0), dtype=float)
        self.target = np.zeros(3) if target is None else np.array(target, dtype=float)

    def copy(self, **changes):
        cam = Camera(self.azimuth, self.elevation, self.roll, self.fov, self.scale, self.size,
                     self.center.copy(), self.target.copy())
        for key, value in changes.items():
            setattr(cam, key, value)
        return cam

    @property
    def focal(self):
        return (self.size / 2.0) / math.tan(math.radians(max(self.fov, 1e-3)) / 2.0)

    @property
    def distance(self):
        return self.focal / self.scale if self.fov > 0 else 1e3

    def basis(self):
        a = math.radians(self.azimuth)
        forward = -direction(self.azimuth, self.elevation)
        right = np.array([math.sin(a), 0.0, -math.cos(a)])
        up = np.cross(right, forward)
        r = math.radians(self.roll)
        return (math.cos(r) * right + math.sin(r) * up, math.cos(r) * up - math.sin(r) * right, forward)

    @property
    def position(self):
        return self.target + direction(self.azimuth, self.elevation) * self.distance

    def project(self, points):
        """Return (uv, depth). Depth is the distance along the optical axis."""
        right, up, forward = self.basis()
        rel = np.asarray(points, dtype=float) - self.position
        z = rel @ forward
        if self.fov > 0:
            safe = np.where(z > 1e-6, z, 1e-6)
            u = self.center[0] + self.focal * (rel @ right) / safe
            v = self.center[1] - self.focal * (rel @ up) / safe
        else:
            u = self.center[0] + self.scale * (rel @ right)
            v = self.center[1] - self.scale * (rel @ up)
        return np.stack([u, v], -1), z

    def rays(self, uv):
        """Origins and unit directions of the viewing rays through pixels `uv`."""
        right, up, forward = self.basis()
        uv = np.asarray(uv, dtype=float)
        x, y = uv[..., 0] - self.center[0], self.center[1] - uv[..., 1]
        if self.fov > 0:
            d = forward + np.multiply.outer(x / self.focal, right) + np.multiply.outer(y / self.focal, up)
            d /= np.linalg.norm(d, axis=-1, keepdims=True)
            return np.broadcast_to(self.position, d.shape).copy(), d
        origin = self.position + np.multiply.outer(x / self.scale, right) + np.multiply.outer(y / self.scale, up)
        return origin, np.broadcast_to(forward, origin.shape).copy()

    def mirrored(self, axis):
        """Camera observing the mirror image of the object (image flipped horizontally)."""
        if axis == 'z': az, el = -self.azimuth, self.elevation
        elif axis == 'x': az, el = 180.0 - self.azimuth, self.elevation
        else: az, el = self.azimuth, -self.elevation
        target = self.target.copy(); target['xyz'.index(axis)] *= -1
        center = np.array([self.size - self.center[0], self.center[1]]) if axis != 'y' else \
            np.array([self.center[0], self.size - self.center[1]])
        return Camera(wrap(az), el, -self.roll, self.fov, self.scale, self.size, center, target)

    def to_json(self):
        return {'azimuth': round(wrap(self.azimuth) % 360, 3), 'elevation': round(self.elevation, 3),
                'roll': round(self.roll, 3), 'fov': round(self.fov, 3), 'scale': round(self.scale, 4),
                'center': [round(float(c), 3) for c in self.center],
                'target': [round(float(c), 5) for c in self.target], 'size': self.size,
                'projection': 'perspective' if self.fov > 0 else 'orthographic'}
