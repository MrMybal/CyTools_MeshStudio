"""The Tools tab: every operation of the manifest, grouped by what it does.

The list on the left is built from the manifest, so an operation added there appears here
with real controls and no UI code of its own. The form on the right is the parameter editor,
plus the backend chooser when an operation accepts several, the run and cancel buttons, live
progress, and what the job produced.
"""
from pathlib import Path

from imgui_bundle import imgui

from gui import widgets

CATEGORY_ORDER = ('Reconstruction', 'Views', 'Topology', 'UV', 'Texturing',
                  'Editing', 'Inspection', 'Rigging', 'Motion', 'Maintenance')

MESH_RESULT_FIELDS = ('material_mesh_file', 'rigged_mesh', 'mesh_file', 'mesh', 'file',
                      'preview_file', 'preview')
IMAGE_RESULT_FIELDS = ('contact_sheet', 'thumbnail', 'preview', 'base_color_file')


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

    # ------------------------------------------------------------------------ draw
    def draw(self):
        tr = self.app.tr
        available = imgui.get_content_region_avail()
        imgui.begin_child('##tool-list', (max(210.0, available.x * 0.26), 0), True)
        for category in self.categories:
            if imgui.collapsing_header(tr(category), imgui.TreeNodeFlags_.default_open):
                for item in self.by_category[category]:
                    selected = item['id'] == self.selected
                    if imgui.selectable(tr(item['name']), selected)[0]:
                        self.selected = item['id']
                        self.result = None
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(tr(item.get('description', '')))
        imgui.end_child()

        imgui.same_line()
        imgui.begin_child('##tool-form', (0, 0), True)
        operation = self.operation()
        if operation is None:
            imgui.text_wrapped(tr('No operation available.'))
        else:
            self._draw_operation(operation)
        imgui.end_child()

    def _draw_operation(self, operation):
        tr = self.app.tr
        # Frames in which this form was really drawn: the form test reads this, because a
        # report written by a run that showed another tab proves nothing.
        self.drawn[operation['id']] = self.drawn.get(operation['id'], 0) + 1
        imgui.text(tr(operation['name']))
        imgui.text_wrapped(tr(operation.get('description', '')))
        origin = operation.get('x-cy-origin') or {}
        if origin.get('tool'):
            imgui.text_disabled(tr('Ported from') + ' ' + origin['tool'])
        imgui.separator()

        backend_id = self._draw_backends(operation)
        readiness = self.app.readiness(operation, backend_id)
        if readiness:
            widgets.status_line(readiness, error=True)
            imgui.separator()

        values = self.values.setdefault(operation['id'], {})
        busy = self.running() or self.app.dialogs.busy
        imgui.begin_disabled(self.running())
        self.editor.draw(operation, values)
        imgui.end_disabled()

        imgui.separator()
        imgui.begin_disabled(busy or bool(readiness))
        if imgui.button(tr('Run')):
            self._submit(operation, values, backend_id)
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button(tr('Reset')):
            self.values[operation['id']] = {}
        running = self.app.jobs.running(operation['id'])
        if running:
            imgui.same_line()
            if imgui.button(tr('Cancel')):
                for job in running:
                    self.app.jobs.cancel(job['jobId'])

        for job in running:
            progress = job.get('progress') or {}
            imgui.progress_bar(float(progress.get('percent', 0.0)) / 100.0, (-1, 0),
                               self.app.jobs.progress_text(job))
        if self.app.jobs.error:
            widgets.status_line(self.app.jobs.error, error=True)
        if self.result and self.result_operation == operation['id']:
            self._draw_result(operation)

    def _draw_backends(self, operation):
        tr = self.app.tr
        backends = operation.get('supportedBackends') or []
        if len(backends) <= 1:
            # One engine, no choice to offer — but the name must still be visible, otherwise
            # the user cannot tell that this operation is, say, LocalMesh.
            if backends:
                imgui.text_disabled(f"{tr('Backend')}: {self.app.backend_label(backends[0])}")
            return backends[0] if backends else ''
        current = self.backend.get(operation['id'], backends[0])
        index = backends.index(current) if current in backends else 0
        labels = [self.app.backend_label(item) for item in backends]
        changed, index = imgui.combo(tr('Backend'), index, labels)
        if changed:
            self.backend[operation['id']] = backends[index]
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
                             label=operation['name'], backend_id=backend_id)

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
        imgui.separator()
        imgui.text(tr('Result') + ': ' + job.get('state', ''))
        if job.get('state') == 'Failed':
            error = job.get('error') or {}
            widgets.status_line(f"{error.get('code', '')}: {error.get('message', '')}", error=True)
            return
        outputs = job.get('outputs') or {}
        mesh = self._mesh_of(outputs)
        if mesh:
            if imgui.button(tr('Open in the 3D view')):
                self.app.open_mesh(mesh)
            imgui.same_line()
            if imgui.button(tr('Open the folder')):
                self.app.open_folder(Path(mesh).parent)
        elif outputs:
            first = next((value for value in outputs.values()
                          if isinstance(value, str) and Path(value).parent.is_dir()), '')
            if first and imgui.button(tr('Open the folder')):
                self.app.open_folder(Path(first).parent)

        if imgui.begin_table('##outputs', 2, imgui.TableFlags_.borders_inner_h
                             | imgui.TableFlags_.row_bg | imgui.TableFlags_.sizing_stretch_prop):
            imgui.table_setup_column(tr('Output'), imgui.TableColumnFlags_.width_fixed, 190.0)
            imgui.table_setup_column(tr('Value'))
            for key, value in outputs.items():
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text(key)
                imgui.table_next_column()
                if isinstance(value, (list, dict)):
                    imgui.text_disabled(f'{type(value).__name__} ({len(value)})')
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(str(value)[:1500])
                else:
                    text = str(value)
                    imgui.text_wrapped(text if len(text) < 90 else '...' + text[-86:])
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(text)
            imgui.end_table()
        notes = outputs.get('notes') or outputs.get('warnings') or []
        for note in notes if isinstance(notes, list) else []:
            imgui.bullet_text(str(note)[:300])
