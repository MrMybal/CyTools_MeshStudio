"""The Installation page: engine environments and the model catalogue.

Everything shown here comes from ``diagnose``, so the interface reports the same state as the
CLI and MCP. Installing an engine is a job like any other: it streams its progress and can be
cancelled.
"""
from imgui_bundle import imgui

import cyui
from gui import widgets

STATE_TONES = {'Installed': 'success', 'Partial': 'warning', 'NotInstalled': 'error'}
DEVICES = ['auto', 'cuda', 'cpu']
TABLE = imgui.TableFlags_.borders_inner_h | imgui.TableFlags_.row_bg | imgui.TableFlags_.sizing_stretch_prop


STATE_LABELS = {'Installed': 'Installed', 'Partial': 'Partially installed', 'NotInstalled': 'Not installed'}


def _state(text, tr):
    """A coloured dot and the state, in a table cell whose rows also hold buttons."""
    tone = STATE_TONES.get(text, 'neutral')
    colour = cyui.palette().textFaint if tone == 'neutral' else cyui.tone_colour(tone)
    # The dot is placed from the text it labels: a table row moves its text down to the
    # baseline of the buttons beside it, and a dot drawn at the cursor would sit above it.
    radius = imgui.get_text_line_height() * 0.24
    gap = radius * 2.0 + cyui.dp(6.0)
    imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + gap)
    imgui.text_unformatted(tr(STATE_LABELS.get(text, text)))
    top, bottom = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    centre = imgui.ImVec2(top.x - gap + radius + cyui.dp(1.0), (top.y + bottom.y) * 0.5)
    draw = imgui.get_window_draw_list()
    draw.add_circle_filled(centre, radius * 1.8, cyui.alpha(colour, 0.18), 16)
    draw.add_circle_filled(centre, radius, colour, 16)


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
        self.search = ''

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
        installed = sum(1 for info in self.engines.values() if info.get('installed'))
        models = sum(1 for item in self.models if item.get('state') == 'Installed')
        cyui.panel_header(tr('Installation'),
                          f"{installed}/{len(self.engines)} {tr('engines installed')} · "
                          f"{models}/{len(self.models)} {tr('models installed')}")
        imgui.same_line()
        cyui.align_right(cyui.button_width(widgets.action('Refresh', cyui.icon.refresh, tr)))
        if cyui.button(widgets.action('Refresh', cyui.icon.refresh, tr), 'ghost'):
            self.refresh()
        cyui.tooltip(tr('State comes from diagnose, the same report the CLI prints.'))
        if self.error:
            cyui.callout('error', self.error)
        # What waits for the user comes first: files only they can download.
        self._draw_manual_files()
        cyui.space(6.0)

        if cyui.begin_section(tr('Engines') + '###engines-section'):
            self._draw_engines()
            cyui.end_section()
        if cyui.begin_section(tr('Models') + '###models-section'):
            self._draw_models()
            cyui.end_section()
        if cyui.begin_section(tr('Backends') + '###backends-section', False):
            self._draw_backends()
            cyui.end_section()

    # --------------------------------------------------------------------- engines
    def _draw_engines(self):
        tr = self.app.tr
        installing = self.app.jobs.running('install_engine')
        cyui.text_dim(tr('Device'))
        imgui.same_line()
        index = DEVICES.index(self.device) if self.device in DEVICES else 0
        changed, index = cyui.segmented('##device', DEVICES, index)
        if changed:
            self.device = DEVICES[index]
        cyui.tooltip(tr('Which PyTorch build an engine gets: auto picks CUDA when an NVIDIA card is present.'))
        imgui.same_line(0.0, cyui.dp(16.0))
        _, self.repair = cyui.toggle_switch(tr('Reinstall even if installed') + '###repair', self.repair)
        cyui.space(4.0)

        if imgui.begin_table('##engines', 5, TABLE):
            for title, width in ((tr('Engine'), 150.0), (tr('State'), 120.0), (tr('Runtime'), 0.0),
                                 (tr('Size'), 80.0), ('', 120.0)):
                if width:
                    imgui.table_setup_column(title, imgui.TableColumnFlags_.width_fixed, cyui.dp(width))
                else:
                    imgui.table_setup_column(title)
            imgui.table_headers_row()
            for name, info in self.engines.items():
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.align_text_to_frame_padding()
                imgui.text_unformatted(name)
                cyui.tooltip(info.get('label', ''))
                imgui.table_next_column()
                _state(info.get('state', ''), tr)
                imgui.table_next_column()
                report = info.get('report') or {}
                runtime = f"Python {info.get('pythonVersion', '')}"
                if report.get('torch'):
                    runtime += f" · torch {report['torch']}"
                if report.get('device'):
                    runtime += f" · {report['device']}"
                cyui.text_dim(runtime)
                cyui.tooltip(info.get('note', ''))
                imgui.table_next_column()
                cyui.text_dim(f"{info.get('estimatedBytes', 0) / 1024 ** 3:.1f} GiB")
                imgui.table_next_column()
                busy = any(job.get('parameters', {}).get('engine') == name for job in installing)
                imgui.push_id(name)
                if busy:
                    cyui.spinner('##installing')
                    imgui.same_line()
                    cyui.text_dim(tr('installing'))
                else:
                    imgui.begin_disabled(bool(installing))
                    label = tr('Repair') if info.get('installed') else tr('Install')
                    if cyui.button(label, 'secondary' if info.get('installed') else 'primary', small=True):
                        self.app.jobs.submit('install_engine',
                                             {'engine': name, 'device': self.device,
                                              'repair': bool(self.repair or info.get('installed'))},
                                             callback=lambda job: self.refresh(),
                                             label=f'install_engine {name}')
                    imgui.end_disabled()
                imgui.pop_id()
            imgui.end_table()

        for job in installing:
            widgets.progress(job, self.app.jobs)
            imgui.push_id('cancel-engine-' + job['jobId'])
            if cyui.button(widgets.action('Cancel the installation', cyui.icon.stop, tr)):
                self.app.jobs.cancel(job['jobId'])
            imgui.pop_id()

    # -------------------------------------------------------------------- backends
    def _draw_backends(self):
        tr = self.app.tr
        if imgui.begin_table('##backends', 4, TABLE):
            for title, width in ((tr('Backend'), 150.0), (tr('Engine'), 120.0),
                                 (tr('Ready'), 80.0), (tr('Missing'), 0.0)):
                if width:
                    imgui.table_setup_column(title, imgui.TableColumnFlags_.width_fixed, cyui.dp(width))
                else:
                    imgui.table_setup_column(title)
            imgui.table_headers_row()
            for item in self.backends:
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text_unformatted(item.get('id', ''))
                cyui.tooltip(item.get('label', '') + ('\n' + item['note'] if item.get('note') else ''))
                imgui.table_next_column()
                cyui.text_dim(item.get('engine', ''))
                imgui.table_next_column()
                ready = bool(item.get('ready'))
                cyui.status_dot(cyui.palette().success if ready else cyui.palette().error)
                imgui.same_line(0.0, cyui.dp(4.0))
                imgui.text_unformatted(tr('yes') if ready else tr('no'))
                imgui.table_next_column()
                missing = list(item.get('missingModels') or [])
                if not item.get('workerPresent'):
                    missing.append(tr('worker not ported'))
                if item.get('engineState') != 'Installed':
                    missing.append(tr('engine') + ' ' + str(item.get('engineState', '')))
                cyui.text_dim(', '.join(missing) if missing else '-')
            imgui.end_table()

    # ---------------------------------------------------------------------- models
    def _draw_models(self):
        tr = self.app.tr
        imgui.set_next_item_width(cyui.dp(160.0))
        _, self.filter_family = imgui.combo('##family', self.filter_family,
                                            [tr('All families') if index == 0 else name
                                             for index, name in enumerate(self.families)])
        cyui.tooltip(tr('Family'))
        imgui.same_line()
        _, self.search = cyui.search_field('##model-search', self.search, tr('Search models'), cyui.dp(220.0))
        family = self.families[self.filter_family] if self.filter_family else ''
        needle = self.search.strip().casefold()
        visible = [item for item in self.models
                   if (not family or item.get('family') == family)
                   and (not needle or needle in (item.get('id', '') + ' ' + item.get('name', '') + ' '
                                                 + item.get('purpose', '')).casefold())]
        total = sum(item.get('sizeBytes', 0) for item in visible)
        imgui.same_line()
        imgui.align_text_to_frame_padding()
        cyui.text_faint(f"{len(visible)} · {total / 1024 ** 3:.1f} GiB")
        cyui.space(4.0)

        if visible and imgui.begin_table('##models', 6, TABLE | imgui.TableFlags_.scroll_y,
                                         (0, cyui.dp(330.0))):
            imgui.table_setup_scroll_freeze(0, 1)
            for title, width in ((tr('Model'), 210.0), (tr('State'), 120.0), (tr('Size'), 80.0),
                                 (tr('Engine'), 110.0), (tr('Licence'), 0.0), ('', 110.0)):
                if width:
                    imgui.table_setup_column(title, imgui.TableColumnFlags_.width_fixed, cyui.dp(width))
                else:
                    imgui.table_setup_column(title)
            imgui.table_headers_row()
            for item in visible:
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.align_text_to_frame_padding()
                imgui.text_unformatted(item.get('id', ''))
                cyui.tooltip(f"{item.get('name', '')}\n{item.get('purpose', '')}\n"
                             f"{tr('Revision')}: {item.get('revision') or tr('unknown')}\n"
                             f"{item.get('source', '')}")
                imgui.table_next_column()
                state = item.get('state', '')
                _state(state, tr)
                if item.get('missingFiles'):
                    cyui.tooltip('\n'.join(item['missingFiles'][:10]))
                imgui.table_next_column()
                cyui.text_dim(f"{item.get('sizeBytes', 0) / 1024 ** 3:.2f} GiB")
                imgui.table_next_column()
                cyui.text_dim(item.get('engine', ''))
                imgui.table_next_column()
                licence = item.get('license', '')
                if item.get('nonCommercial'):
                    cyui.badge(tr('NON-COMMERCIAL'), 'warning')
                    imgui.same_line()
                if item.get('gated'):
                    cyui.badge(tr('ACCEPTANCE'), 'info')
                    cyui.tooltip(tr('Its licence is accepted in person on its official page.'))
                    imgui.same_line()
                cyui.text_dim(licence if len(licence) < 60 else licence[:57] + '...')
                cyui.tooltip(licence)
                imgui.table_next_column()
                self._model_action(item, state)
            imgui.end_table()
        elif not visible:
            cyui.callout('info', tr('No model matches this family and search.'))

        self._draw_downloads()
        for warning in self.warnings[:6]:
            cyui.space(2.0)
            cyui.callout('warning', str(warning)[:300])

    def _model_action(self, item, state):
        """Install a declared model, when the application knows where its files come from."""
        tr = self.app.tr
        if not item.get('installable'):
            cyui.text_faint('-' if state == 'Installed' else tr('manual'))
            cyui.tooltip(tr('This model came with the absorbed Tools; its download is not described here.'))
            return
        busy = any(job.get('parameters', {}).get('model') == item['id']
                   for job in self.app.jobs.running('install_model'))
        imgui.push_id('model-' + item['id'])
        if busy:
            cyui.spinner('##downloading')
            imgui.same_line()
            cyui.text_dim(tr('downloading'))
        else:
            label = tr('Repair') if state == 'Installed' else (
                tr('Resume') if state == 'Partial' else tr('Install'))
            if cyui.button(label, 'secondary' if state == 'Installed' else 'primary', small=True):
                self.app.jobs.submit('install_model',
                                     {'model': item['id'], 'repair': state == 'Installed'},
                                     callback=lambda job: self.refresh(),
                                     label=f"install_model {item['id']}")
        imgui.pop_id()

    def _draw_downloads(self):
        tr = self.app.tr
        for job in self.app.jobs.running('install_model'):
            cyui.space(2.0)
            widgets.progress(job, self.app.jobs)
            imgui.push_id('cancel-' + job['jobId'])
            if cyui.button(widgets.action('Cancel the download', cyui.icon.stop, tr)):
                self.app.jobs.cancel(job['jobId'])
            imgui.pop_id()

    def _draw_manual_files(self):
        """Files whose licence is accepted in person: the application imports, never signs in."""
        tr = self.app.tr
        pending = [(item, entry) for item in self.models
                   for entry in item.get('manualFiles') or [] if not entry.get('present')]
        if not pending:
            return
        cyui.space(6.0)
        if cyui.begin_card('##manual-files', tr('Files to accept and download yourself'), 0.0, 'warning'):
            for item, entry in pending:
                imgui.push_id(f"manual-{item['id']}-{entry['target']}")
                imgui.text_unformatted(f"{item['id']}: {entry['label']}")
                if entry.get('note'):
                    imgui.push_text_wrap_pos(0.0)
                    cyui.text_dim(entry['note'])
                    imgui.pop_text_wrap_pos()
                if entry.get('page'):
                    cyui.text_faint(entry['page'])
                    imgui.same_line()
                    if cyui.button(widgets.action('Copy the address', cyui.icon.copy, tr), 'ghost', small=True):
                        imgui.set_clipboard_text(entry['page'])
                        cyui.notify(tr('Address copied to the clipboard'), 'success')
                    imgui.same_line()
                if cyui.button(widgets.action('Import the file...', cyui.icon.import_file, tr), small=True):
                    self.app.dialogs.open_file(
                        f"model-import#{item['id']}#{entry['target']}",
                        tr('Choose the file downloaded from the official page'),
                        filters=[tr('Accepted files'),
                                 ' '.join('*' + suffix for suffix in entry.get('accepts', [])) or '*',
                                 'All files', '*'])
                cyui.space(4.0)
                imgui.pop_id()
        cyui.end_card()

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
