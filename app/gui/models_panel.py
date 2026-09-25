"""The Installation tab: engine environments and the model catalogue.

Everything shown here comes from ``diagnose`` and ``list_models``, so the interface reports
the same state as the CLI and MCP. Installing an engine is a job like any other: it streams
its progress and can be cancelled.
"""
from imgui_bundle import imgui

from gui import widgets

STATE_COLOURS = {
    'Installed': (0.45, 0.85, 0.55, 1.0),
    'Partial': (0.95, 0.75, 0.35, 1.0),
    'NotInstalled': (0.85, 0.45, 0.42, 1.0),
}


class ModelsPanel:
    def __init__(self, app):
        self.app = app
        self.engines = {}
        self.backends = []
        self.models = []
        self.warnings = []
        self.loaded = False
        self.error = ''
        self.device = 'auto'
        self.repair = False
        self.filter_family = 0
        self.families = ['(all)']

    def refresh(self):
        try:
            report = self.app.jobs.run_sync('diagnose', {}, timeout=60)
            self.engines = report.get('engines', {})
            self.backends = report.get('backends', [])
            self.models = report.get('models', [])
            self.warnings = report.get('warnings', [])
            families = sorted({item.get('family', '') for item in self.models if item.get('family')})
            self.families = ['(all)'] + families
            self.error = ''
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
        self.loaded = True

    def draw(self):
        if not self.loaded:
            self.refresh()
        tr = self.app.tr
        if imgui.button(tr('Refresh')):
            self.refresh()
        imgui.same_line()
        imgui.text_disabled(tr('State comes from diagnose, the same report the CLI prints.'))
        if self.error:
            widgets.status_line(self.error, error=True)

        if imgui.collapsing_header(tr('Engines'), imgui.TreeNodeFlags_.default_open):
            self._draw_engines()
        if imgui.collapsing_header(tr('Backends')):
            self._draw_backends()
        if imgui.collapsing_header(tr('Models'), imgui.TreeNodeFlags_.default_open):
            self._draw_models()

    # --------------------------------------------------------------------- engines
    def _draw_engines(self):
        tr = self.app.tr
        installing = self.app.jobs.running('install_engine')
        devices = ['auto', 'cuda', 'cpu']
        imgui.set_next_item_width(120.0)
        index = devices.index(self.device) if self.device in devices else 0
        changed, index = imgui.combo(tr('Device'), index, devices)
        if changed:
            self.device = devices[index]
        imgui.same_line()
        _, self.repair = imgui.checkbox(tr('Reinstall even if installed'), self.repair)

        if imgui.begin_table('##engines', 5, imgui.TableFlags_.borders | imgui.TableFlags_.row_bg
                             | imgui.TableFlags_.sizing_stretch_prop):
            for title, width in ((tr('Engine'), 150.0), (tr('State'), 110.0), (tr('Runtime'), 0.0),
                                 (tr('Size'), 90.0), ('', 130.0)):
                if width:
                    imgui.table_setup_column(title, imgui.TableColumnFlags_.width_fixed, width)
                else:
                    imgui.table_setup_column(title)
            imgui.table_headers_row()
            for name, info in self.engines.items():
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text(name)
                if imgui.is_item_hovered():
                    imgui.set_tooltip(info.get('label', ''))
                imgui.table_next_column()
                state = info.get('state', '')
                imgui.text_colored(STATE_COLOURS.get(state, (0.8, 0.8, 0.8, 1.0)), state)
                imgui.table_next_column()
                report = info.get('report') or {}
                runtime = f"Python {info.get('pythonVersion', '')}"
                if report.get('torch'):
                    runtime += f" | torch {report['torch']}"
                if report.get('device'):
                    runtime += f" | {report['device']}"
                imgui.text(runtime)
                if info.get('note') and imgui.is_item_hovered():
                    imgui.set_tooltip(info['note'])
                imgui.table_next_column()
                imgui.text(f"{info.get('estimatedBytes', 0) / 1024 ** 3:.1f} GiB")
                imgui.table_next_column()
                busy = any(job.get('parameters', {}).get('engine') == name for job in installing)
                imgui.push_id(name)
                imgui.begin_disabled(bool(installing))
                label = tr('Repair') if info.get('installed') else tr('Install')
                if imgui.small_button(label):
                    self.app.jobs.submit('install_engine',
                                         {'engine': name, 'device': self.device,
                                          'repair': bool(self.repair or info.get('installed'))},
                                         callback=lambda job: self.refresh(),
                                         label=f'install_engine {name}')
                imgui.end_disabled()
                if busy:
                    imgui.same_line()
                    imgui.text_disabled(tr('installing'))
                imgui.pop_id()
            imgui.end_table()

        for job in installing:
            progress = job.get('progress') or {}
            imgui.progress_bar(float(progress.get('percent', 0.0)) / 100.0, (-1, 0),
                               self.app.jobs.progress_text(job))
            if imgui.button(self.app.tr('Cancel the installation')):
                self.app.jobs.cancel(job['jobId'])

    # -------------------------------------------------------------------- backends
    def _draw_backends(self):
        tr = self.app.tr
        if imgui.begin_table('##backends', 4, imgui.TableFlags_.borders | imgui.TableFlags_.row_bg
                             | imgui.TableFlags_.sizing_stretch_prop):
            for title, width in ((tr('Backend'), 150.0), (tr('Engine'), 120.0),
                                 (tr('Ready'), 80.0), (tr('Missing'), 0.0)):
                if width:
                    imgui.table_setup_column(title, imgui.TableColumnFlags_.width_fixed, width)
                else:
                    imgui.table_setup_column(title)
            imgui.table_headers_row()
            for item in self.backends:
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text(item.get('id', ''))
                if imgui.is_item_hovered():
                    imgui.set_tooltip(item.get('label', '') + ('\n' + item['note'] if item.get('note') else ''))
                imgui.table_next_column()
                imgui.text(item.get('engine', ''))
                imgui.table_next_column()
                ready = bool(item.get('ready'))
                imgui.text_colored((0.45, 0.85, 0.55, 1.0) if ready else (0.85, 0.45, 0.42, 1.0),
                                   tr('yes') if ready else tr('no'))
                imgui.table_next_column()
                missing = list(item.get('missingModels') or [])
                if not item.get('workerPresent'):
                    missing.append(tr('worker not ported'))
                if item.get('engineState') != 'Installed':
                    missing.append(tr('engine') + ' ' + str(item.get('engineState', '')))
                imgui.text(', '.join(missing) if missing else '-')
            imgui.end_table()

    # ---------------------------------------------------------------------- models
    def _draw_models(self):
        tr = self.app.tr
        imgui.set_next_item_width(160.0)
        _, self.filter_family = imgui.combo(tr('Family'), self.filter_family, self.families)
        family = self.families[self.filter_family] if self.filter_family else ''
        total = sum(item.get('sizeBytes', 0) for item in self.models
                    if not family or item.get('family') == family)
        imgui.same_line()
        imgui.text_disabled(f"{total / 1024 ** 3:.1f} GiB")

        if imgui.begin_table('##models', 6, imgui.TableFlags_.borders | imgui.TableFlags_.row_bg
                             | imgui.TableFlags_.sizing_stretch_prop | imgui.TableFlags_.scroll_y,
                             (0, 320)):
            for title, width in ((tr('Model'), 210.0), (tr('State'), 100.0), (tr('Size'), 90.0),
                                 (tr('Engine'), 110.0), (tr('Licence'), 0.0), ('', 110.0)):
                if width:
                    imgui.table_setup_column(title, imgui.TableColumnFlags_.width_fixed, width)
                else:
                    imgui.table_setup_column(title)
            imgui.table_headers_row()
            for item in self.models:
                if family and item.get('family') != family:
                    continue
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text(item.get('id', ''))
                if imgui.is_item_hovered():
                    imgui.set_tooltip(f"{item.get('name', '')}\n{item.get('purpose', '')}\n"
                                      f"{tr('Revision')}: {item.get('revision') or tr('unknown')}\n"
                                      f"{item.get('source', '')}")
                imgui.table_next_column()
                state = item.get('state', '')
                imgui.text_colored(STATE_COLOURS.get(state, (0.8, 0.8, 0.8, 1.0)), state)
                if item.get('missingFiles') and imgui.is_item_hovered():
                    imgui.set_tooltip('\n'.join(item['missingFiles'][:10]))
                imgui.table_next_column()
                imgui.text(f"{item.get('sizeBytes', 0) / 1024 ** 3:.2f} GiB")
                imgui.table_next_column()
                imgui.text(item.get('engine', ''))
                imgui.table_next_column()
                licence = item.get('license', '')
                if item.get('nonCommercial'):
                    imgui.text_colored((0.95, 0.75, 0.35, 1.0), tr('non-commercial'))
                    imgui.same_line()
                if item.get('gated'):
                    imgui.text_colored((0.95, 0.65, 0.35, 1.0), tr('gated'))
                    imgui.same_line()
                imgui.text_wrapped(licence if len(licence) < 60 else licence[:57] + '...')
                if imgui.is_item_hovered():
                    imgui.set_tooltip(licence)
                imgui.table_next_column()
                self._model_action(item, state)
            imgui.end_table()

        self._draw_downloads()
        self._draw_manual_files()
        for warning in self.warnings[:6]:
            imgui.bullet_text(str(warning)[:200])

    def _model_action(self, item, state):
        """Install a declared model, when the application knows where its files come from."""
        tr = self.app.tr
        if not item.get('installable'):
            imgui.text_disabled('-' if state == 'Installed' else tr('manual'))
            if imgui.is_item_hovered():
                imgui.set_tooltip(tr('This model came with the absorbed Tools; '
                                     'its download is not described here.'))
            return
        busy = any(job.get('parameters', {}).get('model') == item['id']
                   for job in self.app.jobs.running('install_model'))
        imgui.push_id('model-' + item['id'])
        imgui.begin_disabled(busy)
        label = tr('Repair') if state == 'Installed' else (
            tr('Resume') if state == 'Partial' else tr('Install'))
        if imgui.small_button(label):
            self.app.jobs.submit('install_model',
                                 {'model': item['id'], 'repair': state == 'Installed'},
                                 callback=lambda job: self.refresh(),
                                 label=f"install_model {item['id']}")
        imgui.end_disabled()
        if busy:
            imgui.same_line()
            imgui.text_disabled(tr('downloading'))
        imgui.pop_id()

    def _draw_downloads(self):
        for job in self.app.jobs.running('install_model'):
            progress = job.get('progress') or {}
            imgui.progress_bar(float(progress.get('percent', 0.0)) / 100.0, (-1, 0),
                               self.app.jobs.progress_text(job))
            imgui.push_id('cancel-' + job['jobId'])
            if imgui.button(self.app.tr('Cancel the download')):
                self.app.jobs.cancel(job['jobId'])
            imgui.pop_id()

    def _draw_manual_files(self):
        """Files whose licence is accepted in person: the application imports, never signs in."""
        tr = self.app.tr
        pending = [(item, entry) for item in self.models
                   for entry in item.get('manualFiles') or [] if not entry.get('present')]
        if not pending:
            return
        imgui.separator()
        imgui.text_colored((0.95, 0.75, 0.35, 1.0), tr('Files to accept and download yourself'))
        for item, entry in pending:
            imgui.push_id(f"manual-{item['id']}-{entry['target']}")
            imgui.bullet_text(f"{item['id']}: {entry['label']}")
            imgui.text_wrapped(entry.get('note') or '')
            if entry.get('page'):
                imgui.text_disabled(entry['page'])
                imgui.same_line()
                if imgui.small_button(tr('Copy the address')):
                    imgui.set_clipboard_text(entry['page'])
                imgui.same_line()
            if imgui.small_button(tr('Import the file...')):
                self.app.dialogs.open_file(
                    f"model-import#{item['id']}#{entry['target']}",
                    tr('Choose the file downloaded from the official page'),
                    filters=[tr('Accepted files'),
                             ' '.join('*' + suffix for suffix in entry.get('accepts', [])) or '*',
                             'All files', '*'])
            imgui.pop_id()

    def accept_dialog(self, purpose, result):
        """Import the file the user picked for a licensed model."""
        if not str(purpose).startswith('model-import#'):
            return False
        _, model, target = str(purpose).split('#', 2)
        path = result[0] if isinstance(result, (list, tuple)) else result
        if not path:
            return True
        self.app.jobs.submit('import_model_file',
                             {'model': model, 'file': str(path), 'target': target},
                             callback=lambda job: self.refresh(),
                             label=f'import_model_file {model}')
        return True
