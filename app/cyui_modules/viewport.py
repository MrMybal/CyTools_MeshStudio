from dataclasses import dataclass, field
from math import sqrt, sin, cos, exp, atan2, hypot, pi
from copy import deepcopy
from .common import Edit, ui, snap, take_wheel, wheel_taken
from .canvas import Canvas, CanvasState


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]


def _unit(a):
    length = max(1e-12, sqrt(_dot(a, a)))
    return tuple(v/length for v in a)


@dataclass
class OrbitCamera:
    target: tuple = (0., 0., 0.)
    yaw: float = 0.
    pitch: float = .25
    distance: float = 5.
    up: tuple = (0., 1., 0.)


def camera_position(camera):
    up = _unit(camera.up) if _dot(camera.up, camera.up) > 1e-10 else (0., 1., 0.)
    forward = _unit(_cross((1., 0., 0.) if abs(up[0]) < .9 else (0., 0., 1.), up))
    right, pitch = _unit(_cross(up, forward)), max(-1.56, min(1.56, camera.pitch))
    return tuple(camera.target[n]+max(1e-6, camera.distance)*(right[n]*sin(camera.yaw)*cos(pitch)+forward[n]*cos(camera.yaw)*cos(pitch)+up[n]*sin(pitch)) for n in range(3))


def camera_view_matrix(camera):
    eye = camera_position(camera)
    z = _unit(tuple(eye[n]-camera.target[n] for n in range(3)))
    x = _unit(_cross(camera.up if _dot(camera.up, camera.up) > 1e-10 else (0., 1., 0.), z))
    y = _cross(z, x)
    return [x[0], y[0], z[0], 0., x[1], y[1], z[1], 0., x[2], y[2], z[2], 0., -_dot(x, eye), -_dot(y, eye), -_dot(z, eye), 1.]


@dataclass
class ViewportState:
    camera: OrbitCamera = field(default_factory=OrbitCamera)
    orbiting: bool = False
    panning: bool = False


def viewport(identifier, state, image, size=(0, 280), navigation=True):
    i, c = ui()
    result = {'camera_changed': False, 'clicked': False, 'uv': None}
    with Canvas(identifier, CanvasState(), size, False, False) as f:
        iop = i.get_io()
        a, b = f.top, f.bottom
        if image.width > 0 and image.height > 0:
            scale = min(f.size[0]/image.width, f.size[1]/image.height)
            extent = image.width*scale, image.height*scale
            a = tuple(f.top[n]+(f.size[n]-extent[n])/2 for n in (0, 1))
            b = tuple(a[n]+extent[n] for n in (0, 1))
        if image.texture:
            texture = image.texture if isinstance(image.texture, i.ImTextureRef) else i.ImTextureRef(image.texture)
            f.draw.add_image(texture, a, b, image.uv_min, image.uv_max)
        if f.hovered and all(a[n] <= iop.mouse_pos[n] <= b[n] for n in (0, 1)):
            result['uv'] = tuple((iop.mouse_pos[n]-a[n])/(b[n]-a[n]) for n in (0, 1))
            result['clicked'] = i.is_mouse_clicked(0) and not iop.key_alt
        if navigation:
            if f.hovered and iop.key_alt and i.is_mouse_clicked(0):
                state.orbiting = True
            if f.hovered and i.is_mouse_clicked(2):
                state.panning = True
            if not i.is_mouse_down(0):
                state.orbiting = False
            if not i.is_mouse_down(2):
                state.panning = False
            if state.orbiting and (iop.mouse_delta.x or iop.mouse_delta.y):
                state.camera.yaw -= iop.mouse_delta.x*.007
                state.camera.pitch = max(-1.56, min(1.56, state.camera.pitch+iop.mouse_delta.y*.007))
                result['camera_changed'] = True
            if state.panning and (iop.mouse_delta.x or iop.mouse_delta.y):
                matrix = camera_view_matrix(state.camera)
                right, up = (matrix[0], matrix[4], matrix[8]), (matrix[1], matrix[5], matrix[9])
                factor = state.camera.distance/max(c.dp(1), f.size[1])
                state.camera.target = tuple(state.camera.target[n]+(-right[n]*iop.mouse_delta.x+up[n]*iop.mouse_delta.y)*factor for n in range(3))
                result['camera_changed'] = True
            if f.hovered and iop.mouse_wheel and not wheel_taken():
                state.camera.distance = max(1e-5, min(1e12, state.camera.distance*exp(-iop.mouse_wheel*.15)))
                result['camera_changed'] = True
                take_wheel()
    return result


