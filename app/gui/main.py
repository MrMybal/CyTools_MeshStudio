"""CyTools_MeshStudio interface: tools, workflows, 3D view, installation and updates.

One Core runtime is created here and shared by every tab. The façade in ui_common adds the
3D view, the application log, the advanced operations and the Options tabs, and owns the
language, the theme and the licences. Heavy work is always a job: this process never loads a
model and never schedules anything itself.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from installation_ui import configure as configure_storage  # noqa: E402

configure_storage()

from imgui_bundle import hello_imgui, imgui as native  # noqa: E402
import ui_common  # noqa: E402
from ui_common import imgui, run, tr, configure_generation, preferences  # noqa: E402
from cytools_core import load_manifest  # noqa: E402
from tool import create_runtime  # noqa: E402
from meshstudio import paths  # noqa: E402
from meshstudio.engines import registry as engines  # noqa: E402
from meshstudio.backends import registry as backends  # noqa: E402
from gui.jobs import Jobs  # noqa: E402
from gui.widgets import Dialogs  # noqa: E402
from gui.tools_panel import ToolsPanel  # noqa: E402
from gui.workflow_panel import WorkflowPanel  # noqa: E402
from gui.models_panel import ModelsPanel  # noqa: E402
from gui.updates_panel import UpdatesPanel  # noqa: E402

TABS = ('Tools', 'Workflows', 'Installation', 'Updates')


class App:
    def __init__(self, runtime, actor, session, manifest):
        self.runtime, self.actor, self.session = runtime, actor, session
        self.manifest = manifest
        self.operations = list(manifest['operations'])
        self._by_id = {item['id']: item for item in self.operations}
        self.jobs = Jobs(runtime, actor, session)
        self.dialogs = Dialogs()
        self.data = paths.DATA
        self.tr = tr
        self.frames = 0
        self.requested_tab = None
        self._engine_status = None
        self.tools = ToolsPanel(self)
        self.workflows = WorkflowPanel(self)
        self.models = ModelsPanel(self)
        self.updates = UpdatesPanel(self)

    # ------------------------------------------------------------------- services
    def operation(self, operation_id):
        return self._by_id.get(operation_id)

    def backend_label(self, backend_id):
        try:
            return backends.get(backend_id).label
        except Exception:  # noqa: BLE001
            return backend_id

    def engine_status(self):
        if self._engine_status is None:
            try:
                self._engine_status = engines.status_all()
            except Exception:  # noqa: BLE001
                self._engine_status = {}
        return self._engine_status

    def readiness(self, operation, backend_id):
        """Why this operation cannot run right now, in one sentence, or an empty string."""
        if not backend_id:
            return ''
        try:
            backend = backends.get(backend_id)
        except Exception:  # noqa: BLE001
            return ''
        status = self.engine_status().get(backend.engine) or {}
        if not backend.worker_script().is_file():
            return (self.tr('This backend is not available in this build yet') +
                    f' ({backend.worker}).')
        if status and not status.get('installed'):
            return (self.tr('The engine') + f' "{backend.engine}" ' +
                    self.tr('is not installed. Open the Installation tab.'))
        return ''

    def open_folder(self, folder):
        try:
            if sys.platform == 'win32':
                os.startfile(str(folder))
            else:
                subprocess.Popen(['xdg-open', str(folder)])
        except OSError:
            pass

    def open_mesh(self, path):
        """Show a produced mesh in the façade's 3D view."""
        panel = getattr(ui_common, '_mesh_panel', None)
        if panel is None:
            return False
        try:
            panel.open(str(path))
            return True
        except Exception:  # noqa: BLE001
            return False

    def select_tab(self, name):
        self.requested_tab = name

    # ------------------------------------------------------------------------ draw
    def draw(self):
        self.frames += 1
        self.jobs.poll()
        answered = self.dialogs.poll()
        if answered:
            purpose, result = answered
            for panel in (self.models, self.updates, self.tools, self.workflows):
                if panel.accept_dialog(purpose, result):
                    break

        if native.begin_tab_bar('###meshstudio'):
            for name in TABS:
                flags = 0
                if self.requested_tab == name:
                    flags = native.TabItemFlags_.set_selected
                    self.requested_tab = None
                opened, _ = native.begin_tab_item(ui_common.label(name), None, flags)
                if opened:
                    if name == 'Tools':
                        self.tools.draw()
                    elif name == 'Workflows':
                        self.workflows.draw()
                    elif name == 'Installation':
                        self.models.draw()
                    else:
                        self.updates.draw()
                    native.end_tab_item()
            # Tabs owned by the façade: 3D view, log, advanced operations, options.
            panel = getattr(ui_common, '_mesh_panel', None)
            if panel is not None:
                panel.tab()
            ui_common.journal.draw_tab()
            advanced = getattr(ui_common, '_advanced_panel', None)
            if advanced is not None:
                advanced.draw_tab()
            ui_common.options_tab()
            native.end_tab_bar()

    def close(self):
        try:
            self.jobs.cancel_all()
        except Exception:  # noqa: BLE001
            pass


