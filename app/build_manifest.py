"""Generate app/CyTool.json — the contract shared by the ImGui interface, CLI, JSONL, HTTP and MCP.

    python app/build_manifest.py            # writes CyTool.json
    python app/build_manifest.py --check    # exits 1 when CyTool.json is stale

Operations that come from an absorbed Tool reuse that Tool's schemas verbatim, read from
``app/legacy-manifests/<Tool>.json`` (its ``CyTool.json``, copied from the archive in
``runtime/legacy-apps``): a client that drove CyTools_TripoSR or CyTools_ViewGenerator keeps
every parameter it used. Only the operation id, its name and
its description change, plus the backend list. New operations are written here.

Never edit CyTool.json by hand. Platform ``tested`` records come from app/platform-tested.json
and are only written there after real executions on this machine.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parent
ROOT = APP.parent
#: The manifests of the eleven absorbed Tools, copied from runtime/legacy-apps so that the
#: manifest can be rebuilt from a clone (the archive itself is not versioned).
LEGACY = APP / 'legacy-manifests'
OUT = APP / 'CyTool.json'
TESTED = APP / 'platform-tested.json'

TOOL_ID = 'cy.tool.meshstudio'
TOOL_NAME = 'CyTools_MeshStudio'
VERSION = '0.1.0'
GiB = 1024 ** 3
MiB = 1024 ** 2


# ----------------------------------------------------------------------- schema helpers

def STRING(description, default=None, enum=None, multiline=False, advanced=False, **extra):
    spec = {'type': 'string', 'description': description}
    if enum:
        spec['enum'] = list(enum)
        spec['x-cy-kind'] = 'Enum'
    else:
        spec['x-cy-kind'] = 'MultilineString' if multiline else 'String'
    if default is not None:
        spec['default'] = default
    if advanced:
        spec['x-cy-ui'] = {'advanced': True}
    spec.update(extra)
    return spec


def FILE(description, kind='File', **extra):
    spec = {'type': 'string', 'description': description, 'x-cy-kind': kind, 'maxLength': 1024}
    spec.update(extra)
    return spec


def FILES(description, kind='Files', max_items=64):
    return {'type': 'array', 'description': description, 'items': {'type': 'string', 'maxLength': 1024},
            'maxItems': max_items, 'x-cy-kind': kind}


def NUMBER(description, default, minimum=None, maximum=None, advanced=False, **extra):
    spec = {'type': 'number', 'description': description, 'default': default, 'x-cy-kind': 'Float'}
    if minimum is not None:
        spec['minimum'] = minimum
    if maximum is not None:
        spec['maximum'] = maximum
    if advanced:
        spec['x-cy-ui'] = {'advanced': True}
    spec.update(extra)
    return spec


def INTEGER(description, default, minimum=None, maximum=None, advanced=False, **extra):
    spec = {'type': 'integer', 'description': description, 'default': default, 'x-cy-kind': 'Integer'}
    if minimum is not None:
        spec['minimum'] = minimum
    if maximum is not None:
        spec['maximum'] = maximum
    if advanced:
        spec['x-cy-ui'] = {'advanced': True}
    spec.update(extra)
    return spec


def BOOLEAN(description, default, advanced=False):
    spec = {'type': 'boolean', 'description': description, 'default': default, 'x-cy-kind': 'Boolean'}
    if advanced:
        spec['x-cy-ui'] = {'advanced': True}
    return spec


def OBJECT(properties, required=(), additional=False):
    return {'type': 'object', 'properties': properties, 'required': list(required),
            'additionalProperties': additional}


def operation(op_id, name, description, inputs, outputs, *, backends=(), resources=None,
              progress=True, category='', tags=(), permissions=()):
    return {
        'id': op_id,
        'name': name,
        'description': description,
        'inputSchema': inputs,
        'outputSchema': outputs,
        'resourceRequirements': resources or {'ramBytes': 512 * MiB},
        'supportedBackends': list(backends),
        'permissions': list(permissions),
        'canRunAsync': True,
        'canCancel': True,
        'supportsProgress': progress,
        'x-cy-category': category,
        'x-cy-tags': list(tags),
    }


# ------------------------------------------------------------------- ported operations

def legacy_manifest(tool):
    path = LEGACY / f'{tool}.json'
    if not path.is_file():
        raise SystemExit(f'Missing legacy manifest: {path}.')
    return json.loads(path.read_text('utf-8-sig'))


def legacy_operation(tool, op_id):
    for item in legacy_manifest(tool)['operations']:
        if item['id'] == op_id:
            return copy.deepcopy(item)
    raise SystemExit(f'Operation "{op_id}" not found in {tool}')


# new id, legacy tool, legacy op, name, description, backends, resources, category
PORTED = [
    ('remesh_auto', 'CyTools_AutoRemesher', 'remesh', 'Quad remesh (AutoRemesher)',
     'Rebuild the topology as a quad dominant mesh with the official AutoRemesher program. '
     'Geometry only: UV sets and materials of the input are not carried over, and the quad target is approximate.',
     ['autoremesher'], {'ramBytes': 4 * GiB, 'diskBytes': 512 * MiB, 'cpuThreads': 4}, 'Topology'),

    ('remesh_field', 'CyTools_QuadWild', 'remesh', 'Quad remesh (QuadWild Bi-MDF)',
     'Field aligned quadrangulation of a triangulated mesh with the official QuadWild Bi-MDF binaries. '
     'Slower than AutoRemesher and bounded by a solver time limit, but follows the curvature field.',
     ['quadwild'], {'ramBytes': 6 * GiB, 'diskBytes': 512 * MiB, 'cpuThreads': 4}, 'Topology'),

    ('uv_unwrap', 'CyTools_Xatlas', 'unwrap', 'UV unwrap (xatlas)',
     'Generate UV charts and pack them into a single atlas with xatlas.',
     ['xatlas'], {'ramBytes': 2 * GiB, 'diskBytes': 256 * MiB}, 'UV'),

    ('uv_repack', 'CyTools_Xatlas', 'repack', 'UV repack (xatlas)',
     'Repack the UV charts the mesh already carries, without recomputing the parametrisation.',
     ['xatlas'], {'ramBytes': 2 * GiB, 'diskBytes': 256 * MiB}, 'UV'),

    ('texture_pbr', 'CyTools_Trellis2Texture', 'generate_pbr', 'Bake PBR channels',
     'Bake Base Color, Metallic, Roughness and Alpha into a UV atlas, plus the glTF packed '
     'metallic-roughness map. Colour carried by the mesh is baked; channels the mesh does not carry are '
     'derived with documented deterministic heuristics, not generated by a model.',
     ['pbrbake'], {'ramBytes': 6 * GiB, 'diskBytes': 1 * GiB}, 'Texturing'),

    ('mesh_inspect', 'CyTools_Trellis2Texture', 'inspect_mesh', 'Inspect a mesh',
     'Report geometry, UV, colour source, materials and transparency of a mesh, plus the settings '
     'recommended before baking.',
     ['meshedit'], {'ramBytes': 2 * GiB}, 'Inspection'),

    ('image_to_mesh_triposr', 'CyTools_TripoSR', 'image_to_mesh', 'Image to mesh (TripoSR)',
     'Reconstruct one object from a single image in seconds: feed-forward NeRF then marching cubes, '
     'vertex colours or a baked texture atlas. Fast prototyping, not a measurement of the real object.',
     ['triposr'], {'ramBytes': 8 * GiB, 'vramBytes': {'auto': 6 * GiB}, 'diskBytes': 1 * GiB}, 'Reconstruction'),

    ('image_to_mesh_spar3d', 'CyTools_SPAR3D', 'image_to_mesh', 'Image to mesh (SPAR3D)',
     'Reconstruct one object as a textured mesh with its point cloud. The backside is inferred by the '
     'model, not measured.',
     ['spar3d'], {'ramBytes': 12 * GiB, 'vramBytes': {'auto': 8 * GiB}, 'diskBytes': 2 * GiB}, 'Reconstruction'),

    ('photos_to_mesh', 'CyTools_LocalMesh', 'generate', 'Image or photos to a textured mesh (LocalMesh)',
     'LocalMesh: one image, or four photographs of the same subject, to a textured GLB. The TRELLIS.2 '
     'model generates the shape; the mesh is then cleaned, remeshed and decimated, and its PBR texture '
     'is generated for that final mesh, with a baked normal map. Local CUDA inference.',
     ['trellis'], {'ramBytes': 16 * GiB, 'vramBytes': {'auto': 10 * GiB}, 'diskBytes': 4 * GiB}, 'Reconstruction'),

    ('construct_proxy', 'CyTools_MeshConstruct', 'construct_mesh', 'Construct a proxy mesh from pictures',
     'Build a simple, clean, mostly hard-surface proxy mesh (lofted cross-sections, extruded polygons, '
     'boxes, cylinders) from one or several pictures of the same object, and project the pictures on it. '
     'AI models only supply masks, relative depth, camera poses and optional synthetic views.',
     ['proxyfit'], {'ramBytes': 12 * GiB, 'vramBytes': {'auto': 6 * GiB}, 'diskBytes': 2 * GiB}, 'Reconstruction'),

    ('analyze_views', 'CyTools_MeshConstruct', 'analyze_views', 'Analyse a set of pictures',
     'Pre-flight for a reconstruction: segmentation, view poses, same-object check, coverage map and the '
     'list of viewpoints that are missing.',
     ['proxyfit'], {'ramBytes': 8 * GiB, 'vramBytes': {'auto': 4 * GiB}}, 'Views'),

    ('views_generate', 'CyTools_ViewGenerator', 'generate_views', 'Generate new views',
     'Generate the requested viewpoints of the object locally. Real photographs are reused when they '
     'already cover a requested angle.',
     ['zero123plus', 'mirror'],
     {'ramBytes': 12 * GiB, 'vramBytes': {'auto': 8 * GiB}, 'diskBytes': 1 * GiB}, 'Views'),
    # Wonder3D and SyncDreamer are deliberately not listed here: they answer the payload of
    # CyTools_MeshConstruct's runners, not the View Set contract of this operation. They are
    # reached through construct_proxy, which is where the absorbed Tool used them.

    ('views_auto_complete', 'CyTools_ViewGenerator', 'auto_complete_view_set', 'Complete a view set',
     'Analyse the supplied images, decide which important viewpoints are missing and generate only those.',
     ['zero123plus', 'mirror'], {'ramBytes': 12 * GiB, 'vramBytes': {'auto': 8 * GiB}}, 'Views'),

    ('views_turntable', 'CyTools_ViewGenerator', 'turntable_views', 'Turntable views',
     'Produce N equally spaced views around the object, on one ring or on several rings at different elevations.',
     ['zero123plus'], {'ramBytes': 12 * GiB, 'vramBytes': {'auto': 8 * GiB}}, 'Views'),

    ('views_mirror', 'CyTools_ViewGenerator', 'mirror_view', 'Mirror a view',
     'Produce the opposite view by mirroring one real image. A geometric flip, not a generation: it is '
     'only valid for a symmetric object.',
     ['mirror'], {'ramBytes': 2 * GiB}, 'Views'),

    ('views_validate', 'CyTools_ViewGenerator', 'validate_views', 'Score candidate views',
     'Score candidate views against the real photographs of the same object: identity, features, colour '
     'and materials.',
     ['zero123plus'], {'ramBytes': 8 * GiB, 'vramBytes': {'auto': 4 * GiB}}, 'Views'),

    ('segment_object', 'CyTools_ViewGenerator', 'segment_object', 'Segment the object',
     'Isolate the object in every supplied image and return its mask, an RGBA cut-out and its bounding box.',
     ['sam2'], {'ramBytes': 8 * GiB, 'vramBytes': {'auto': 4 * GiB}}, 'Views'),

    ('mesh_to_rig', 'CyTools_UniRig', 'mesh_to_rig', 'Rig a mesh (UniRig)',
     'Predict a skeleton and skinning weights for a mesh with UniRig Articulation-XL.',
     ['unirig'], {'ramBytes': 16 * GiB, 'vramBytes': {'auto': 8 * GiB}, 'diskBytes': 2 * GiB}, 'Rigging'),

    ('video_to_motion', 'CyTools_WHAM', 'reconstruct', 'Video to 3D human motion (WHAM)',
     'Reconstruct SMPL poses, translations and time stamps of the people in a monocular video.',
     ['wham'], {'ramBytes': 12 * GiB, 'vramBytes': {'auto': 8 * GiB}, 'diskBytes': 4 * GiB}, 'Motion'),

    ('video_inspect', 'CyTools_WHAM', 'inspect_video', 'Inspect a video',
     'Decode every frame and report a JPEG preview and the metadata of the file.',
     ['wham'], {'ramBytes': 4 * GiB, 'diskBytes': 2 * GiB}, 'Motion'),
]


# Fields this Tool adds on top of what the absorbed Tool declared. Anything here is optional:
# a client that drove the old Tool keeps working without knowing about it.
ADDITIONS = {
    'photos_to_mesh': {
        # The absorbed Tool offered three tiers; the engine has a fourth, the only one that adds
        # geometric detail beyond High (a 1536 grid instead of 1024). It was never exposed.
        'tier': {
            'type': 'string', 'title': 'Quality', 'default': 'standard',
            'enum': ['draft', 'standard', 'high', 'max'],
            'description': 'draft: 512 grid, 80 000 faces, 2K atlas, to judge the shape. '
                           'standard: 1024 grid, 150 000 faces, 4K atlas. '
                           'high: 1024 grid, 16 passes, 250 000 faces, 4K atlas. '
                           'max: 1536 grid, 400 000 faces, 8K atlas; needs a 24 GB card, and with '
                           'four photos it uses the older view mixer because the four-view models '
                           'stop at 1024.',
        },
        'subject_set': STRING(
            'Folder produced by prepare_subject. Its cut-outs are used as the views, so the '
            'subject is segmented once for the whole workflow instead of once per backend.',
            default='', **{'x-cy-kind': 'Directory'}),
    },
    'image_to_mesh_triposr': {
        'subject_set': STRING('Folder produced by prepare_subject; its front cut-out replaces '
                              'the image and switches the internal background removal off.',
                              default='', **{'x-cy-kind': 'Directory'}),
    },
    'image_to_mesh_spar3d': {
        'subject_set': STRING('Folder produced by prepare_subject; its front cut-out replaces '
                              'the image and switches the internal background removal off.',
                              default='', **{'x-cy-kind': 'Directory'}),
    },
}


#: The picture a subject set replaces, per operation that accepts one.
SUBJECT_REPLACES = {'photos_to_mesh': 'front', 'image_to_mesh_triposr': 'image_file',
                    'image_to_mesh_spar3d': 'image_file'}

#: Output fields this Tool adds; the runtime rejects an output its schema does not declare.
OUTPUT_ADDITIONS = {
    'photos_to_mesh': {
        'grid_resolution': {'type': 'integer', 'description': 'Grid the shape was really sampled '
                            'on. The 1536 cascade lowers it by steps of 128 when the object has more '
                            'tokens than the card allows.'},
        'token_cap': {'type': 'integer', 'description': 'Token ceiling applied, taken on the memory '
                      'available at the start of the job.'},
    },
}


def ported_operations():
    result = []
    for op_id, tool, legacy_id, name, description, backends, resources, category in PORTED:
        legacy = legacy_operation(tool, legacy_id)
        item = operation(op_id, name, description, legacy['inputSchema'], legacy['outputSchema'],
                         backends=backends, resources=resources,
                         progress=legacy.get('supportsProgress', True), category=category,
                         tags=('ported',), permissions=legacy.get('permissions', []))
        # The absorbed Tools each carried the SDK's model library (model_profile / loras). That
        # mechanism is driven by app/model-capabilities.json, which this Tool does not ship:
        # weights are managed by the catalogue and app/models/install.json instead. Leaving the
        # fields in would advertise a setting no handler reads.
        for dead in ('model_profile', 'loras'):
            item['inputSchema'].get('properties', {}).pop(dead, None)
        for field, schema in ADDITIONS.get(op_id, {}).items():
            item['inputSchema']['properties'][field] = schema
        for field, schema in OUTPUT_ADDITIONS.get(op_id, {}).items():
            item['outputSchema'].setdefault('properties', {})[field] = schema
        # A prepared subject set replaces the picture, so the picture can no longer be required:
        # the absorbed schemas made it mandatory and non-empty, which refused a job given only a
        # subject set. The handler still refuses a job given neither.
        replaced = SUBJECT_REPLACES.get(op_id)
        if replaced:
            schema = item['inputSchema']
            schema['required'] = [name for name in schema.get('required', []) if name != replaced]
            field = schema['properties'][replaced]
            field.pop('minLength', None)
            field['description'] = (field.get('description', '') +
                                    ' Optional when subject_set is given.').strip()
            # The side views of the four-view mode come from the subject set too: the rule that
            # demands them applies only when no subject set is given.
            for rule in schema.get('allOf', []):
                if set(rule.get('then', {}).get('required', [])) & {'right', 'left', 'back'}:
                    rule['if'].setdefault('properties', {})['subject_set'] = {'maxLength': 0}
        item['x-cy-origin'] = {'tool': tool, 'operation': legacy_id,
                               'note': 'Schemas reused verbatim from the absorbed Tool'
                                       + (', plus the optional fields listed in ADDITIONS.'
                                          if op_id in ADDITIONS else '.')}
        result.append(item)
    return result


# ---------------------------------------------------------------------- new operations

EDIT_ACTIONS = ['center', 'recenter_base', 'scale', 'scale_to_size', 'rotate', 'translate',
                'flip_axis', 'swap_up_axis', 'decimate', 'subdivide', 'smooth', 'weld_vertices',
                'remove_floaters', 'fill_holes', 'fix_normals', 'triangulate', 'split_components',
                'merge_components', 'keep_largest', 'strip_materials', 'strip_uv']

MESH_STATS = {
    'vertices': {'type': 'integer'}, 'faces': {'type': 'integer'},
    'components': {'type': 'integer'}, 'bounds': {'type': 'array', 'items': {'type': 'number'}},
    'extents': {'type': 'array', 'items': {'type': 'number'}},
    'isWatertight': {'type': 'boolean'}, 'hasUv': {'type': 'boolean'},
    'hasVertexColors': {'type': 'boolean'}, 'materialCount': {'type': 'integer'},
}


def new_operations():
    edit_step = {
        'type': 'object',
        'description': 'One edit applied to the mesh, in order.',
        'properties': {
            'action': STRING('Edit to apply.', enum=EDIT_ACTIONS),
            'value': NUMBER('Main value: factor for scale, angle in degrees for rotate, '
                            'target ratio for decimate, distance for weld.', 1.0),
            'axis': STRING('Axis the edit applies to.', default='y', enum=['x', 'y', 'z', 'all']),
            'vector': {'type': 'array', 'description': 'Three numbers for translate, scale or rotate per axis.',
                       'items': {'type': 'number'}, 'minItems': 3, 'maxItems': 3},
            'targetFaces': INTEGER('Absolute face count for decimate; 0 uses "value" as a ratio.', 0, minimum=0),
            'iterations': INTEGER('Iterations for smooth and subdivide.', 1, minimum=1, maximum=10),
            'threshold': NUMBER('Size threshold: minimum component size for remove_floaters, '
                                'maximum hole perimeter for fill_holes.', 0.0, minimum=0.0),
        },
        'required': ['action'],
        'additionalProperties': False,
    }
    yield operation(
        'mesh_edit', 'Edit a mesh',
        'Apply a chain of geometric edits to a mesh and write the result: transforms, decimation, '
        'cleaning, hole filling, components and material stripping. Every step is deterministic and the '
        'input file is never modified.',
        OBJECT({
            'mesh_file': FILE('Mesh to edit (GLB, glTF, OBJ, PLY, STL, OFF).'),
            'steps': {'type': 'array', 'description': 'Edits applied in order.', 'items': edit_step,
                      'minItems': 1, 'maxItems': 32, 'x-cy-kind': 'Array'},
            'output_format': STRING('Format of the written mesh.', default='glb',
                                    enum=['glb', 'gltf', 'obj', 'ply', 'stl']),
            'keep_materials': BOOLEAN('Carry materials and textures over to the result when the format allows it.', True),
            'report': BOOLEAN('Write a JSON report with the state before and after every step.', True),
        }, required=['mesh_file', 'steps']),
        OBJECT({
            'mesh_file': FILE('Edited mesh.'),
            'report_file': FILE('Report, when requested.', kind='File'),
            'preview_file': FILE('Preview of the result for the 3D view.'),
            'before': OBJECT(MESH_STATS),
            'after': OBJECT(MESH_STATS),
            'appliedSteps': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'warnings': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['mesh_file', 'before', 'after', 'appliedSteps']),
        backends=['meshedit'], resources={'ramBytes': 4 * GiB, 'diskBytes': 1 * GiB}, category='Editing')

    yield operation(
        'mesh_convert', 'Convert a mesh',
        'Convert a mesh between the supported formats, optionally triangulating it and embedding or '
        'extracting its textures.',
        OBJECT({
            'mesh_file': FILE('Mesh to convert.'),
            'output_format': STRING('Target format.', default='glb', enum=['glb', 'gltf', 'obj', 'ply', 'stl', 'off']),
            'triangulate': BOOLEAN('Triangulate faces during the conversion.', False),
            'embed_textures': BOOLEAN('Embed the textures in the file when the format allows it.', True),
            'scale': NUMBER('Uniform scale applied during the conversion.', 1.0, minimum=0.000001),
        }, required=['mesh_file']),
        OBJECT({
            'mesh_file': FILE('Converted mesh.'),
            'textures': FILES('Textures written next to the mesh.', kind='Files'),
            'vertices': {'type': 'integer'}, 'faces': {'type': 'integer'},
            'warnings': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['mesh_file']),
        backends=['meshedit'], resources={'ramBytes': 4 * GiB, 'diskBytes': 1 * GiB}, category='Editing')

    yield operation(
        'prepare_subject', 'Prepare the subject (shared front end)',
        'Cut the subject out of every view once, at a common scale, and measure where each '
        'photograph was taken from. The result is a subject set that every reconstruction '
        'backend can consume, instead of each one carrying its own background remover and its '
        'own camera estimate.',
        OBJECT({
            'front': FILE('Reference view of the subject. Optional when images are given.', kind='Image'),
            'right': FILE('Right side view.', kind='Image'),
            'left': FILE('Left side view.', kind='Image'),
            'back': FILE('Back view.', kind='Image'),
            'images': FILES('Views of the same subject. Without a front view, the role of each is read '
                            'from its file name (front, right, left, back, or face, droite, gauche, dos); '
                            'the first one without a role becomes the front.', kind='Files', max_items=16),
            'common_framing': BOOLEAN(
                'Cut every view at one common scale. Required by a multi-view fusion: framing each '
                'view on its own scales an elongated object differently per view.', True),
            'measure_camera': BOOLEAN(
                'Measure the azimuth of each view instead of assuming a regular turntable.', True),
            'contact_sheet': BOOLEAN('Write a contact sheet of the prepared views.', True),
            'gpu': INTEGER('GPU index.', 0, minimum=0, maximum=15, advanced=True),
        }),
        OBJECT({
            'subject_set': STRING('Folder holding the prepared views and their description.',
                                  **{'x-cy-kind': 'Directory'}),
            'subject_file': FILE('The subject description (JSON).'),
            'views': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'contact_sheet': FILE('Contact sheet of the prepared views.', kind='Image'),
            'camera': OBJECT({}, additional=True),
            'viewCount': {'type': 'integer'},
            'commonFraming': {'type': 'boolean'},
            'notes': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['subject_set', 'subject_file', 'views', 'viewCount']),
        backends=['birefnet', 'sam2'],
        resources={'ramBytes': 6 * GiB, 'vramBytes': {'auto': 4 * GiB}, 'diskBytes': 512 * MiB},
        category='Views')

    yield operation(
        'complete_subject', 'Complete the subject with generated views (Wonder3D)',
        'From one picture, generate the right, left and back views with Wonder3D around the '
        'vertical axis of the picture, then cut the four views out at one common scale: a subject '
        'set for the four-view path of LocalMesh. Only for a level front view: with a three-quarter '
        'or top view the generated views are tilted and the fusion deforms the object. The '
        'generated views are marked as such, and LocalMesh measures their angles itself.',
        OBJECT({
            'image': FILE('Reference picture of the subject (the front).', kind='Image'),
            'subject_set': STRING('Folder produced by prepare_subject; its front cut-out is used.',
                                  default='', **{'x-cy-kind': 'Directory'}),
            'seed': INTEGER('Wonder3D random seed.', 42, minimum=0, maximum=2 ** 31 - 1),
            'steps': INTEGER('Diffusion steps of Wonder3D.', 50, minimum=10, maximum=100, advanced=True),
            'guidance': NUMBER('Guidance scale of Wonder3D.', 3.0, minimum=1.0, maximum=10.0, advanced=True),
            'gpu': INTEGER('GPU index.', 0, minimum=0, maximum=7, advanced=True),
        }),
        OBJECT({
            'subject_set': FILE('The four cut-outs and subject.json.', kind='Directory'),
            'subject_file': FILE('subject.json.', kind='File'),
            'contact_sheet': FILE('The four views side by side.', kind='Image'),
            'views': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'viewCount': {'type': 'integer'},
            'generated': {'type': 'array', 'items': {'type': 'string'}},
            'generator': {'type': 'string'},
            'wonder3d_folder': FILE('The six raw Wonder3D views and their normal maps.', kind='Directory'),
            'notes': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['subject_set', 'subject_file', 'views']),
        backends=['wonder3d'],
        resources={'ramBytes': 12 * GiB, 'vramBytes': {'auto': 10 * GiB}, 'diskBytes': 1 * GiB},
        category='Views')

    yield operation(
        'image_to_mesh_hi3dgen', 'Image to mesh (Hi3DGen)',
        'Hi3DGen (Stable-X): the picture becomes a sharp normal map (StableNormal YOSO), and a TRELLIS '
        'v1 retrained on normal maps turns that normal map into a mesh. Geometry only, on a 256 grid, '
        'in the same frame as the LocalMesh output: texture it with "Texture a mesh for its own '
        'topology", or regenerate its detail on the 1536 grid first with "Refine a mesh". A picture '
        'without transparency is cut out first with the shared front end.',
        OBJECT({
            'image': FILE('Picture of the subject. With an alpha channel it is used as it is; '
                          'otherwise it is cut out with BiRefNet first.', kind='Image'),
            'subject_set': STRING('Folder produced by prepare_subject or complete_subject: its '
                                  'front cut-out is used.', default='', **{'x-cy-kind': 'Directory'}),
            'seed': INTEGER('Seed (-1 draws one).', -1, minimum=-1, maximum=2 ** 31 - 1,
                            **{'x-cy-kind': 'Seed'}),
            'normal_resolution': INTEGER('Resolution of the normal map estimation.', 768,
                                         enum=[512, 768, 1024], title='Normal map resolution'),
            'ss_steps': INTEGER('Sampling steps of the sparse structure.', 50, minimum=10,
                                maximum=100, advanced=True, title='Structure steps'),
            'ss_guidance': NUMBER('Guidance of the sparse structure.', 3.0, minimum=0.0,
                                  maximum=10.0, advanced=True, title='Structure guidance'),
            'slat_steps': INTEGER('Sampling steps of the structured latent.', 6, minimum=2,
                                  maximum=50, advanced=True, title='Detail steps'),
            'slat_guidance': NUMBER('Guidance of the structured latent.', 3.0, minimum=0.0,
                                    maximum=10.0, advanced=True, title='Detail guidance'),
            'origin_at_base': BOOLEAN('Put the base of the object on the ground plane.', True),
            'gpu': INTEGER('GPU index.', 0, minimum=0, maximum=7, advanced=True),
        }),
        OBJECT({
            'file': FILE('The mesh (GLB, geometry only).', kind='File'),
            'normal_file': FILE('The normal map the geometry was generated from.', kind='Image'),
            'prepared_file': FILE('The cut-out, cropped and padded as the model saw it.', kind='Image'),
            'subject_set': FILE('The subject set used, when one was prepared.', kind='Directory'),
            'report': FILE('hi3dgen-report.json.', kind='File'),
            'seed': {'type': 'integer'}, 'faces': {'type': 'integer'},
            'vertices': {'type': 'integer'}, 'peak_vram_gb': {'type': 'number'},
            'seconds': {'type': 'number'},
            'notes': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['file', 'normal_file']),
        backends=['hi3dgen'],
        resources={'ramBytes': 16 * GiB, 'vramBytes': {'auto': 12 * GiB}, 'diskBytes': 1 * GiB},
        category='Reconstruction')

    yield operation(
        'refine_mesh', 'Refine a mesh with TRELLIS.2 (LocalMesh)',
        'Regenerate the geometric detail of an existing mesh, keeping its overall shape: the mesh is '
        'encoded, its occupancy becomes the structure, and TRELLIS.2 samples the shape again on it '
        'from the reference picture, up to the 1536 grid. LocalMesh\'s own cleaning chain then closes '
        'the holes, removes the debris and brings it to the face budget, in the frame and at the '
        'scale of the input. Geometry only: texture the result with "Texture a mesh for its own '
        'topology".',
        OBJECT({
            'mesh_file': FILE('Mesh to refine, Y-up and facing like the LocalMesh output.', kind='File'),
            'subject_set': STRING('Folder produced by prepare_subject or complete_subject: the '
                                  'reference cut-out.', default='', **{'x-cy-kind': 'Directory'}),
            'image': FILE('Reference picture, when there is no subject set; it is cut out here.',
                          kind='Image'),
            'resolution': INTEGER('Grid the shape is sampled on again. 1536 needs a 24 GB card and '
                                  'is lowered by steps of 128 when the shape has too many tokens.',
                                  1536, enum=[1024, 1536]),
            'target_faces': INTEGER('Face budget of the result; 0 takes the recipe of that grid '
                                    '(250 000 on 1024, 400 000 on 1536).', 0, minimum=0,
                                    maximum=1_000_000),
            'use_all_views': BOOLEAN('Condition on every view of the subject set, not only the front. '
                                     'Experimental.', False),
            'steps': INTEGER('Sampling steps of the shape model.', 16, minimum=4, maximum=50,
                             advanced=True),
            'guidance': NUMBER('Shape guidance; 0 keeps the weights\' own value.', 0.0, minimum=0.0,
                               maximum=15.0, advanced=True),
            'seed': INTEGER('Seed (-1 draws one).', -1, minimum=-1, maximum=2 ** 31 - 1,
                            **{'x-cy-kind': 'Seed'}),
            'up_axis': STRING('Up axis of the input mesh.', default='y', enum=['y', 'z'],
                              advanced=True),
            'gpu': INTEGER('GPU index.', 0, minimum=0, maximum=7, advanced=True),
        }, required=['mesh_file']),
        OBJECT({
            'file': FILE('The refined mesh (GLB, geometry only).', kind='File'),
            'report': FILE('refine-report.json.', kind='File'),
            'seed': {'type': 'integer'}, 'grid_resolution': {'type': 'integer'},
            'token_cap': {'type': 'integer'}, 'faces': {'type': 'integer'},
            'vertices': {'type': 'integer'}, 'peak_vram_gb': {'type': 'number'},
            'seconds': {'type': 'number'},
            'notes': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['file', 'grid_resolution']),
        backends=['trellis'],
        resources={'ramBytes': 24 * GiB, 'vramBytes': {'auto': 24 * GiB}, 'diskBytes': 2 * GiB},
        category='Editing')

    yield operation(
        'texture_mesh', 'Texture a mesh for its own topology (LocalMesh)',
        'Give a remeshed model — QuadWild quads, a retopology, any mesh aligned with the reference — '
        'a texture made for that exact topology. "generate" asks TRELLIS.2 to generate it on this '
        'mesh from the reference picture, as LocalMesh does on its own mesh; "transfer" re-projects '
        'the texture of the detailed model instead, with no model. The detailed model, when given, '
        'is also baked into a normal map. Quads are kept in the OBJ; the GLB is triangulated, as '
        'glTF requires.',
        OBJECT({
            'mesh_file': FILE('Mesh to texture (OBJ keeps its quads; GLB, PLY, STL are read as '
                              'triangles). Y-up, facing like the LocalMesh output.', kind='File'),
            'subject_set': STRING('Folder produced by prepare_subject or complete_subject: the '
                                  'reference cut-out, and the other views for multi-view texturing.',
                                  default='', **{'x-cy-kind': 'Directory'}),
            'image': FILE('Reference picture, when there is no subject set; it is cut out here.',
                          kind='Image'),
            'detail_mesh': FILE('Detailed model aligned with this mesh (the LocalMesh output): '
                                'baked into the normal map, and the source of "transfer".',
                                kind='File'),
            'texture_source': STRING('generate: TRELLIS.2 generates the texture on this mesh. '
                                     'transfer: the texture of the detailed model is re-projected.',
                                     default='generate', enum=['generate', 'transfer']),
            'texture_size': INTEGER('Side of the atlas in pixels.', 4096,
                                    enum=[1024, 2048, 4096, 8192]),
            'multiview_texture': BOOLEAN('Guide the texture with every view of the subject set, not '
                                         'only the front. Experimental: never measured upstream.',
                                         False),
            'resolution': INTEGER('Texture model grid: 512 uses the 512 model, 1024 the 1024 one.',
                                  1024, enum=[512, 1024], advanced=True),
            'steps': INTEGER('Sampling steps of the texture model.', 16, minimum=4, maximum=50,
                             advanced=True),
            'guidance': NUMBER('Guidance of the texture model.', 5.0, minimum=1.0, maximum=12.0,
                               advanced=True),
            'seed': INTEGER('Seed (-1 draws one).', -1, minimum=-1, maximum=2 ** 31 - 1,
                            **{'x-cy-kind': 'Seed'}),
            'up_axis': STRING('Up axis of the input mesh.', default='y', enum=['y', 'z'],
                              advanced=True),
            'uv_padding': INTEGER('Padding between UV islands, in texels.', 4, minimum=1,
                                  maximum=32, advanced=True),
            'gpu': INTEGER('GPU index.', 0, minimum=0, maximum=7, advanced=True),
        }, required=['mesh_file']),
        OBJECT({
            'file': FILE('Textured GLB (triangulated, PBR with normal map).', kind='File'),
            'obj_file': FILE('Textured OBJ that keeps the quads, with its MTL.', kind='File'),
            'base_color_file': FILE('Base colour map.', kind='Image'),
            'normal_file': FILE('Tangent-space normal map, when a detailed model was given.',
                                kind='Image'),
            'roughness_file': FILE('Roughness map.', kind='Image'),
            'report': FILE('texture-report.json.', kind='File'),
            'seed': {'type': 'integer'}, 'faces': {'type': 'integer'},
            'polygons': {'type': 'integer'}, 'polygons_kept': {'type': 'integer'},
            'polygons_split': {'type': 'integer'}, 'texture_size': {'type': 'integer'},
            'texels_per_triangle': {'type': 'number'}, 'peak_vram_gb': {'type': 'number'},
            'seconds': {'type': 'number'},
            'notes': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['file', 'obj_file', 'base_color_file']),
        backends=['trellis'],
        resources={'ramBytes': 16 * GiB, 'vramBytes': {'auto': 10 * GiB}, 'diskBytes': 1 * GiB},
        category='Texturing')

    workflow_step = {
        'type': 'object',
        'description': 'One operation of the workflow.',
        'properties': {
            'operation': STRING('Operation id, as declared by this manifest.'),
            'backend': STRING('Backend id, when the operation supports several.', default=''),
            'parameters': {'type': 'object', 'description': 'Parameters of the operation.',
                           'additionalProperties': True},
            'input_from': STRING('Step id whose output feeds this step; empty means the workflow input.', default=''),
            'input_field': STRING('Output field of that step to use as the input.', default=''),
            'input_to': STRING('Parameter of this step that receives it; empty uses the field the '
                               'operation normally reads its input from.', default=''),
            'extra_inputs': {
                'type': 'array', 'maxItems': 8, 'default': [],
                'description': 'More values taken from earlier steps, when one input is not enough: '
                               'a retexturing step needs the new topology, the detailed original and '
                               'the prepared views.',
                'items': {'type': 'object', 'additionalProperties': False, 'required': ['to'],
                          'properties': {
                              'from': STRING('Earlier step id, or @input for the workflow input.'),
                              'field': STRING('Output field of that step; empty takes its main output.',
                                              default=''),
                              'to': STRING('Parameter of this step that receives it.'),
                          }},
            },
            'id': STRING('Identifier of this step inside the workflow.', default=''),
            'enabled': BOOLEAN('Run this step.', True),
            'continue_on_error': BOOLEAN(
                'Keep going when this step fails: what it received is handed on, as when it is '
                'switched off, and the failure is listed in the report.', False),
        },
        'required': ['operation'],
        'additionalProperties': False,
    }
    input_mode = STRING(
        'What a folder given as input means. each: the workflow runs once per file. together: it '
        'runs once, and its first step receives every file as one list: the photographs of one '
        'subject, whose roles prepare_subject reads from the file names.',
        default='each', enum=['each', 'together'])

    yield operation(
        'run_workflow', 'Run a workflow',
        'Run a saved chain of operations on one input or on every file of a folder. Each step is '
        'submitted as a real job on the same runtime as the interface, the CLI and MCP.',
        OBJECT({
            'workflow_name': STRING('Name of a workflow saved in data/workflows.', default=''),
            'workflow': {'type': 'object', 'description': 'Inline workflow document, instead of a saved name.',
                         'properties': {
                             'name': STRING('Name of the workflow.', default=''),
                             'description': STRING('What the workflow does.', default='', multiline=True),
                             'input_mode': input_mode,
                             'steps': {'type': 'array', 'items': workflow_step, 'minItems': 1, 'maxItems': 32},
                         },
                         'required': ['steps'], 'additionalProperties': False},
            'input_file': FILE('Input of the first step.'),
            'input_folder': STRING('Folder to process instead of a single file.', default='',
                                   **{'x-cy-kind': 'Directory'}),
            'input_pattern': STRING('Glob applied inside the folder.', default='*'),
            'input_mode': STRING('Overrides the input mode of the workflow: each (one run per file) '
                                 'or together (one run with every file). Empty: the workflow decides.',
                                 default='', enum=['', 'each', 'together'], advanced=True),
            'keep_intermediate': BOOLEAN('Keep the output of every step, not only the last one.', True),
            'stop_on_error': BOOLEAN('Stop the whole workflow at the first failed step.', True),
        }),
        OBJECT({
            'results': {'type': 'array', 'description': 'One entry per input processed.',
                        'items': {'type': 'object', 'additionalProperties': True}},
            'outputs': FILES('Final files produced by the workflow.', kind='Files'),
            'report_file': FILE('Report of the run.', kind='File'),
            'stepCount': {'type': 'integer'}, 'inputCount': {'type': 'integer'},
            'failedSteps': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'seconds': {'type': 'number'},
        }, required=['results', 'outputs', 'stepCount', 'inputCount']),
        backends=[], resources={'ramBytes': 1 * GiB}, category='Workflow')

    yield operation(
        'save_workflow', 'Save a workflow',
        'Write a workflow document to data/workflows so that the interface, the CLI and MCP can run it by name.',
        OBJECT({
            'name': STRING('Name of the workflow.'),
            'workflow': {'type': 'object', 'description': 'The workflow document.',
                         'properties': {
                             'name': STRING('Name of the workflow.', default=''),
                             'description': STRING('What the workflow does.', default='', multiline=True),
                             'input_mode': input_mode,
                             'steps': {'type': 'array', 'items': workflow_step, 'minItems': 1, 'maxItems': 32},
                         },
                         'required': ['steps'], 'additionalProperties': False},
            'overwrite': BOOLEAN('Replace an existing workflow with the same name.', False),
        }, required=['name', 'workflow']),
        OBJECT({'file': FILE('Saved document.', kind='File'), 'name': {'type': 'string'},
                'stepCount': {'type': 'integer'}}, required=['file', 'name', 'stepCount']),
        backends=[], resources={'ramBytes': 64 * MiB}, progress=False, category='Workflow')

    yield operation(
        'list_workflows', 'List the workflows',
        'List the workflows saved in data/workflows with their steps and the operations they use.',
        OBJECT({'include_steps': BOOLEAN('Include the full step list of every workflow.', False)}),
        OBJECT({'workflows': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
                'directory': STRING('Where the workflows are stored.')},
               required=['workflows', 'directory']),
        backends=[], resources={'ramBytes': 64 * MiB}, progress=False, category='Workflow')

    yield operation(
        'install_engine', 'Install or repair an engine',
        'Create or repair one of the engine environments declared in app/engines.json, including the '
        'upstream sources it needs. Downloads happen here, never during an inference job.',
        OBJECT({
            'engine': STRING('Engine to install.',
                             enum=['geometry', 'torch-cu124', 'trellis', 'diffusion',
                                   'wonder3d', 'syncdreamer', 'wham', 'hi3dgen']),
            'device': STRING('Build the CUDA variant or the CPU variant when the engine offers one.',
                             default='auto', enum=['auto', 'cuda', 'cpu']),
            'repair': BOOLEAN('Reinstall even when the engine reports itself as installed.', False),
            'sources_only': BOOLEAN('Only fetch or update the upstream sources.', False),
        }, required=['engine']),
        OBJECT({
            'engine': {'type': 'string'}, 'state': {'type': 'string'},
            'python': {'type': 'string'}, 'torch': {'type': 'string'}, 'cuda': {'type': 'boolean'},
            'log_file': FILE('Full installation log.', kind='File'),
            'sources': {'type': 'object', 'additionalProperties': True},
            'seconds': {'type': 'number'}, 'warnings': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['engine', 'state']),
        backends=[], resources={'ramBytes': 2 * GiB, 'diskBytes': 12 * GiB},
        category='Maintenance', permissions=['network'])

    yield operation(
        'install_model', 'Install or repair a model',
        'Download the weights of a model that is declared but absent, into data/models. Files whose '
        'licence is accepted in person are never downloaded here: the answer names them, and '
        'import_model_file puts them in place once obtained.',
        OBJECT({
            'model': STRING('Model identifier, as list_models reports it.'),
            'repair': BOOLEAN('Download again even when the files are already present.', False),
            'skip_optional': BOOLEAN('Leave the optional files out (global motion for WHAM).', False),
        }, required=['model']),
        OBJECT({
            'model': {'type': 'string'}, 'state': {'type': 'string'},
            'directory': FILE('Where the model was installed.', kind='Directory'),
            'missingFiles': {'type': 'array', 'items': {'type': 'string'}},
            'manualFiles': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'log_file': FILE('Full download log.', kind='File'),
            'seconds': {'type': 'number'}, 'warnings': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['model', 'state']),
        backends=[], resources={'ramBytes': 1 * GiB, 'diskBytes': 8 * GiB},
        category='Maintenance', permissions=['network'])

    yield operation(
        'import_model_file', 'Import a licensed model file',
        'Put in place a file the user downloaded themselves after accepting its licence, such as the '
        'SMPL body model. The application never asks for the credentials of those sites; it checks '
        'the file, copies it into data/models and records its hash.',
        OBJECT({
            'model': STRING('Model identifier, as list_models reports it.'),
            'file': STRING('The file downloaded from the official page (.pkl, or the .zip holding it).'),
            'target': STRING('Which declared file this is, when the model expects several.', default=''),
        }, required=['model', 'file']),
        OBJECT({
            'model': {'type': 'string'}, 'state': {'type': 'string'},
            'file': FILE('The installed file.', kind='File'),
            'sizeBytes': {'type': 'integer'},
            'missingFiles': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['model', 'file', 'state']),
        backends=[], resources={'ramBytes': 512 * MiB, 'diskBytes': 512 * MiB},
        category='Maintenance')

    yield operation(
        'update_status', 'Update state',
        'Where the three streams stand: the application version and its repository, what is staged, '
        'what is pending for the next start, the backups kept, the engines and their pinned '
        'revisions, and the model catalogue. Reads local files only.',
        OBJECT({}),
        OBJECT({
            'application': {'type': 'object', 'additionalProperties': True},
            'pending': {'type': ['object', 'null'], 'additionalProperties': True},
            'lastApplied': {'type': ['object', 'null'], 'additionalProperties': True},
            'staged': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'backups': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'engines': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'models': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
        }, required=['application']),
        backends=[], resources={'ramBytes': 128 * MiB}, progress=False, category='Maintenance')

    yield operation(
        'check_update', 'Check for an update',
        'Ask the configured GitHub repository for its latest release and compare it with the '
        'installed version. The engines and the weights streams answer from local files: they are '
        'updated by reinstalling an engine or a model, not by a release.',
        OBJECT({
            'stream': STRING('Which stream to check.', default='application',
                             enum=['application', 'engines', 'models']),
            'repository': STRING('GitHub repository owner/name; saved in data/settings/updates.json.',
                                 default=''),
            'release_file': STRING('A release description already on disk, instead of asking GitHub '
                                   '(used by the tests).', default='', **{'x-cy-kind': 'File'}),
        }),
        OBJECT({
            'stream': {'type': 'string'}, 'updateAvailable': {'type': 'boolean'},
            'message': {'type': 'string'},
            'report': {'type': 'object', 'additionalProperties': True},
        }, required=['stream', 'report']),
        backends=[], resources={'ramBytes': 256 * MiB},
        category='Maintenance', permissions=['network'])

    yield operation(
        'stage_update', 'Stage an update',
        'Download or copy a release archive, check its SHA-256 when one is given, unpack it under '
        'runtime/updates and verify it holds this Tool and no data folder. Nothing is activated: '
        'the running application is untouched.',
        OBJECT({
            'source': STRING('URL of the release asset, or a local .zip.'),
            'sha256': STRING('Expected SHA-256 of the archive; refused when it differs.', default=''),
            'version': STRING('Name of the staging folder; defaults to the archive digest.', default=''),
        }, required=['source']),
        OBJECT({
            'staged': FILE('Where the update was unpacked.', kind='Directory'),
            'version': {'type': 'string'}, 'sha256': {'type': 'string'},
            'stream': {'type': 'string'}, 'source': {'type': 'string'},
            'files': {'type': 'integer'}, 'archiveBytes': {'type': 'integer'},
            'stagedAt': {'type': 'string'},
            'verified': {'type': 'object', 'additionalProperties': True},
        }, required=['staged', 'version']),
        backends=[], resources={'ramBytes': 512 * MiB, 'diskBytes': 1 * GiB},
        category='Maintenance', permissions=['network'])

    yield operation(
        'activate_update', 'Activate a staged update',
        'Verify a staged update once more and record the swap for the next start. The folders are '
        'exchanged by a separate process before the application loads, so the running code is never '
        'replaced underneath itself, the previous app folder is kept as a backup, and data/ is not '
        'touched.',
        OBJECT({'staged': STRING('Staged folder; the most recent one when left empty.',
                                 default='', **{'x-cy-kind': 'Directory'})}),
        OBJECT({
            'pending': FILE('The recorded request.', kind='File'),
            'restartRequired': {'type': 'boolean'}, 'mode': {'type': 'string'},
            'version': {'type': 'string'}, 'fromVersion': {'type': 'string'},
            'source': {'type': 'string'}, 'requestedAt': {'type': 'string'},
            'verified': {'type': 'object', 'additionalProperties': True},
        }, required=['pending', 'restartRequired']),
        backends=[], resources={'ramBytes': 256 * MiB}, category='Maintenance')

    yield operation(
        'rollback_update', 'Roll back to a backup',
        'Record the reverse swap: the next start restores a kept backup of the app folder. Cancelling '
        'instead drops a pending request. Your data is never part of either move.',
        OBJECT({
            'backup': STRING('Backup folder to restore; the most recent one when left empty.',
                             default='', **{'x-cy-kind': 'Directory'}),
            'cancel': BOOLEAN('Drop the pending request instead of rolling back.', False),
        }),
        OBJECT({
            'pending': {'type': 'string'}, 'restartRequired': {'type': 'boolean'},
            'mode': {'type': 'string'}, 'version': {'type': 'string'},
            'fromVersion': {'type': 'string'}, 'source': {'type': 'string'},
            'cancelled': {'type': 'boolean'}, 'requestedAt': {'type': 'string'},
        }, required=['restartRequired']),
        backends=[], resources={'ramBytes': 256 * MiB}, category='Maintenance')

    yield operation(
        'diagnose', 'Diagnose the installation',
        'Report the state of every engine, backend, native program and model: what is installed, what is '
        'missing, and which device each backend would really use.',
        OBJECT({'engine': STRING('Restrict the report to one engine.', default=''),
                'deep': BOOLEAN('Also start each installed engine to report its real torch and device.', False)}),
        OBJECT({
            'engines': {'type': 'object', 'additionalProperties': True},
            'backends': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'models': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
            'natives': {'type': 'object', 'additionalProperties': True},
            'platform': {'type': 'object', 'additionalProperties': True},
            'warnings': {'type': 'array', 'items': {'type': 'string'}},
        }, required=['engines', 'backends', 'models']),
        backends=[], resources={'ramBytes': 512 * MiB}, progress=False, category='Maintenance')

    yield operation(
        'list_models', 'List the models',
        'List every model of the catalogue with its family, its engine, its size on disk, its licence and '
        'whether it is installed.',
        OBJECT({'family': STRING('Restrict to one family.', default=''),
                'installed_only': BOOLEAN('Only the models present on disk.', False)}),
        OBJECT({'models': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}},
                'totalBytes': {'type': 'integer'}, 'directory': {'type': 'string'}},
               required=['models', 'totalBytes', 'directory']),
        backends=[], resources={'ramBytes': 256 * MiB}, progress=False, category='Maintenance')


# --------------------------------------------------------------------------- manifest

def catalogue():
    path = APP / 'models' / 'catalog.json'
    if not path.is_file():
        return {}
    return {item['id']: item for item in json.loads(path.read_text('utf-8'))['models']}


def backend_descriptors():
    """Declared backends, with the models the catalogue really holds for each one."""
    sys.path.insert(0, str(APP))
    from meshstudio.backends import registry as backend_registry  # noqa: E402
    from meshstudio.engines import registry as engine_registry  # noqa: E402

    models = catalogue()
    engines = engine_registry.spec()['engines']
    descriptors = []
    for backend in backend_registry.BACKENDS.values():
        engine = engines.get(backend.engine, {})
        version = ''
        for source in (engine.get('sources') or {}).values():
            version = source['revision']
            break
        entries = []
        for model_id in backend.models:
            item = models.get(model_id)
            if item is None:
                continue
            entries.append({
                'id': model_id,
                'name': item['name'],
                'version': item['revision'] or 'unknown',
                'source': item['source']['url'] or item['source']['repository'],
                'license': item['license'],
                'location': 'Local',
                'runsLocally': True,
                'installed': item['installed'],
                'installedSize': item['sizeBytes'],
                'computeBackends': ['CPU'] if backend.engine == 'geometry' else ['CUDA'],
            })
        descriptors.append({
            'id': backend.id,
            'name': backend.label,
            'version': version or engine.get('python', ''),
            'models': entries,
            'threadSafe': False,
            'shareableModelInstance': False,
            'concurrentInference': False,
            'maxConcurrentInference': 1,
        })
    return descriptors


def platforms():
    tested = {}
    if TESTED.is_file():
        tested = json.loads(TESTED.read_text('utf-8'))
    entries = []
    for os_name, architecture, status, backends in (
            ('Windows', 'x64', 'Experimental', ['CPU', 'CUDA']),
            ('Linux', 'x64', 'Unknown', ['CPU', 'CUDA']),
            ('macOS', 'ARM64', 'Unsupported', ['CPU']),
    ):
        item = {'os': os_name, 'architecture': architecture, 'status': status, 'computeBackends': backends}
        records = tested.get(os_name)
        if records:
            item['tested'] = records
            item['status'] = records[-1].get('status', status)
        entries.append(item)
    return entries


def build():
    operations = ported_operations() + list(new_operations())
    manifest = {
        'schemaVersion': 1,
        'protocolVersion': '1.0',
        'id': TOOL_ID,
        'name': TOOL_NAME,
        'version': VERSION,
        'description': 'Mesh studio: specialised operations (reconstruction, views, remesh, UV, PBR, rig, '
                       'motion, editing) and complete workflows that chain them, in one standalone '
                       'application usable through its interface, the CLI and MCP.',
        'vendor': 'Cyberalien',
        'author': 'Cyberalien',
        # The GitHub repository of the Tool: shown in Options, and the default source of the
        # application update stream when none has been typed in the Updates tab.
        'homepage': 'https://github.com/MrMybal/CyTools_MeshStudio',
        'repository': 'MrMybal/CyTools_MeshStudio',
        # SPDX identifier, as CyToolsCore declares it. Engines, models and dependencies keep
        # their own licences: app/Docs/ThirdPartyNotices.md, shown in Options with this one.
        'license': 'GPL-3.0-only',
        'licenseUrl': 'https://github.com/MrMybal/CyTools_MeshStudio/blob/main/LICENSE',
        'executable': 'runtime/python/Scripts/python.exe app/tool.py',
        'standaloneExecutable': 'CyTools_MeshStudio.exe',
        'distributionStatus': 'Standalone Windows delivery: launcher, ImGui interface, CLI and MCP run. Eight engines built and eighteen of the twenty backends executed here; WHAM waits for the SMPL body model, which is accepted in person. Updates are implemented and tested on a fixture release, never against a published one. The validation report is kept with the installation '
                              '(data/reports/VALIDATION.md).',
        'categories': ['3d', 'mesh', 'reconstruction', 'rigging', 'texturing'],
        'tags': ['mesh', 'remesh', 'uv', 'pbr', 'rig', 'views', 'workflow', 'imgui'],
        'capabilities': ['jobs', 'cancellation', 'progress', 'desktop-ui', 'mesh-viewer',
                         'model-installer', 'github-updates', 'workflows'],
        'backends': backend_descriptors(),
        'platforms': platforms(),
        'interfaces': ['Native', 'CLI', 'JSONL', 'HTTP', 'MCP', 'ImGui'],
        'runtimeRequirements': [],
        'concurrency': {'policy': 'Sequential', 'maxWorkers': 1},
        'idleUnloadPolicy': 'After5Minutes',
        'operations': operations,
    }
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='exit 1 when CyTool.json is stale')
    args = parser.parse_args(argv)
    manifest = build()
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        current = OUT.read_text('utf-8') if OUT.is_file() else ''
        if current != text:
            print('CyTool.json is stale: run python app/build_manifest.py')
            return 1
        print('CyTool.json is up to date.')
        return 0
    OUT.write_text(text, encoding='utf-8')
    print(f'{len(manifest["operations"])} operations -> {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