@dataclass
class Transform2D:
    center: tuple = (0., 0.)
    size: tuple = (1., 1.)
    rotation: float = 0.


@dataclass
class TransformState:
    before: object = None
    preview: object = None
    grab: tuple = (0, 0)
    handle: int = 0
    revision: int = 0


def transform_gizmo(identifier, state, value, project=lambda p: p, unproject=lambda p: p, enabled=True, revision=0):
    i, c = ui()
    io, p, d = i.get_io(), c.palette(), i.get_window_draw_list()
    edit = Edit()
    if state.handle and (state.revision != revision or not enabled or i.is_key_pressed(i.Key.escape)):
        state.handle, edit = 0, Edit('cancel')
    shown = state.preview if state.handle else value
    def at(x, y):
        return project((shown.center[0]+x*cos(shown.rotation)-y*sin(shown.rotation), shown.center[1]+x*sin(shown.rotation)+y*cos(shown.rotation)))
    points = [at(x*shown.size[0]/2, y*shown.size[1]/2) for x, y in ((-1,-1),(1,-1),(1,1),(-1,1))]
    hit = 0
    center, rotate = project(shown.center), at(0, -shown.size[1]/2-c.dp(24))
    for n, point in enumerate(points):
        d.add_line(point, points[(n+1)%4], p.accent, c.dp(1.5))
        d.add_circle_filled(point, c.dp(3), p.text)
        if hypot(point[0]-io.mouse_pos.x, point[1]-io.mouse_pos.y) < c.dp(8):
            hit = n+2
    d.add_circle(center, c.dp(7), p.accent)
    d.add_circle_filled(rotate, c.dp(4), p.info)
    if hypot(center[0]-io.mouse_pos.x, center[1]-io.mouse_pos.y) < c.dp(10):
        hit = 1
    if hypot(rotate[0]-io.mouse_pos.x, rotate[1]-io.mouse_pos.y) < c.dp(8):
        hit = 6
    if enabled and i.is_window_hovered() and hit and i.is_mouse_clicked(0):
        state.before, state.preview, state.grab, state.handle, state.revision = deepcopy(value), deepcopy(value), unproject(tuple(io.mouse_pos)), hit, revision
        edit = Edit('begin', deepcopy(state.preview))
    if state.handle:
        if i.is_mouse_down(0):
            mouse = unproject(tuple(io.mouse_pos))
            state.preview = deepcopy(state.before)
            if state.handle == 1:
                state.preview.center = tuple(value.center[n]+mouse[n]-state.grab[n] for n in (0, 1))
            elif state.handle == 6:
                state.preview.rotation += atan2(mouse[1]-value.center[1], mouse[0]-value.center[0])-atan2(state.grab[1]-value.center[1], state.grab[0]-value.center[0])
                if io.key_ctrl:
                    state.preview.rotation = snap(state.preview.rotation, pi/12)
            else:
                dx, dy = mouse[0]-value.center[0], mouse[1]-value.center[1]
                state.preview.size = max(1e-6, abs(dx*cos(value.rotation)+dy*sin(value.rotation))*2), max(1e-6, abs(-dx*sin(value.rotation)+dy*cos(value.rotation))*2)
            if edit.phase != 'begin' and (io.mouse_delta.x or io.mouse_delta.y):
                edit = Edit('update', deepcopy(state.preview))
        else:
            state.handle, edit = 0, Edit('commit', deepcopy(state.preview))
    return edit
