"""Run a workflow: every step is an operation of this Tool, executed in order.

The steps of one workflow run inside the job that started it, sequentially, by calling the
same handlers the CLI, MCP and the interface call. That keeps one reservation for the whole
chain instead of one per step, so ``run_workflow`` estimates its resources as the maximum
of its steps (see ``estimate``); a step that needs more than the job reserved would be
reported by the scheduler before anything starts.

Each step writes into its own folder of the job workspace, so a later step can read the
output of an earlier one and nothing overwrites anything.
"""
import json
from pathlib import Path
import time

from cytools_core import CyToolError, validate_parameters

from . import model as workflow_model


class StepContext:
    """A JobContext view whose ``path`` is confined to one step folder.

    Progress is rescaled to the slice of the whole workflow this step occupies, so the
    progress bar of the job moves once per step instead of restarting at zero each time.
    """

    def __init__(self, context, folder, offset, scale, label):
        self._context = context
        self._folder = folder
        self._offset = offset
        self._scale = scale
        self._label = label

    def __getattr__(self, name):
        return getattr(self._context, name)

    @property
    def workspace(self):
        return self._folder

    def path(self, relative):
        target = self._folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def progress(self, percent, **fields):
        fields.setdefault('currentStep', self._label)
        self._context.progress(max(0.0, min(100.0, self._offset + float(percent) * self._scale)), **fields)

    def log(self, message, level='Info'):
        self._context.log(f'[{self._label}] {message}', level=level)


def _output_file(result, field=''):
    """The file a following step should read from a finished step."""
    if field:
        value = result.get(field)
        if not value:
            raise CyToolError('InvalidParameters',
                              f'The step produced no "{field}" output (available: {", ".join(sorted(result))})')
        return value
    for candidate in workflow_model.MESH_OUTPUT_FIELDS:
        if result.get(candidate):
            return result[candidate]
    for candidate in workflow_model.IMAGE_OUTPUT_FIELDS:
        if result.get(candidate):
            return result[candidate]
    raise CyToolError('InvalidParameters',
                      'The step produced no file output to feed the next step; '
                      'name one with input_field')


def _apply_input(step, parameters, value):
    """Put the incoming value in the parameter that receives it.

    By default that is the field the operation reads its main input from; a step that
    consumes something else — a prepared subject folder rather than a mesh — names it with
    ``input_to``.
    """
    operation = step['operation']
    field = step.get('input_to') or workflow_model.INPUT_FIELD.get(operation)
    if not field:
        return parameters
    if field in parameters and parameters[field]:
        return parameters  # the step declares its own input explicitly
    if field in workflow_model.LIST_FIELDS:
        values = value if isinstance(value, list) else [value]
        parameters[field] = [str(item) for item in values]
    else:
        parameters[field] = str(value[0] if isinstance(value, list) else value)
    return parameters


def _passed_through(step, produced, previous_id, source):
    """What a disabled step hands on: exactly what it would have received.

    That is what makes an optional step optional: the steps after it read from it by name, and
    when it is switched off they get the output of the step that fed it, unchanged. Its output
    fields are those of that step, so an optional step should produce the same field names as
    the one it would replace (``file`` for a mesh, ``subject_set`` for views).
    """
    feeding = step['input_from'] or previous_id
    if feeding and feeding in produced:
        return produced[feeding]
    if isinstance(source, list):
        return {'file': str(source[0]), 'files': [str(item) for item in source]} if source else {}
    return {'file': str(source)} if source else {}


def _describe_input(source):
    if isinstance(source, list):
        return [str(item) for item in source]
    return str(source) if source else ''


