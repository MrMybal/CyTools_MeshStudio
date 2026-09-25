"""Handlers of the CPU geometry operations: remesh, UV, PBR bake, inspection, editing."""
import os

from cytools_core import CyToolError

from ..engines import registry as engines
from .common import GiB, MiB, MESH_SUFFIXES, require_file


def register(runtime, services):
    def remesh_auto(context, parameters):
        source = require_file(parameters.get('input_file'), 'input_file', ('.obj',))
        engine = engines.require_native('autoremesher')
        engines.require('geometry')
        return services.run(context, 'autoremesher', 'remesh',
                            {'parameters': {**parameters, 'input_file': str(source)},
                             'engine': str(engine), 'version': '1.2.0'})

    def remesh_field(context, parameters):
        source = require_file(parameters.get('input'), 'input', ('.obj',))
        engine = engines.require_native('quadwild')
        engines.require('geometry')
        return services.run(context, 'quadwild', 'remesh',
                            {'parameters': {**parameters, 'input': str(source)},
                             'engine': str(engine.parent)},
                            timeout=max(600, int(parameters.get('solverSeconds', 200)) * 6))

    def unwrap(context, parameters):
        source = require_file(parameters.get('input'), 'input', ('.obj', '.ply', '.stl', '.glb', '.gltf', '.off'))
        engines.require('geometry')
        return services.run(context, 'xatlas', 'unwrap',
                            {'parameters': {**parameters, 'input': str(source)}})

    def repack(context, parameters):
        source = require_file(parameters.get('input'), 'input', ('.obj', '.ply', '.stl', '.glb', '.gltf', '.off'))
        engines.require('geometry')
        return services.run(context, 'xatlas', 'repack',
                            {'parameters': {**parameters, 'input': str(source)}})

    def texture_pbr(context, parameters):
        source = require_file(parameters.get('mesh_file'), 'mesh_file')
        engines.require('geometry')
        return services.run(context, 'pbrbake', 'generate_pbr',
                            {'parameters': {**parameters, 'mesh_file': str(source)}}, timeout=1800)

    def mesh_inspect(context, parameters):
        source = require_file(parameters.get('mesh_file'), 'mesh_file')
        engines.require('geometry')
        return services.run(context, 'meshedit', 'inspect',
                            {'parameters': {**parameters, 'mesh_file': str(source)}})

    def mesh_edit(context, parameters):
        source = require_file(parameters.get('mesh_file'), 'mesh_file')
        steps = parameters.get('steps') or []
        if not steps:
            raise CyToolError('InvalidParameters', 'At least one edit step is required')
        engines.require('geometry')
        return services.run(context, 'meshedit', 'edit',
                            {'parameters': {**parameters, 'mesh_file': str(source)}}, timeout=1800)

    def mesh_convert(context, parameters):
        source = require_file(parameters.get('mesh_file'), 'mesh_file')
        engines.require('geometry')
        return services.run(context, 'meshedit', 'convert',
                            {'parameters': {**parameters, 'mesh_file': str(source)}})

    def by_size(field, ram_factor, disk_factor, floor_ram=1 * GiB):
        def estimate(parameters, backend, model):
            try:
                size = os.path.getsize(parameters.get(field, ''))
            except OSError:
                size = 0
            return {'ramBytes': max(floor_ram, size * ram_factor),
                    'diskBytes': max(64 * MiB, size * disk_factor),
                    'cpuThreads': max(1, os.cpu_count() or 1)}
        return estimate

    def pbr_estimate(parameters, backend, model):
        resolution = int(parameters.get('resolution', 1024) or 1024)
        # Four float32 channels of the atlas, plus the rasterisation indices, plus the mesh.
        atlas = resolution * resolution * 4 * 4 * 3
        return {'ramBytes': max(2 * GiB, atlas), 'diskBytes': max(128 * MiB, atlas // 2),
                'cpuThreads': max(1, os.cpu_count() or 1)}

    registered = {
        'remesh_auto': (remesh_auto, by_size('input_file', 30, 8, 2 * GiB)),
        'remesh_field': (remesh_field, by_size('input', 40, 10, 2 * GiB)),
        'uv_unwrap': (unwrap, by_size('input', 30, 8)),
        'uv_repack': (repack, by_size('input', 30, 8)),
        'texture_pbr': (texture_pbr, pbr_estimate),
        'mesh_inspect': (mesh_inspect, by_size('mesh_file', 20, 2)),
        'mesh_edit': (mesh_edit, by_size('mesh_file', 40, 8)),
        'mesh_convert': (mesh_convert, by_size('mesh_file', 30, 8)),
    }
    for name, (handler, estimate) in registered.items():
        runtime.register(name, handler, estimate=estimate)
    return {name: handler for name, (handler, _estimate) in registered.items()}
