"""The Workflows tab: build a chain of operations, save it, run it on a file or a folder.

A workflow is the same document the CLI and MCP run; this panel only edits it and submits
``run_workflow``. Nothing is executed here, and the steps are the operations of the manifest,
so a workflow built in the interface runs identically from an AI client.
"""
import json
from pathlib import Path

from imgui_bundle import imgui

from gui import widgets


class WorkflowPanel:
    def __init__(self, app):
        self.app = app
        self.editor = widgets.ParameterEditor(app.dialogs, app.tr)
        self.workflows = []
        self.selected = -1
        self.document = {'name': 'New workflow', 'description': '', 'steps': []}
        self.input_file = ''
        self.input_folder = ''
        self.input_pattern = '*'
        self.step_choice = 0
        self.editing_step = -1
        self.message = ''
        self.error = ''
        self.shown_error = ''
        self.loaded = False
        self.choices = [item for item in app.operations
                        if item.get('x-cy-category') not in ('', 'Workflow', 'Maintenance')]

    # ------------------------------------------------------------------- catalogue
    def refresh(self):
        try:
            outputs = self.app.jobs.run_sync('list_workflows', {'include_steps': True}, timeout=30)
            self.workflows = outputs.get('workflows', [])
            self.error = ''
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
        self.loaded = True

    def accept_dialog(self, purpose, result):
        if purpose == 'workflow:input_file':
            self.input_file = str(result[0] if isinstance(result, list) else result)
            self.input_folder = ''
            return True
        if purpose == 'workflow:input_folder':
            self.input_folder = str(result[0] if isinstance(result, list) else result)
            self.input_file = ''
            return True
        if purpose.startswith('step#'):
            index = self.editing_step
            if 0 <= index < len(self.document['steps']):
                parameters = self.document['steps'][index].setdefault('parameters', {})
                return self.editor.accept_path(purpose, result, parameters)
        return False

    # ------------------------------------------------------------------------ draw
    def draw(self):
        if not self.loaded:
            self.refresh()
        tr = self.app.tr
        available = imgui.get_content_region_avail()
        imgui.begin_child('##workflow-list', (max(230.0, available.x * 0.28), 0), True)
        imgui.text(tr('Saved workflows'))
        if imgui.small_button(tr('Refresh')):
            self.refresh()
        imgui.same_line()
        if imgui.small_button(tr('New')):
            self.document = {'name': 'New workflow', 'description': '', 'input_mode': 'each', 'steps': []}
            self.selected = -1
        imgui.separator()
        for index, item in enumerate(self.workflows):
            label = f"{item.get('name', '?')} ({item.get('stepCount', 0)})"
            if imgui.selectable(label, index == self.selected)[0]:
                self.selected = index
                self._load(item)
            if imgui.is_item_hovered() and item.get('description'):
                imgui.set_tooltip(item['description'])
        if self.error:
            widgets.status_line(self.error, error=True)
        imgui.end_child()

        imgui.same_line()
        imgui.begin_child('##workflow-editor', (0, 0), True)
        self._draw_editor()
        imgui.end_child()

    def _load(self, item):
        self.document = {'name': item.get('name', ''), 'description': item.get('description', ''),
                         'input_mode': item.get('input_mode', 'each'),
                         'steps': [dict(step) for step in item.get('steps', [])]}
        self.editing_step = -1

    def _draw_editor(self):
        tr = self.app.tr
        running = self.app.jobs.is_running('run_workflow')

        _, self.document['name'] = imgui.input_text(tr('Name'), self.document.get('name', ''))
        _, self.document['description'] = imgui.input_text_multiline(
            tr('Description'), self.document.get('description', ''), (-1, 44))

        imgui.separator()
        imgui.text(tr('Steps'))
        labels = [self.app.tr(item['name']) for item in self.choices]
        imgui.set_next_item_width(280.0)
        _, self.step_choice = imgui.combo('##step-choice', self.step_choice, labels)
        imgui.same_line()
        if imgui.button(tr('Add step')) and self.choices:
            self._add_step(self.choices[self.step_choice])

        removed = None
        for index, step in enumerate(self.document['steps']):
            imgui.push_id(index)
            operation = self.app.operation(step['operation'])
            title = f"{index + 1}. {self.app.tr(operation['name']) if operation else step['operation']}"
            opened = imgui.collapsing_header(title)
            # The controls sit on their own line, left aligned: placed at an absolute x near
            # the right edge they were clipped out of the child window and did not answer a
            # click, which the interaction test caught.
            imgui.indent()
            if imgui.small_button('^') and index > 0:
                self.document['steps'][index - 1], self.document['steps'][index] = (
                    self.document['steps'][index], self.document['steps'][index - 1])
            imgui.same_line()
            if imgui.small_button('v') and index < len(self.document['steps']) - 1:
                self.document['steps'][index + 1], self.document['steps'][index] = (
                    self.document['steps'][index], self.document['steps'][index + 1])
            imgui.same_line()
            if imgui.small_button(tr('Remove')):
                removed = index
            imgui.same_line()
            changed, enabled = imgui.checkbox(tr('Enabled'), bool(step.get('enabled', True)))
            if changed:
                step['enabled'] = enabled
            imgui.unindent()
            if opened and operation is not None:
                self.editing_step = index
                self._draw_step(index, step, operation)
            imgui.pop_id()
        if removed is not None:
            del self.document['steps'][removed]

        imgui.separator()
        imgui.text(tr('Input'))
        imgui.set_next_item_width(max(200.0, imgui.get_content_region_avail().x - 320.0))
        _, self.input_file = imgui.input_text(tr('File'), self.input_file)
        imgui.same_line()
        if imgui.button(tr('Browse') + '###wf-file'):
            self.app.dialogs.open_file('workflow:input_file', tr('Choose the input'),
                                       filters=widgets.ANY_FILTER)
        imgui.set_next_item_width(max(200.0, imgui.get_content_region_avail().x - 320.0))
        _, self.input_folder = imgui.input_text(tr('Folder'), self.input_folder)
        imgui.same_line()
        if imgui.button(tr('Browse') + '###wf-folder'):
            self.app.dialogs.select_folder('workflow:input_folder', tr('Choose a folder'))
        if self.input_folder:
            imgui.set_next_item_width(160.0)
            _, self.input_pattern = imgui.input_text(tr('Pattern'), self.input_pattern)
        # What a folder means belongs to the workflow: four photographs of one statue are one
        # subject, a folder of meshes is a batch. It is saved with the document.
        modes = ('each', 'together')
        labels = [tr('One run per file'), tr('All files together, as the views of one subject')]
        mode = self.document.get('input_mode', 'each')
        current = modes.index(mode) if mode in modes else 0
        imgui.set_next_item_width(max(200.0, imgui.get_content_region_avail().x - 320.0))
        changed, current = imgui.combo(tr('Files of the folder') + '###wf-input-mode', current, labels)
        widgets.remember_combo(tr('Files of the folder'))
        if changed:
            self.document['input_mode'] = modes[current]

        imgui.separator()
        imgui.begin_disabled(running or not self.document['steps'])
        if imgui.button(tr('Run the workflow')):
            self._run()
        imgui.same_line()
        if imgui.button(tr('Save')):
            self._save()
        imgui.end_disabled()
        if running:
            imgui.same_line()
            if imgui.button(tr('Cancel')):
                for job in self.app.jobs.running('run_workflow'):
                    self.app.jobs.cancel(job['jobId'])
        for job in self.app.jobs.running('run_workflow'):
            progress = job.get('progress') or {}
            imgui.progress_bar(float(progress.get('percent', 0.0)) / 100.0, (-1, 0),
                               self.app.jobs.progress_text(job))
        if self.message:
            widgets.status_line(self.message)
        # A refused submission or a failed run must be said here, where Run was clicked: the
        # scheduler once refused a workflow and this panel showed nothing at all.
        error = self.app.jobs.error
        if error:
            widgets.status_line(error, error=True)
        self.shown_error = error

    def _draw_step(self, index, step, operation):
        tr = self.app.tr
        imgui.indent()
        backends = operation.get('supportedBackends') or []
        if len(backends) > 1:
            current = step.get('backend') or backends[0]
            position = backends.index(current) if current in backends else 0
            changed, position = imgui.combo(tr('Backend'), position,
                                            [self.app.backend_label(item) for item in backends])
            if changed:
                step['backend'] = backends[position]
        elif backends:
            step['backend'] = backends[0]

        if index > 0:
            previous = [item['id'] for item in self.document['steps'][:index]]
            names = [tr('Previous step')] + previous
            current = step.get('input_from', '')
            position = names.index(current) if current in names else 0
            changed, position = imgui.combo(tr('Input from'), position, names)
            if changed:
                step['input_from'] = '' if position == 0 else names[position]
            source = self.app.operation(
                next((item['operation'] for item in self.document['steps']
                      if item['id'] == step.get('input_from')), '')) if step.get('input_from') else None
            if source is not None:
                fields = [''] + list((source.get('outputSchema') or {}).get('properties', {}))
                current = step.get('input_field', '')
                position = fields.index(current) if current in fields else 0
                changed, position = imgui.combo(tr('Output field'), position,
                                                [tr('Main output') if not item else item for item in fields])
                if changed:
                    step['input_field'] = fields[position]
            targets = [''] + list((operation.get('inputSchema') or {}).get('properties', {}))
            current = step.get('input_to', '')
            position = targets.index(current) if current in targets else 0
            changed, position = imgui.combo(tr('Receives it in'), position,
                                            [tr('Default input') if not item else item for item in targets])
            if changed:
                step['input_to'] = targets[position]

        self._draw_extra_inputs(index, step, operation)
        parameters = step.setdefault('parameters', {})
        self.editor.draw(operation, parameters, owner='step')
        imgui.unindent()

    def _draw_extra_inputs(self, index, step, operation):
        """Values taken from other earlier steps than the one feeding the main input."""
        tr = self.app.tr
        extra = step.setdefault('extra_inputs', [])
        if not imgui.tree_node(f"{tr('More inputs')} ({len(extra)})###extra-inputs"):
            return
        previous = [item['id'] for item in self.document['steps'][:index]]
        sources = ['@input'] + previous
        targets = list((operation.get('inputSchema') or {}).get('properties', {}))
        removed = None
        for position, item in enumerate(extra):
            imgui.push_id(f'extra{position}')
            current = item.get('from', '@input')
            chosen = sources.index(current) if current in sources else 0
            imgui.set_next_item_width(150.0)
            changed, chosen = imgui.combo(tr('From'), chosen,
                                          [tr('Workflow input') if name == '@input' else name
                                           for name in sources])
            if changed:
                item['from'] = sources[chosen]
                item['field'] = ''
            source = self.app.operation(next((entry['operation'] for entry in self.document['steps']
                                              if entry['id'] == item.get('from')), ''))
            if source is not None:
                fields = [''] + list((source.get('outputSchema') or {}).get('properties', {}))
                current = item.get('field', '')
                chosen = fields.index(current) if current in fields else 0
                imgui.same_line()
                imgui.set_next_item_width(170.0)
                changed, chosen = imgui.combo(tr('Output field'), chosen,
                                              [tr('Main output') if not name else name for name in fields])
                if changed:
                    item['field'] = fields[chosen]
            current = item.get('to', '')
            chosen = targets.index(current) if current in targets else 0
            imgui.same_line()
            imgui.set_next_item_width(170.0)
            changed, chosen = imgui.combo(tr('Receives it in'), chosen, targets or [''])
            if changed or not item.get('to'):
                item['to'] = targets[chosen] if targets else ''
            imgui.same_line()
            if imgui.small_button(tr('Remove')):
                removed = position
            imgui.pop_id()
        if removed is not None:
            del extra[removed]
        if imgui.small_button(tr('Add an input')):
            extra.append({'from': previous[-1] if previous else '@input', 'field': '', 'to': ''})
        imgui.tree_pop()

    def _add_step(self, operation):
        identifier = operation['id'][:6] + str(len(self.document['steps']) + 1)
        backends = operation.get('supportedBackends') or []
        self.document['steps'].append({
            'id': identifier, 'operation': operation['id'],
            'backend': backends[0] if backends else '', 'parameters': {},
            'input_from': '', 'input_field': '', 'input_to': '', 'extra_inputs': [],
            'enabled': True, 'continue_on_error': False})

    def _document(self):
        steps = []
        for step in self.document['steps']:
            operation = self.app.operation(step['operation'])
            parameters = dict(step.get('parameters') or {})
            if operation is not None:
                try:
                    parameters = widgets.coerce(operation, parameters)
                except ValueError as exc:
                    raise ValueError(f"{step['operation']}: {exc}") from exc
            steps.append({**step, 'parameters': parameters})
        return {'name': self.document.get('name') or 'Workflow',
                'description': self.document.get('description', ''),
                'input_mode': self.document.get('input_mode', 'each'), 'steps': steps}

    def _run(self):
        try:
            payload = {'workflow': self._document(), 'keep_intermediate': True, 'stop_on_error': True}
        except ValueError as exc:
            self.app.jobs.error = str(exc)
            return
        if self.input_folder:
            payload['input_folder'] = self.input_folder
            payload['input_pattern'] = self.input_pattern or '*'
        elif self.input_file:
            payload['input_file'] = self.input_file

        def finished(job):
            outputs = job.get('outputs') or {}
            produced = outputs.get('outputs') or []
            self.message = self.app.tr('Workflow finished') + f": {len(produced)} " + self.app.tr('output(s)')
            if produced and self.app.open_mesh:
                last = str(produced[-1])
                if Path(last).suffix.lower() in ('.glb', '.gltf', '.obj', '.ply', '.stl', '.off'):
                    self.app.open_mesh(last)

        self.message = ''
        self.app.jobs.submit('run_workflow', payload, callback=finished, label='run_workflow')

    def _save(self):
        try:
            document = self._document()
        except ValueError as exc:
            self.app.jobs.error = str(exc)
            return
        try:
            outputs = self.app.jobs.run_sync('save_workflow', {
                'name': document['name'], 'workflow': document, 'overwrite': True}, timeout=30)
            self.message = self.app.tr('Saved to') + ' ' + str(outputs.get('file', ''))
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self.app.jobs.error = str(exc)
