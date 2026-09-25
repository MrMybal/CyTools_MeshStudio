"""Viewpoint vocabulary, spherical pose arithmetic, coverage and the View Set format.

Conventions used everywhere in this Tool, including its JSON contracts:

* ``azimuth``   degrees in ``(-180, 180]``. ``0`` looks at the front of the object and
                positive values move the camera towards the object's right side, so
                ``+90`` is Right, ``-90`` is Left and ``180`` is Rear.
* ``elevation`` degrees in ``[-90, 90]``. Positive means the camera is above the object.
* ``roll``      degrees in ``(-180, 180]``, positive rotates the image clockwise.
* ``fov``       horizontal field of view in degrees.

No model, torch import or network access belongs in this module: it is shared by the
runtime process, the Dear ImGui interface and the inference worker.
"""
import math

VIEW_SET_FORMAT = 'cytools-view-set'
VIEW_SET_VERSION = 1

# Preset viewpoints. Top and Bottom are polar: their azimuth is not meaningful.
PRESETS = {
    'Front': (0.0, 0.0),
    'FrontRight': (45.0, 0.0),
    'Right': (90.0, 0.0),
    'RearRight': (135.0, 0.0),
    'Rear': (180.0, 0.0),
    'RearLeft': (-135.0, 0.0),
    'Left': (-90.0, 0.0),
    'FrontLeft': (-45.0, 0.0),
    'Top': (0.0, 90.0),
    'Bottom': (0.0, -90.0),
}
PRESET_NAMES = tuple(PRESETS)
EQUATORIAL = tuple(name for name in PRESETS if name not in ('Top', 'Bottom'))
POLAR_THRESHOLD = 60.0
# A view is credited to a sector when it is this close to the sector centre.
REAL_TOLERANCE = 22.5
PARTIAL_TOLERANCE = 40.0


def wrap180(value):
    """Normalise an angle to (-180, 180]."""
    value = math.fmod(float(value) + 180.0, 360.0)
    if value <= 0.0:
        value += 360.0
    return value - 180.0


def clamp_elevation(value):
    return max(-90.0, min(90.0, float(value)))


def direction(azimuth, elevation):
    """Unit vector of the camera position on the object-centred sphere."""
    a, e = math.radians(wrap180(azimuth)), math.radians(clamp_elevation(elevation))
    return (math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a))


def angular_distance(first, second):
    """Great-circle angle in degrees between two (azimuth, elevation) pairs."""
    a, b = direction(*first), direction(*second)
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    return math.degrees(math.acos(dot))


def classify(azimuth, elevation):
    """Nearest preset name and its angular error in degrees."""
    if elevation >= POLAR_THRESHOLD:
        return 'Top', angular_distance((azimuth, elevation), PRESETS['Top'])
    if elevation <= -POLAR_THRESHOLD:
        return 'Bottom', angular_distance((azimuth, elevation), PRESETS['Bottom'])
    best, error = None, 1e9
    for name in EQUATORIAL:
        value = angular_distance((azimuth, elevation), PRESETS[name])
        if value < error:
            best, error = name, value
    return best, error


def preset_pose(name):
    if name not in PRESETS:
        raise ValueError('Unknown preset view: ' + str(name))
    return PRESETS[name]


def make_view(*, azimuth, elevation, roll=0.0, fov=None, is_real, name='', image='',
              mask='', normal='', confidence=0.0, source_views=(), backend='',
              model_version='', method='', requested=None, notes=(), extra=None):
    """Build one View Set entry. ``isReal`` and ``isGenerated`` are never both true."""
    view_type, error = classify(azimuth, elevation)
    view = {
        'name': name or view_type,
        'viewType': view_type,
        'viewTypeError': round(error, 3),
        'azimuth': round(wrap180(azimuth), 3),
        'elevation': round(clamp_elevation(elevation), 3),
        'roll': round(wrap180(roll), 3),
        'fov': None if fov is None else round(float(fov), 3),
        'isReal': bool(is_real),
        'isGenerated': not bool(is_real),
        'image': str(image),
        'mask': str(mask),
        'normal': str(normal),
        'confidence': round(float(confidence), 4),
        'sourceViews': [str(x) for x in source_views],
        'generationBackend': str(backend),
        'modelVersion': str(model_version),
        'method': str(method),
        'targetAzimuth': None,
        'targetElevation': None,
        'targetRoll': None,
        'poseError': None,
        'notes': [str(x) for x in notes],
    }
    if requested is not None:
        view['targetAzimuth'] = round(wrap180(requested[0]), 3)
        view['targetElevation'] = round(clamp_elevation(requested[1]), 3)
        view['targetRoll'] = round(wrap180(requested[2] if len(requested) > 2 else 0.0), 3)
        view['poseError'] = round(angular_distance((azimuth, elevation), requested[:2]), 3)
    if extra:
        view.update(extra)
    return view


def sectors():
    """Coverage sectors: the eight equatorial presets plus Top and Bottom."""
    return [{'name': name, 'azimuth': PRESETS[name][0], 'elevation': PRESETS[name][1],
             'polar': name in ('Top', 'Bottom')} for name in PRESET_NAMES]


