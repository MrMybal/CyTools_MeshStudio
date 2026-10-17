"""The Tools page: every operation of the manifest, grouped by what it does.

The list on the left is built from the manifest, so an operation added there appears here
with real controls and no UI code of its own; a search narrows it. The form on the right is
the parameter editor, plus the backend chooser when an operation accepts several. The action
bar under the form stays in view however long the form is: Run, Reset, Cancel, live progress
and what went wrong. What the job produced is shown as a card at the end of the form.
"""
from pathlib import Path

from imgui_bundle import imgui

import cyui
from gui import widgets

CATEGORY_ORDER = ('Reconstruction', 'Views', 'Topology', 'UV', 'Texturing',
                  'Editing', 'Inspection', 'Rigging', 'Motion', 'Maintenance')

MESH_RESULT_FIELDS = ('material_mesh_file', 'rigged_mesh', 'mesh_file', 'mesh', 'file',
                      'preview_file', 'preview')
IMAGE_RESULT_FIELDS = ('contact_sheet', 'thumbnail', 'preview', 'base_color_file')
STATE_TONES = {'Completed': 'success', 'Failed': 'error', 'Cancelled': 'warning'}


class ToolsPanel:
    def __init__(self, app):
        self.app = app
        self.editor = widgets.ParameterEditor(app.dialogs, app.tr)
        self.values = {}
        self.selected = ''
        self.backend = {}
        self.drawn = {}
        self.result = None
        self.result_operation = ''
        self.search = ''
        self.footer_height = 0.0
        operations = [item for item in app.operations
                      if item.get('x-cy-category') not in ('', 'Workflow')]
        self.by_category = {}
        for item in operations:
            self.by_category.setdefault(item.get('x-cy-category') or 'Other', []).append(item)
        self.categories = [name for name in CATEGORY_ORDER if name in self.by_category]
        self.categories += [name for name in self.by_category if name not in self.categories]
        if self.categories:
            self.selected = self.by_category[self.categories[0]][0]['id']

    # --------------------------------------------------------------------- helpers
    def operation(self, operation_id=''):
        return self.app.operation(operation_id or self.selected)

    def accept_dialog(self, purpose, result):
        operation = self.operation()
        if operation and purpose.startswith(operation['id'] + '#'):
            return self.editor.accept_path(purpose, result, self.values.setdefault(operation['id'], {}))
        return False

    def running(self):
        operation = self.operation()
        return self.app.jobs.is_running(operation['id']) if operation else False

    def _matches(self, item):
        if not self.search.strip():
            return True
        needle = self.search.strip().casefold()
        tr = self.app.tr
        return any(needle in str(text).casefold() for text in
                   (tr(item['name']), item['id'], tr(item.get('description', '')), item.get('name', '')))

    # ------------------------------------------------------------------------ draw
    def draw(self):
        available = imgui.get_content_region_avail()
        width = max(cyui.dp(250.0), available.x * 0.27)
        with cyui.scoped_color(imgui.Col_.child_bg, cyui.palette().bg0):
            imgui.begin_child('##tool-list', (width, 0), imgui.ChildFlags_.borders
                              | imgui.ChildFlags_.always_use_window_padding)
        self._draw_list()
        imgui.end_child()

        imgui.same_line()
        imgui.begin_child('##tool-form', (0, 0), imgui.ChildFlags_.borders
                          | imgui.ChildFlags_.always_use_window_padding)
        operation = self.operation()
        if operation is None:
            cyui.empty_state(self.app.tr('No operation available.'), '', cyui.icon.settings)
        else:
            self._draw_operation(operation)
        imgui.end_child()

    def _draw_list(self):
        tr = self.app.tr
        _, self.search = cyui.search_field('##tool-search', self.search, tr('Search operations'), -1.0)
        cyui.space(4.0)
        shown = 0
        for category in self.categories:
            items = [item for item in self.by_category[category] if self._matches(item)]
            if not items:
                continue
            cyui.space(4.0)
            cyui.overline(tr(category).upper(), cyui.palette().textFaint)
            for item in items:
                selected = item['id'] == self.selected
                running = self.app.jobs.is_running(item['id'])
                if imgui.selectable(tr(item['name']), selected)[0]:
                    self.selected = item['id']
                    self.result = None
                cyui.tooltip((tr(item['name']) + '\n' + tr(item.get('description', ''))).strip())
                if running:
                    imgui.same_line()
                    cyui.status_dot(cyui.palette().accent, tr('Running'))
                shown += 1
        if not shown:
            cyui.empty_state(tr('No operation matches'), tr('Change or clear the search.'), cyui.icon.search)

    def _draw_operation(self, operation):
        tr = self.app.tr
        # Frames in which this form was really drawn: the form test reads this, because a
        # report written by a run that showed another tab proves nothing.
        self.drawn[operation['id']] = self.drawn.get(operation['id'], 0) + 1
        backends = operation.get('supportedBackends') or []
        default_backend = self.backend.get(operation['id'], backends[0] if backends else '')

        footer = max(self.footer_height, imgui.get_frame_height() + cyui.dp(16.0))
        imgui.begin_child('##tool-form-body', (0, -footer))
        cyui.panel_header(tr(operation['name']),
                          self.app.backend_label(default_backend) if default_backend else '')
        cyui.badge(tr(operation.get('x-cy-category') or 'Other').upper(), 'accent')
        origin = operation.get('x-cy-origin') or {}
        if origin.get('tool'):
            imgui.same_line()
            cyui.badge(origin['tool'].upper())
            cyui.tooltip(tr('Ported from') + ' ' + origin['tool'])
        cyui.space(4.0)
        imgui.push_text_wrap_pos(0.0)
        cyui.text_dim(tr(operation.get('description', '')))
        imgui.pop_text_wrap_pos()
        cyui.space(6.0)

        backend_id = self._draw_backends(operation)
        readiness = self.app.readiness(operation, backend_id)
        if readiness:
            cyui.callout('warning', readiness)
            cyui.space(4.0)

        values = self.values.setdefault(operation['id'], {})
        imgui.begin_disabled(self.running())
        self.editor.draw(operation, values)
        imgui.end_disabled()
        if self.result and self.result_operation == operation['id']:
            cyui.space(8.0)
            self._draw_result(operation)
        imgui.end_child()

        start = imgui.get_cursor_pos_y()
        self._draw_actions(operation, values, backend_id, readiness)
        self.footer_height = imgui.get_cursor_pos_y() - start + imgui.get_style().item_spacing.y

    def _draw_actions(self, operation, values, backend_id, readiness):
        tr = self.app.tr
        cyui.divider(2.0)
        busy = self.running() or self.app.dialogs.busy
        imgui.begin_disabled(busy or bool(readiness))
        if cyui.primary_button(widgets.action('Run', cyui.icon.play, tr)):
            self._submit(operation, values, backend_id)
        imgui.end_disabled()
        imgui.same_line()
        if cyui.button(widgets.action('Reset', cyui.icon.undo, tr), 'ghost'):
            self.values[operation['id']] = {}
        cyui.tooltip(tr('Every parameter back to its default'))
        running = self.app.jobs.running(operation['id'])
        if running:
            imgui.same_line()
            if cyui.button(widgets.action('Cancel', cyui.icon.stop, tr)):
                for job in running:
                    self.app.jobs.cancel(job['jobId'])
        for job in running:
            widgets.progress(job, self.app.jobs)
        if self.app.jobs.error:
            cyui.callout('error', self.app.jobs.error)

    def _draw_backends(self, operation):
        tr = self.app.tr
        backends = operation.get('supportedBackends') or []
        if len(backends) <= 1:
            # One engine, no choice to offer: its name is in the header, so the user can still
            # tell that this operation is, say, LocalMesh.
            return backends[0] if backends else ''
        current = self.backend.get(operation['id'], backends[0])
        index = backends.index(current) if current in backends else 0
        labels = [self.app.backend_label(item) for item in backends]
        if cyui.begin_properties('##backend-choice'):
            cyui.property(tr('Backend'), tr('The engine that runs this operation; each has its own models.'))
            changed, index = imgui.combo('##backend', index, labels)
            widgets.remember_combo(tr('Backend'))
            if changed:
                self.backend[operation['id']] = backends[index]
            cyui.end_properties()
        return backends[index]

    def _submit(self, operation, values, backend_id):
        try:
            payload = widgets.coerce(operation, values)
        except ValueError as exc:
            self.app.jobs.error = str(exc)
            return

        def finished(job):
            self.result = job
            self.result_operation = operation['id']
            outputs = job.get('outputs') or {}
            path = self._mesh_of(outputs)
            if path and self.app.open_mesh:
                self.app.open_mesh(path)

        self.result = None
        self.app.jobs.submit(operation['id'], payload, callback=finished,
                             label=self.app.tr(operation['name']), backend_id=backend_id)

    @staticmethod
    def _mesh_of(outputs):
        for field in MESH_RESULT_FIELDS:
            value = outputs.get(field)
            if isinstance(value, str) and value and Path(value).suffix.lower() in (
                    '.glb', '.gltf', '.obj', '.ply', '.stl', '.off'):
                return value
        return ''

    def _draw_result(self, operation):
        tr = self.app.tr
        job = self.result
        state = job.get('state', '')
        tone = STATE_TONES.get(state, 'info')
        if cyui.begin_card('##result', tr('Result'), 0.0, 'error' if state == 'Failed' else 'neutral'):
            cyui.badge(tr(state).upper(), tone)
            if state == 'Failed':
                error = job.get('error') or {}
                cyui.space(2.0)
                cyui.callout('error', f"{error.get('code', '')}: {error.get('message', '')}")
            else:
                outputs = job.get('outputs') or {}
                mesh = self._mesh_of(outputs)
                imgui.same_line()
                if mesh:
                    if cyui.button(widgets.action('Open in the 3D view', cyui.icon.view, tr)):
                        self.app.open_mesh(mesh)
                    imgui.same_line()
                    if cyui.button(widgets.action('Open the folder', cyui.icon.folder, tr), 'ghost'):
                        self.app.open_folder(Path(mesh).parent)
                elif outputs:
                    first = next((value for value in outputs.values()
                                  if isinstance(value, str) and Path(value).parent.is_dir()), '')
                    if first and cyui.button(widgets.action('Open the folder', cyui.icon.folder, tr), 'ghost'):
                        self.app.open_folder(Path(first).parent)
                cyui.space(4.0)
                if outputs and cyui.begin_properties('##outputs'):
                    for key, value in outputs.items():
                        cyui.property(key)
                        if isinstance(value, (list, dict)):
                            cyui.text_faint(f'{type(value).__name__} ({len(value)})')
                            cyui.tooltip(str(value)[:1500])
                        else:
                            text = str(value)
                            imgui.text_unformatted(text if len(text) < 90 else '...' + text[-86:])
                            cyui.tooltip(text)
                    cyui.end_properties()
                notes = outputs.get('notes') or outputs.get('warnings') or []
                for note in notes if isinstance(notes, list) else []:
                    cyui.space(2.0)
                    cyui.callout('info', str(note)[:300])
        cyui.end_card()
