"""Workflow document: versioned JSON, validated, executing nothing on load.

A workflow is a chain of operations of this Tool. It is data, not code:

{
  "format": "cytools-meshstudio-workflow", "schemaVersion": 1,
  "name": "Photo to game asset", "description": "",
  "createdAt": "...", "updatedAt": "...",
  "steps": [
    {"id": "s1", "operation": "image_to_mesh_triposr", "backend": "triposr",
     "parameters": {"mc_resolution": 256}, "enabled": true},
    {"id": "s2", "operation": "remesh_auto", "input_from": "s1", "input_field": "mesh_file",
     "parameters": {"target_quads": 4000}},
    {"id": "s3", "operation": "uv_unwrap", "input_from": "s2", "input_field": "file"},
    {"id": "s4", "operation": "texture_pbr", "input_from": "s3", "input_field": "mesh"}
  ]
}

``input_from`` names the step whose output feeds this one, ``input_field`` which of its
output fields carries the value, and ``input_to`` which parameter of this step receives it.
All three may be omitted: the runner then takes the previous step's main mesh output and
puts it in the field that operation reads its input from, and the workflow input feeds the
first step. ``input_to`` is what lets a step consume something other than a mesh file — a
prepared subject folder, for instance.

A step that needs more than one thing from earlier steps lists them in ``extra_inputs``:
``[{"from": "mesh", "field": "file", "to": "detail_mesh"}, ...]``. ``from`` is an earlier
step, or ``@input`` for the file the workflow was started on. Retexturing a remeshed model is
the case that needs it: the new topology, the detailed original and the prepared views all
come from different steps.

``input_mode`` says what a folder given as input means. ``each`` (the default) runs the whole
chain once per file. ``together`` runs it once, with every file as one input: the photographs
of one subject, which the first step receives as a list.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

FORMAT = 'cytools-meshstudio-workflow'
SCHEMA_VERSION = 1
MAX_STEPS = 32
#: ``from`` value of an extra input that means the file the workflow was started on.
WORKFLOW_INPUT = '@input'
#: What a folder given as input means: one run per file, or one run with all of them.
INPUT_MODES = ('each', 'together')

# Output fields that carry the main file of an operation, most specific first.
MESH_OUTPUT_FIELDS = ('material_mesh_file', 'rigged_mesh', 'mesh_file', 'mesh', 'file', 'motion')
IMAGE_OUTPUT_FIELDS = ('directory', 'thumbnail', 'preview_file')

# Input field an operation reads its main file from.
INPUT_FIELD = {
    'remesh_auto': 'input_file',
    'remesh_field': 'input',
    'uv_unwrap': 'input',
    'uv_repack': 'input',
    'texture_pbr': 'mesh_file',
    'mesh_inspect': 'mesh_file',
    'mesh_edit': 'mesh_file',
    'mesh_convert': 'mesh_file',
    'image_to_mesh_triposr': 'image_file',
    'image_to_mesh_spar3d': 'image_file',
    'photos_to_mesh': 'front',
    'mesh_to_rig': 'mesh',
    'video_to_motion': 'video',
    'video_inspect': 'video',
    'construct_proxy': 'images',
    'analyze_views': 'images',
    'views_generate': 'images',
    'views_auto_complete': 'images',
    'views_turntable': 'images',
    'views_mirror': 'images',
    'views_validate': 'images',
    'segment_object': 'images',
    'prepare_subject': 'front',
    'complete_subject': 'image',
    'texture_mesh': 'mesh_file',
    'refine_mesh': 'mesh_file',
    'image_to_mesh_hi3dgen': 'image',
}
#: Input fields that take a list of paths rather than one.
LIST_FIELDS = frozenset({'images', 'generated_views', 'candidates'})
LIST_INPUT_OPERATIONS = {name for name, field in INPUT_FIELD.items() if field in LIST_FIELDS}


class WorkflowError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def safe_name(name, fallback='workflow'):
    cleaned = re.sub(r'[^A-Za-z0-9._ -]+', '_', str(name or '')).strip(' ._')
    return cleaned[:80] or fallback


def new_workflow(name='Untitled workflow', steps=None, description=''):
    return validate({'format': FORMAT, 'schemaVersion': SCHEMA_VERSION, 'name': name,
                     'description': description, 'createdAt': _now(), 'updatedAt': _now(),
                     'steps': list(steps or [])})


def normalize_step(step, known_operations=None):
    if not isinstance(step, dict):
        raise WorkflowError('A step must be an object')
    operation = str(step.get('operation') or '')
    if not operation:
        raise WorkflowError('A step must name an operation')
    if known_operations is not None and operation not in known_operations:
        raise WorkflowError(f'Unknown operation "{operation}"')
    parameters = step.get('parameters') or {}
    if not isinstance(parameters, dict):
        raise WorkflowError(f'Parameters of step "{operation}" must be an object')
    extra = step.get('extra_inputs') or []
    if not isinstance(extra, list):
        raise WorkflowError(f'extra_inputs of step "{operation}" must be a list')
    extra_inputs = []
    for item in extra:
        if not isinstance(item, dict) or not item.get('to'):
            raise WorkflowError(f'Each extra input of step "{operation}" needs "from" and "to"')
        extra_inputs.append({'from': str(item.get('from') or ''),
                             'field': str(item.get('field') or ''),
                             'to': str(item['to'])})
    return {'id': str(step.get('id') or uuid.uuid4().hex[:8]),
            'operation': operation,
            'backend': str(step.get('backend', '') or ''),
            'parameters': dict(parameters),
            'input_from': str(step.get('input_from', '') or ''),
            'input_field': str(step.get('input_field', '') or ''),
            'input_to': str(step.get('input_to', '') or ''),
            'extra_inputs': extra_inputs,
            'enabled': bool(step.get('enabled', True)),
            'continue_on_error': bool(step.get('continue_on_error', False))}


def validate(document, known_operations=None):
    if not isinstance(document, dict):
        raise WorkflowError('A workflow must be an object')
    steps = document.get('steps')
    if not isinstance(steps, list) or not steps:
        raise WorkflowError('A workflow needs at least one step')
    if len(steps) > MAX_STEPS:
        raise WorkflowError(f'A workflow is limited to {MAX_STEPS} steps')
    normalized = [normalize_step(step, known_operations) for step in steps]
    identifiers = [step['id'] for step in normalized]
    if len(set(identifiers)) != len(identifiers):
        raise WorkflowError('Two steps share the same id')
    known = set()
    for step in normalized:
        if step['input_from']:
            if step['input_from'] not in known:
                raise WorkflowError(f'Step "{step["id"]}" reads from "{step["input_from"]}", '
                                    'which is not one of the steps before it')
        for item in step['extra_inputs']:
            if item['from'] != WORKFLOW_INPUT and item['from'] not in known:
                raise WorkflowError(f'Step "{step["id"]}" takes "{item["to"]}" from '
                                    f'"{item["from"]}", which is not one of the steps before it')
        known.add(step['id'])
    input_mode = str(document.get('input_mode') or 'each')
    if input_mode not in INPUT_MODES:
        raise WorkflowError(f'input_mode must be one of {", ".join(INPUT_MODES)}')
    return {'format': FORMAT, 'schemaVersion': SCHEMA_VERSION,
            'name': str(document.get('name') or 'Untitled workflow'),
            'description': str(document.get('description') or ''),
            'input_mode': input_mode,
            'createdAt': str(document.get('createdAt') or _now()),
            'updatedAt': _now(), 'steps': normalized}


def load(path, known_operations=None):
    try:
        document = json.loads(Path(path).read_text('utf-8'))
    except OSError as exc:
        raise WorkflowError(f'Cannot read {path}: {exc}') from exc
    except ValueError as exc:
        raise WorkflowError(f'{path} is not valid JSON: {exc}') from exc
    if document.get('format') not in (FORMAT, None):
        raise WorkflowError(f'{path} is not a CyTools_MeshStudio workflow')
    return validate(document, known_operations)


def save(document, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path


def describe(document, include_steps=False):
    summary = {'name': document['name'], 'description': document['description'],
               'stepCount': len(document['steps']),
               'operations': [step['operation'] for step in document['steps']],
               'input_mode': document.get('input_mode', 'each'),
               'updatedAt': document.get('updatedAt', '')}
    if include_steps:
        summary['steps'] = document['steps']
    return summary