def coverage(views):
    """Real / Partial / Missing per sector, from the poses of the supplied views."""
    entries = []
    for sector in sectors():
        target = (sector['azimuth'], sector['elevation'])
        best_real, best_any = 1e9, 1e9
        source = ''
        for view in views:
            distance = angular_distance((view['azimuth'], view['elevation']), target)
            if distance < best_any:
                best_any = distance
            if view.get('isReal') and distance < best_real:
                best_real, source = distance, view.get('name', '')
        state = ('Real' if best_real <= REAL_TOLERANCE else
                 'Partial' if best_real <= PARTIAL_TOLERANCE else
                 'Generated' if best_any <= REAL_TOLERANCE else 'Missing')
        entries.append({'view': sector['name'], 'state': state,
                        'nearestRealDegrees': None if best_real > 1e8 else round(best_real, 2),
                        'source': source})
    real = sum(1 for x in entries if x['state'] == 'Real')
    partial = sum(1 for x in entries if x['state'] == 'Partial')
    synthetic = sum(1 for x in entries if x['state'] == 'Generated')
    total = len(entries) or 1
    return {
        'sectors': entries,
        'realViewCoveragePercent': round(100.0 * (real + 0.5 * partial) / total, 2),
        'totalCoveragePercent': round(100.0 * (real + synthetic + 0.5 * partial) / total, 2),
        'generatedSectors': synthetic,
        'realSectors': real,
        'partialSectors': partial,
        'missingImportantViews': [x['view'] for x in entries if x['state'] == 'Missing'],
        'partialViews': [x['view'] for x in entries if x['state'] == 'Partial'],
    }


def recommendations(report, include_polar=True, limit=8):
    """Sectors worth generating, most useful first: missing before partial."""
    order = {'Front': 0, 'Rear': 1, 'Left': 2, 'Right': 3, 'FrontRight': 4,
             'FrontLeft': 5, 'RearRight': 6, 'RearLeft': 7, 'Top': 8, 'Bottom': 9}
    missing = [x['view'] for x in report['sectors'] if x['state'] == 'Missing']
    partial = [x['view'] for x in report['sectors'] if x['state'] == 'Partial']
    if not include_polar:
        missing = [x for x in missing if x not in ('Top', 'Bottom')]
        partial = [x for x in partial if x not in ('Top', 'Bottom')]
    ranked = sorted(missing, key=lambda x: order.get(x, 99)) + sorted(partial, key=lambda x: order.get(x, 99))
    return ranked[:max(0, int(limit))]


def turntable(count, elevation=0.0, start=0.0):
    """``count`` equally spaced azimuths on one ring."""
    if count < 1:
        raise ValueError('A turntable needs at least one view')
    step = 360.0 / float(count)
    return [(wrap180(start + index * step), clamp_elevation(elevation)) for index in range(count)]


def rings(count, elevations, start=0.0):
    poses = []
    for elevation in elevations:
        poses.extend(turntable(count, elevation, start))
    return poses


def mirror_pose(azimuth, elevation, roll=0.0):
    """Pose obtained by mirroring a view across the object's symmetry plane."""
    return wrap180(-float(azimuth)), clamp_elevation(elevation), wrap180(-float(roll))


def dedupe_targets(targets, tolerance=1.0):
    """Drop requested poses that duplicate an earlier one."""
    unique = []
    for target in targets:
        if all(angular_distance(target[:2], kept[:2]) > tolerance for kept in unique):
            unique.append(target)
    return unique


def existing_match(views, target, tolerance=REAL_TOLERANCE, real_only=True):
    """Return the view already covering ``target``, honouring REAL > GENERATED."""
    best, distance = None, tolerance
    for view in views:
        if real_only and not view.get('isReal'):
            continue
        value = angular_distance((view['azimuth'], view['elevation']), target[:2])
        if value <= distance:
            best, distance = view, value
    return best, (None if best is None else round(distance, 3))


def view_set(tool_version, views, *, coverage_report=None, analysis=None, notes=(), extra=None):
    """The portable bundle other CyTools read; ordered, with real views announced first."""
    ordered = sorted(views, key=lambda v: (not v.get('isReal'),
                                           PRESET_NAMES.index(v['viewType'])
                                           if v['viewType'] in PRESET_NAMES else 99,
                                           v['azimuth']))
    document = {
        'format': VIEW_SET_FORMAT,
        'schemaVersion': VIEW_SET_VERSION,
        'toolId': 'cy.tools.viewgenerator',
        'toolVersion': str(tool_version),
        'conventions': {
            'azimuthZero': 'object front',
            'azimuthPositive': 'towards the object right side',
            'azimuthRange': '(-180, 180]',
            'elevationPositive': 'camera above the object',
            'elevationRange': '[-90, 90]',
            'rollPositive': 'clockwise image rotation',
            'angleUnit': 'degree',
        },
        'viewCount': len(ordered),
        'realViewCount': sum(1 for v in ordered if v.get('isReal')),
        'generatedViewCount': sum(1 for v in ordered if v.get('isGenerated')),
        'coverage': coverage_report or coverage(ordered),
        'analysis': analysis or {},
        'views': ordered,
        'notes': [str(x) for x in notes],
    }
    if extra:
        document.update(extra)
    return document