def main():
    paths.ensure_data_layout()
    manifest = load_manifest(APP / 'CyTool.json')
    from branding import configure as configure_branding
    configure_branding('Cyberalien.CyTools_MeshStudio')
    runner = hello_imgui.RunnerParams()
    runner.app_window_params.window_title = 'CyTools_MeshStudio'
    runner.app_window_params.window_geometry.size = (1280, 840)
    runner.ini_filename = str(paths.SETTINGS / 'imgui.ini')

    smoke = '--smoke-test' in sys.argv
    test_tab = next((argument.split('=', 1)[1] for argument in sys.argv
                     if argument.startswith('--ui-test-tab=')), '')
    # --ui-run=<operation>=<file> submits one real job through the panel's own Run path,
    # so the evidence covers submission and not only rendering.
    demand = next((argument.split('=', 1)[1] for argument in sys.argv
                   if argument.startswith('--ui-run=')), '')
    # --ui-test-operation=<id> draws one operation's form for a few frames and reports.
    # Every form must be exercised, not only the one the panel happens to select first.
    one_operation = next((argument.split('=', 1)[1] for argument in sys.argv
                          if argument.startswith('--ui-test-operation=')), '')

    interactions = '--ui-test-interactions' in sys.argv
    recorder = None

    with create_runtime(paths.JOBS) as runtime:
        # The interface installs engines and weights and checks releases, so its client needs
        # the network permission those operations declare; without it every such button was
        # refused with "Client lacks operation permissions".
        actor = runtime.authenticate(runtime.create_client('ImGui', ['filesystemExternal', 'network'])['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']
        app = App(runtime, actor, session, manifest)

        if interactions:
            from gui import interaction_tests
            recorder = interaction_tests.Recorder(paths.DATA)

            def register_tests():
                engine = hello_imgui.get_imgui_test_engine()
                io = native.test_engine.get_io(engine)
                io.config_run_speed = native.test_engine.TestRunSpeed.fast
                interaction_tests.register(app, runner, recorder)
            runner.callbacks.register_tests = register_tests
            runner.use_imgui_test_engine = True

        submitted = {'done': False, 'job': None}

        def prefill(operation_id):
            """Give the object lists one entry, so their sub-form is drawn too.

            An empty list draws only its header: the fields of an entry — where a nested file
            picker and nested enums live — would never be exercised otherwise.
            """
            operation = app.operation(operation_id)
            if operation is None:
                return
            values = app.tools.values.setdefault(operation_id, {})
            for field, schema in (operation['inputSchema'].get('properties') or {}).items():
                items = schema.get('items') or {}
                if schema.get('type') != 'array' or items.get('type') != 'object':
                    continue
                properties = items.get('properties') or {}
                from gui import widgets as widget_module
                values[field] = [{key: widget_module.default_for(value)
                                  for key, value in properties.items()}]

        def gui():
            if recorder is not None:
                app.draw()
                if recorder.done:
                    summary = recorder.save()
                    print(json.dumps({'passed': summary['passed'], 'failed': summary['failed']}))
                    runner.app_shall_exit = True
                return
            if one_operation:
                app.tools.selected = one_operation
                # The 3D viewer reopens the last mesh at start and selects its own tab; the
                # form is only drawn while the Tools tab is the selected one.
                app.select_tab('Tools')
                if app.frames == 0:
                    prefill(one_operation)
            app.draw()
            if one_operation and app.frames >= 8:
                form_frames = app.tools.drawn.get(one_operation, 0)
                reports = paths.REPORTS
                reports.mkdir(parents=True, exist_ok=True)
                (reports / 'ui-operation.json').write_text(json.dumps(
                    {'operation': one_operation, 'frames': app.frames,
                     'formFrames': form_frames, 'drawn': form_frames >= 3}),
                    encoding='utf-8')
                runner.app_shall_exit = True
                return
            if test_tab and app.frames == 2:
                app.select_tab(test_tab)
            if demand and app.frames == 3 and not submitted['done']:
                operation_id, _, argument = demand.partition('=')
                operation = app.operation(operation_id)
                if operation is not None:
                    app.tools.selected = operation_id
                    field = next((name for name, item in
                                  (operation['inputSchema'].get('properties') or {}).items()
                                  if item.get('x-cy-kind') in ('File', 'Image', 'Video')), '')
                    values = app.tools.values.setdefault(operation_id, {})
                    if field and argument:
                        values[field] = argument
                    backends_of = operation.get('supportedBackends') or ['']
                    app.tools._submit(operation, values, backends_of[0])
                    submitted['done'] = True
            if demand and submitted['done']:
                job = app.tools.result
                if job is not None and job.get('state') in ('Completed', 'Failed', 'Cancelled'):
                    reports = paths.REPORTS
                    reports.mkdir(parents=True, exist_ok=True)
                    (reports / 'ui-run.json').write_text(json.dumps(
                        {'operation': demand.split('=', 1)[0], 'state': job['state'],
                         'frames': app.frames, 'outputs': job.get('outputs'),
                         'error': job.get('error')}, indent=2, default=str), encoding='utf-8')
                    runner.app_shall_exit = True
                elif app.frames > 1800:
                    runner.app_shall_exit = True
                return
            if (smoke or test_tab) and app.frames > 12:
                reports = paths.REPORTS
                reports.mkdir(parents=True, exist_ok=True)
                (reports / f"ui-smoke-{(test_tab or 'tools').lower()}.json").write_text(
                    json.dumps({'frames': app.frames, 'tab': test_tab or 'Tools',
                                'operations': len(app.operations),
                                'language': preferences.values.get('language', 'en')}),
                    encoding='utf-8')
                runner.app_shall_exit = True

        def capture_config():
            operation = app.tools.operation()
            if operation is None:
                return {'operationId': '', 'parameters': {}}
            from gui import widgets as widget_module
            values = app.tools.values.get(operation['id'], {})
            try:
                parameters = widget_module.coerce(operation, values)
            except ValueError:
                parameters = {}
            return {'operationId': operation['id'], 'parameters': parameters,
                    'backendId': app.tools.backend.get(operation['id'], '')}

        def restore_config(value):
            operation_id = value.get('operationId', '')
            if operation_id and app.operation(operation_id):
                app.tools.selected = operation_id
                app.tools.values[operation_id] = dict(value.get('parameters') or {})
                if value.get('backendId'):
                    app.tools.backend[operation_id] = value['backendId']
                app.select_tab('Tools')

        configure_generation(runtime, capture_config, restore_config)
        runner.callbacks.show_gui = gui
        try:
            run(runner)
        finally:
            app.close()
            try:
                runtime.services.pool.stop_all()
            except Exception:  # noqa: BLE001
                pass
        if smoke or test_tab or one_operation:
            try:
                from standalone_log import save_screenshot
                pixels = hello_imgui.final_app_window_screenshot()
                if pixels.size:
                    name = one_operation or test_tab or 'tools'
                    save_screenshot(paths.REPORTS / f"ui-{name.lower()}-"
                                                    f"{preferences.values.get('language', 'en')}.png", pixels)
            except Exception as exc:  # noqa: BLE001
                (paths.REPORTS / 'ui-screenshot-error.txt').write_text(str(exc), encoding='utf-8')


if __name__ == '__main__':
    main()
