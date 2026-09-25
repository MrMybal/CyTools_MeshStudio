"""Handlers of the workflow operations: run, save and list."""
import json
from pathlib import Path

from cytools_core import CyToolError

from ..paths import WORKFLOWS
from ..workflow import model as workflow_model
from ..workflow import runner as workflow_runner
from .common import IMAGE_SUFFIXES, MESH_SUFFIXES, VIDEO_SUFFIXES, fit_to_card

ACCEPTED = tuple(sorted(set(MESH_SUFFIXES + IMAGE_SUFFIXES + VIDEO_SUFFIXES)))
MAX_INPUTS = 500


def workflow_path(name):
    candidate = Path(name)
    if candidate.suffix.lower() == '.json' and candidate.is_file():
        return candidate
    return WORKFLOWS / (workflow_model.safe_name(name) + '.json')


def register(runtime, services, handlers, manifest_operations):
    known_operations = set(manifest_operations)

    def resolve_document(parameters):
        document = parameters.get('workflow')
        name = (parameters.get('workflow_name') or '').strip()
        try:
            if document:
                return workflow_model.validate(document, known_operations)
            if name:
                return workflow_model.load(workflow_path(name), known_operations)
        except workflow_model.WorkflowError as exc:
            raise CyToolError('InvalidParameters', str(exc)) from exc
        raise CyToolError('InvalidParameters', 'Provide workflow_name or an inline workflow document')

    def collect_inputs(parameters, mode='each'):
        """The inputs of the run: one per file, or a single list of every file (``together``)."""
        folder = (parameters.get('input_folder') or '').strip()
        single = (parameters.get('input_file') or '').strip()
        if folder:
            root = Path(folder).expanduser()
            if not root.is_dir():
                raise CyToolError('MissingInput', f'Folder not found: {folder}', recoverable=True)
            pattern = parameters.get('input_pattern') or '*'
            found = sorted(item for item in root.glob(pattern)
                           if item.is_file() and item.suffix.lower() in ACCEPTED)
            if not found:
                raise CyToolError('MissingInput',
                                  f'No supported file matches "{pattern}" in {folder}', recoverable=True)
            if len(found) > MAX_INPUTS:
                raise CyToolError('InvalidParameters',
                                  f'{len(found)} files matched; this operation is limited to {MAX_INPUTS}')
            files = [str(item.resolve()) for item in found]
            return [files] if mode == 'together' else files
        if single:
            path = Path(single).expanduser()
            if not path.is_file():
                raise CyToolError('MissingInput', f'File not found: {single}', recoverable=True)
            return [[str(path.resolve())]] if mode == 'together' else [str(path.resolve())]
        # A workflow whose first step needs no file (a turntable from saved views, for example).
        return ['']

    def run_workflow(context, parameters):
        document = resolve_document(parameters)
        mode = parameters.get('input_mode') or document.get('input_mode', 'each')
        inputs = collect_inputs(parameters, mode)
        if mode == 'together':
            context.log(f'Workflow "{document["name"]}": {len(document["steps"])} step(s), '
                        f'{len(inputs[0]) if inputs[0] else 0} file(s) taken together as one subject')
        else:
            context.log(f'Workflow "{document["name"]}": {len(document["steps"])} step(s) over {len(inputs)} input(s)')
        return workflow_runner.run(context, document, handlers, inputs,
                                   keep_intermediate=parameters.get('keep_intermediate', True),
                                   stop_on_error=parameters.get('stop_on_error', True),
                                   schemas={name: item['inputSchema']
                                            for name, item in manifest_operations.items()})

    def save_workflow(context, parameters):
        name = workflow_model.safe_name(parameters['name'])
        try:
            document = workflow_model.validate({**parameters['workflow'], 'name': parameters['name']},
                                               known_operations)
        except workflow_model.WorkflowError as exc:
            raise CyToolError('InvalidParameters', str(exc)) from exc
        path = WORKFLOWS / (name + '.json')
        if path.exists() and not parameters.get('overwrite'):
            raise CyToolError('AlreadyExists',
                              f'A workflow named "{name}" already exists; pass overwrite=true to replace it')
        workflow_model.save(document, path)
        return {'file': str(path), 'name': document['name'], 'stepCount': len(document['steps'])}

    def list_workflows(context, parameters):
        WORKFLOWS.mkdir(parents=True, exist_ok=True)
        rows = []
        for path in sorted(WORKFLOWS.glob('*.json')):
            try:
                document = workflow_model.load(path, known_operations)
            except workflow_model.WorkflowError as exc:
                rows.append({'name': path.stem, 'file': str(path), 'valid': False, 'error': str(exc)})
                continue
            rows.append({**workflow_model.describe(document, parameters.get('include_steps', False)),
                         'file': str(path), 'valid': True})
        return {'workflows': rows, 'directory': str(WORKFLOWS)}

    def step_estimate(step):
        """A step's own estimate from its parameters: the tier, the grid, the atlas size."""
        estimator = getattr(runtime, '_estimators', {}).get(step['operation'])
        return estimator(dict(step.get('parameters') or {}), None, None) if estimator else {}

    def estimate(parameters, backend, model):
        try:
            document = resolve_document(parameters)
        except CyToolError:
            return {'ramBytes': 1024 ** 3, 'diskBytes': 1024 ** 3}
        return fit_to_card(runtime, workflow_runner.estimate(document, manifest_operations,
                                                             step_estimate=step_estimate))

    runtime.register('run_workflow', run_workflow, estimate=estimate)
    runtime.register('save_workflow', save_workflow)
    runtime.register('list_workflows', list_workflows)
