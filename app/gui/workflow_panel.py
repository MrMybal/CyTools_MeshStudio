"""The Workflows page: build a chain of operations, save it, run it on a file or a folder.

A workflow is the same document the CLI and MCP run; this panel only edits it and submits
``run_workflow``. Nothing is executed here, and the steps are the operations of the manifest,
so a workflow built in the interface runs identically from an AI client.
"""
from pathlib import Path

from imgui_bundle import imgui

import cyui
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
        self.search = ''
        self.footer_height = 0.0
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
        available = imgui.get_content_region_avail()
        with cyui.scoped_color(imgui.Col_.child_bg, cyui.palette().bg0):
            imgui.begin_child('##workflow-list', (max(cyui.dp(270.0), available.x * 0.28), 0),
                              imgui.ChildFlags_.borders | imgui.ChildFlags_.always_use_window_padding)
        self._draw_list()
        imgui.end_child()

        imgui.same_line()
        imgui.begin_child('##workflow-editor', (0, 0), imgui.ChildFlags_.borders
                          | imgui.ChildFlags_.always_use_window_padding)
        self._draw_editor()
        imgui.end_child()

    def _draw_list(self):
        tr = self.app.tr
        tools = imgui.get_frame_height() * 2 + cyui.dp(10.0)
        _, self.search = cyui.search_field('##workflow-search', self.search, tr('Search workflows'), -tools)
        imgui.same_line(0.0, cyui.dp(4.0))
        if cyui.icon_button(cyui.icon.add, tr('New workflow')):
            self.document = {'name': 'New workflow', 'description': '', 'input_mode': 'each', 'steps': []}
            self.selected = -1
        imgui.same_line(0.0, cyui.dp(2.0))
        if cyui.icon_button(cyui.icon.refresh, tr('Refresh')):
            self.refresh()
        cyui.space(6.0)
        cyui.overline(tr('SAVED WORKFLOWS'), cyui.palette().textFaint)
        needle = self.search.strip().casefold()
        shown = 0
        for index, item in enumerate(self.workflows):
            if needle and needle not in (item.get('name', '') + ' ' + item.get('description', '')).casefold():
                continue
            label = f"{item.get('name', '?')} ({item.get('stepCount', 0)})"
            if imgui.selectable(label, index == self.selected)[0]:
                self.selected = index
                self._load(item)
            # The list is narrow: the tooltip gives the whole name back with the description.
            cyui.tooltip((item.get('name', '') + '\n' + item.get('description', '')).strip())
            shown += 1
        if self.error:
            cyui.callout('error', self.error)
        elif not shown:
            cyui.empty_state(tr('No workflow found') if needle else tr('No workflow saved yet'),
                             tr('Change or clear the search.') if needle else
                             tr('Build one on the right, then save it.'), cyui.icon.link)

    def _load(self, item):
        self.document = {'name': item.get('name', ''), 'description': item.get('description', ''),
                         'input_mode': item.get('input_mode', 'each'),
                         'steps': [dict(step) for step in item.get('steps', [])]}
        self.editing_step = -1

    def _draw_editor(self):
        footer = max(self.footer_height, imgui.get_frame_height() + cyui.dp(16.0))
        imgui.begin_child('##workflow-body', (0, -footer))
        self._draw_document()
        imgui.end_child()
        start = imgui.get_cursor_pos_y()
        self._draw_actions()
        self.footer_height = imgui.get_cursor_pos_y() - start + imgui.get_style().item_spacing.y

    def _draw_document(self):
        tr = self.app.tr
        steps = self.document['steps']
        cyui.panel_header(self.document.get('name') or tr('New workflow'),
                          f"{len(steps)} {tr('step(s)')}")
        cyui.space(6.0)
        if cyui.begin_properties('##workflow-document'):
            cyui.property(tr('Name'))
            _, self.document['name'] = imgui.input_text('##workflow-name', self.document.get('name', ''))
            cyui.property(tr('Description'))
            _, self.document['description'] = imgui.input_text_multiline(
                '##workflow-description', self.document.get('description', ''), (-1.17549435e-38, cyui.dp(48.0)))
            cyui.end_properties()

        cyui.space(6.0)
        if cyui.begin_section(tr('Steps') + '###steps-section'):
            labels = [tr(item['name']) for item in self.choices]
            button = widgets.action('Add step', cyui.icon.add, tr)
            imgui.set_next_item_width(max(cyui.dp(160.0), imgui.get_content_region_avail().x
                                          - cyui.button_width(button) - cyui.dp(8.0)))
            _, self.step_choice = imgui.combo('##step-choice', self.step_choice, labels)
            cyui.tooltip(tr('The operation the new step runs'))
            imgui.same_line()
            if cyui.button(button) and self.choices:
                self._add_step(self.choices[self.step_choice])
            cyui.space(4.0)
            if not steps:
                cyui.callout('info', tr('No step yet: choose an operation above and press Add step.'))
            removed = None
            for index, step in enumerate(steps):
                imgui.push_id(index)
                operation = self.app.operation(step['operation'])
                title = f"{index + 1}. {tr(operation['name']) if operation else step['operation']}"
                opened = imgui.collapsing_header(title)
                # The controls sit on their own line, left aligned: placed at an absolute x near
                # the right edge they were clipped out of the child window and did not answer a
                # click, which the interaction test caught.
                imgui.indent(cyui.dp(4.0))
                if cyui.icon_button(cyui.icon.chevron_up, tr('Move up')) and index > 0:
                    steps[index - 1], steps[index] = steps[index], steps[index - 1]
                imgui.same_line(0.0, cyui.dp(2.0))
                if cyui.icon_button(cyui.icon.chevron_down, tr('Move down')) and index < len(steps) - 1:
                    steps[index + 1], steps[index] = steps[index], steps[index + 1]
                imgui.same_line(0.0, cyui.dp(2.0))
                if cyui.button(widgets.action('Remove', cyui.icon.trash, tr), 'ghost'):
                    removed = index
                imgui.same_line(0.0, cyui.dp(12.0))
                changed, enabled = cyui.toggle_switch(tr('Enabled') + '###enabled', bool(step.get('enabled', True)))
                if changed:
                    step['enabled'] = enabled
                if not step.get('enabled', True):
                    imgui.same_line()
                    cyui.badge(tr('SKIPPED'), 'warning')
                imgui.unindent(cyui.dp(4.0))
                if opened and operation is not None:
                    self.editing_step = index
                    self._draw_step(index, step, operation)
                cyui.space(2.0)
                imgui.pop_id()
            if removed is not None:
                del steps[removed]
            cyui.end_section()

        if cyui.begin_section(tr('Input') + '###input-section'):
            if cyui.begin_properties('##workflow-input'):
                cyui.property(tr('File'), tr('One file to run the workflow on.'))
                self._path('##wf-file', 'input_file', 'workflow:input_file', folder=False)
                cyui.property(tr('Folder'), tr('Every matching file of a folder, instead of one file.'))
                self._path('##wf-folder', 'input_folder', 'workflow:input_folder', folder=True)
                if self.input_folder:
                    cyui.property(tr('Pattern'))
                    _, self.input_pattern = imgui.input_text('##wf-pattern', self.input_pattern)
                # What a folder means belongs to the workflow: four photographs of one statue are
                # one subject, a folder of meshes is a batch. It is saved with the document.
                cyui.property(tr('Files of the folder'))
                modes = ('each', 'together')
                labels = [tr('One run per file'), tr('All files together, as the views of one subject')]
                mode = self.document.get('input_mode', 'each')
                current = modes.index(mode) if mode in modes else 0
                changed, current = imgui.combo('###wf-input-mode', current, labels)
                widgets.remember_combo(tr('Files of the folder'))
                if changed:
                    self.document['input_mode'] = modes[current]
                cyui.end_properties()
            cyui.end_section()

    def _path(self, identifier, attribute, purpose, folder):
        tr = self.app.tr
        value = getattr(self, attribute)
        imgui.set_next_item_width(max(cyui.dp(80.0), imgui.get_content_region_avail().x
                                      - imgui.get_frame_height() - cyui.dp(6.0)))
        changed, value = imgui.input_text_with_hint(identifier, tr('No folder chosen') if folder
                                                     else tr('No file chosen'), value)
        if changed:
            setattr(self, attribute, value)
        imgui.same_line(0.0, cyui.dp(4.0))
        if cyui.icon_button(cyui.icon.folder, tr('Browse')):
            if folder:
                self.app.dialogs.select_folder(purpose, tr('Choose a folder'))
            else:
                self.app.dialogs.open_file(purpose, tr('Choose the input'), filters=widgets.ANY_FILTER)

    def _draw_actions(self):
        tr = self.app.tr
        running = self.app.jobs.is_running('run_workflow')
        cyui.divider(2.0)
        imgui.begin_disabled(running or not self.document['steps'])
        if cyui.primary_button(widgets.action('Run the workflow', cyui.icon.play, tr)):
            self._run()
        imgui.same_line()
        if cyui.button(widgets.action('Save', cyui.icon.save, tr)):
            self._save()
        imgui.end_disabled()
        if running:
            imgui.same_line()
            if cyui.button(widgets.action('Cancel', cyui.icon.stop, tr)):
                for job in self.app.jobs.running('run_workflow'):
                    self.app.jobs.cancel(job['jobId'])
        for job in self.app.jobs.running('run_workflow'):
            widgets.progress(job, self.app.jobs)
        if self.message:
            cyui.callout('success', self.message)
        # A refused submission or a failed run must be said here, where Run was clicked: the
        # scheduler once refused a workflow and this panel showed nothing at all.
        error = self.app.jobs.error
        if error:
            cyui.callout('error', error)
        self.shown_error = error

    def _draw_step(self, index, step, operation):
        tr = self.app.tr
        imgui.indent(cyui.dp(4.0))
        backends = operation.get('supportedBackends') or []
        if cyui.begin_properties('##step-wiring'):
            if len(backends) > 1:
                cyui.property(tr('Backend'))
                current = step.get('backend') or backends[0]
                position = backends.index(current) if current in backends else 0
                changed, position = imgui.combo('##step-backend', position,
                                                [self.app.backend_label(item) for item in backends])
                if changed:
                    step['backend'] = backends[position]
            elif backends:
                step['backend'] = backends[0]

            if index > 0:
                previous = [item['id'] for item in self.document['steps'][:index]]
                names = [tr('Previous step')] + previous
                cyui.property(tr('Input from'), tr('The step whose output this one reads.'))
                current = step.get('input_from', '')
                position = names.index(current) if current in names else 0
                changed, position = imgui.combo('##input-from', position, names)
                if changed:
                    step['input_from'] = '' if position == 0 else names[position]
                source = self.app.operation(
                    next((item['operation'] for item in self.document['steps']
                          if item['id'] == step.get('input_from')), '')) if step.get('input_from') else None
                if source is not None:
                    fields = [''] + list((source.get('outputSchema') or {}).get('properties', {}))
                    cyui.property(tr('Output field'))
                    current = step.get('input_field', '')
                    position = fields.index(current) if current in fields else 0
                    changed, position = imgui.combo('##output-field', position,
                                                    [tr('Main output') if not item else item for item in fields])
                    if changed:
                        step['input_field'] = fields[position]
                targets = [''] + list((operation.get('inputSchema') or {}).get('properties', {}))
                cyui.property(tr('Receives it in'))
                current = step.get('input_to', '')
                position = targets.index(current) if current in targets else 0
                changed, position = imgui.combo('##receives', position,
                                                [tr('Default input') if not item else item for item in targets])
                if changed:
                    step['input_to'] = targets[position]
            cyui.end_properties()

        self._draw_extra_inputs(index, step, operation)
        parameters = step.setdefault('parameters', {})
        self.editor.draw(operation, parameters, owner='step')
        imgui.unindent(cyui.dp(4.0))

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
            imgui.set_next_item_width(cyui.dp(150.0))
            changed, chosen = imgui.combo('##from', chosen,
                                          [tr('Workflow input') if name == '@input' else name
                                           for name in sources])
            cyui.tooltip(tr('From'))
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
                imgui.set_next_item_width(cyui.dp(170.0))
                changed, chosen = imgui.combo('##field', chosen,
                                              [tr('Main output') if not name else name for name in fields])
                cyui.tooltip(tr('Output field'))
                if changed:
                    item['field'] = fields[chosen]
            current = item.get('to', '')
            chosen = targets.index(current) if current in targets else 0
            imgui.same_line()
            cyui.text_faint('->')
            imgui.same_line()
            imgui.set_next_item_width(cyui.dp(170.0))
            changed, chosen = imgui.combo('##to', chosen, targets or [''])
            cyui.tooltip(tr('Receives it in'))
            if changed or not item.get('to'):
                item['to'] = targets[chosen] if targets else ''
            imgui.same_line()
            if cyui.icon_button(cyui.icon.close, tr('Remove')):
                removed = position
            imgui.pop_id()
        if removed is not None:
            del extra[removed]
        if cyui.button(widgets.action('Add an input', cyui.icon.add, tr), 'ghost'):
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
        self.app.jobs.submit('run_workflow', payload, callback=finished, label=self.app.tr('Run the workflow'))

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
            cyui.notify(self.app.tr('Workflow saved'), 'success')
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self.app.jobs.error = str(exc)