def run(context, document, handlers, inputs, *, keep_intermediate=True, stop_on_error=True,
        schemas=None):
    """Execute the workflow over each input and return one result entry per input.

    An input is one file, or a list of files for a workflow whose ``input_mode`` is
    ``together`` (the photographs of one subject, given to its first step at once).

    A step marked ``continue_on_error`` that fails hands on what it received, exactly as when
    it is switched off, and the chain goes on: a comparison of engines keeps the others when one
    of them fails, and an optional refinement that fails leaves the unrefined model to the rest.

    ``schemas`` maps an operation to its input schema. Each step's parameters are then
    validated and completed with their defaults exactly as a job submitted on its own would
    be: a step calls its handler directly, and without this a misspelt parameter or a missing
    default only surfaced inside the worker, after the steps before it had been paid for.
    """
    every_step = list(document['steps'])
    disabled = {step['id'] for step in every_step if not step['enabled']}
    steps = [step for step in every_step if step['enabled']]
    if not steps:
        raise CyToolError('InvalidParameters', 'Every step of this workflow is disabled')
    unknown = [step['operation'] for step in steps if step['operation'] not in handlers]
    if unknown:
        raise CyToolError('InvalidParameters', f'Unknown operation(s): {", ".join(sorted(set(unknown)))}')

    started = time.monotonic()
    results, outputs, failures = [], [], []
    total_units = max(1, len(inputs) * len(steps))
    unit = 100.0 / total_units

    for input_index, source in enumerate(inputs):
        context.cancellation.check()
        entry = {'input': _describe_input(source), 'steps': [], 'output': '', 'failed': False}
        current = source
        produced = {}
        executed = 0          # enabled steps run so far, for the progress bar
        last_id = None        # the step whose output a step without input_from reads
        for position, step in enumerate(every_step):
            if step['id'] in disabled:
                produced[step['id']] = _passed_through(step, produced, last_id, current)
                entry['steps'].append({'id': step['id'], 'operation': step['operation'],
                                       'ok': True, 'skipped': True,
                                       'note': 'disabled: its input was passed on unchanged'})
                last_id = step['id']
                continue
            step_index = executed
            context.cancellation.check()
            offset = (input_index * len(steps) + step_index) * unit
            label = f'{step["operation"]} ({step_index + 1}/{len(steps)})'
            # Folders are numbered by position in the workflow, so a step keeps its folder
            # whether the optional steps before it are switched on or off.
            folder = Path(context.workspace) / 'workflow' / f'input{input_index + 1}' / f'{position + 1}-{step["id"]}'
            folder.mkdir(parents=True, exist_ok=True)
            step_context = StepContext(context, folder, offset, unit / 100.0, label)

            parameters = dict(step['parameters'])
            if step['input_from']:
                previous = produced.get(step['input_from'])
                if previous is None:
                    raise CyToolError('InvalidParameters',
                                      f'Step "{step["id"]}" reads from "{step["input_from"]}", which did not run')
                incoming = _output_file(previous, step['input_field'])
            elif last_id is None:
                incoming = current
            else:
                incoming = _output_file(produced[last_id], step['input_field'])
            if incoming:
                parameters = _apply_input(step, parameters, incoming)
            for item in step.get('extra_inputs') or []:
                if parameters.get(item['to']):
                    continue      # the step sets that parameter itself
                if item['from'] == workflow_model.WORKFLOW_INPUT:
                    value = source
                else:
                    earlier = produced.get(item['from'])
                    if earlier is None:
                        raise CyToolError('InvalidParameters',
                                          f'Step "{step["id"]}" takes "{item["to"]}" from '
                                          f'"{item["from"]}", which did not run')
                    value = _output_file(earlier, item['field'])
                if value:
                    parameters = _apply_input({**step, 'input_to': item['to']}, parameters, value)

            context.progress(offset, currentStep=label,
                             statusMessage=f'Input {input_index + 1} of {len(inputs)}')
            step_started = time.monotonic()
            try:
                if schemas and step['operation'] in schemas:
                    try:
                        parameters = validate_parameters(parameters, schemas[step['operation']])
                    except CyToolError as exc:
                        raise CyToolError('InvalidParameters',
                                          f'Parameters of step "{step["id"]}": {exc}') from exc
                result = handlers[step['operation']](step_context, parameters)
            except CyToolError as exc:
                record = {'id': step['id'], 'operation': step['operation'], 'ok': False,
                          'code': exc.code, 'message': str(exc),
                          'seconds': round(time.monotonic() - step_started, 2)}
                entry['failed'] = True
                if step['continue_on_error']:
                    record['note'] = 'failed: its input was passed on unchanged'
                    entry['steps'].append(record)
                    failures.append({**record, 'input': entry['input']})
                    context.log(f'[{label}] failed, the workflow goes on without it: {exc}',
                                level='Warning')
                    produced[step['id']] = _passed_through(step, produced, last_id, current)
                    last_id = step['id']
                    executed += 1
                    continue
                entry['steps'].append(record)
                failures.append({**record, 'input': entry['input']})
                if stop_on_error:
                    results.append(entry)
                    raise CyToolError(exc.code, f'Step "{step["operation"]}" failed: {exc}',
                                      recoverable=getattr(exc, 'recoverable', False),
                                      details={'step': step['id'], 'input': entry['input'],
                                               'results': results})
                break
            produced[step['id']] = result
            last_id = step['id']
            executed += 1
            entry['steps'].append({'id': step['id'], 'operation': step['operation'], 'ok': True,
                                   'seconds': round(time.monotonic() - step_started, 2),
                                   'outputs': {key: value for key, value in result.items()
                                               if isinstance(value, str) and key.endswith(('file', 'mesh', '_file'))}})
            if not keep_intermediate and step_index and step_index < len(steps) - 1:
                entry['steps'][-1]['outputs'] = {}

        if produced:
            last = produced[list(produced)[-1]]
            try:
                entry['output'] = str(_output_file(last))
                outputs.append(entry['output'])
            except CyToolError:
                entry['output'] = ''
            entry['result'] = last
        results.append(entry)

    report = Path(context.path('outputs/workflow-report.json'))
    report.write_text(json.dumps({'workflow': document['name'], 'steps': len(steps),
                                  'inputs': len(inputs), 'results': results,
                                  'failedSteps': failures,
                                  'seconds': round(time.monotonic() - started, 2)},
                                 indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    context.progress(100, currentStep='Workflow finished',
                     statusMessage=f'{len(outputs)} output(s) from {len(inputs)} input(s)')
    return {'results': results, 'outputs': outputs, 'report_file': str(report),
            'stepCount': len(steps), 'inputCount': len(inputs), 'failedSteps': failures,
            'seconds': round(time.monotonic() - started, 2)}


def estimate(document, manifest_operations, step_estimate=None):
    """Resources of a workflow: the maximum of its steps, since they run one after another.

    Only the enabled steps count: an optional step switched off must not reserve anything —
    an unticked refinement on the 1536 grid once made a whole workflow ask for 24 GiB and be
    refused before it started. ``step_estimate(step)`` gives a step's own estimate from its
    parameters (the tier, the grid, the atlas size); without it the manifest's declaration is
    used.
    """
    budget = {'ramBytes': 512 * 1024 ** 2, 'diskBytes': 256 * 1024 ** 2}
    vram = 0
    for step in document.get('steps', []):
        if not step.get('enabled', True):
            continue
        declared = manifest_operations.get(step['operation'], {}).get('resourceRequirements', {})
        if step_estimate is not None:
            try:
                declared = {**declared, **(step_estimate(step) or {})}
            except Exception:  # noqa: BLE001 - an estimate must never block a run
                pass
        budget['ramBytes'] = max(budget['ramBytes'], declared.get('ramBytes', 0))
        budget['diskBytes'] = max(budget['diskBytes'], declared.get('diskBytes', 0))
        requested = declared.get('vramBytes')
        if isinstance(requested, dict):
            vram = max(vram, max(requested.values()))
    if vram:
        budget['vramBytes'] = {'auto': vram}
    return budget
