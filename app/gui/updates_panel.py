"""The Updates page: the three streams, and what can be done with each.

The application is a GitHub release of the ``app`` folder: check, stage, verify, activate at the
next start, roll back. The engines are rebuilt from the revisions pinned in ``app/engines.json``
by the Installation page, and the weights follow their own catalogue, so those two streams are
reported here but acted on there. No button in this panel touches ``data/``.

Everything goes through the same operations as the CLI and MCP: ``update_status``,
``check_update``, ``stage_update``, ``activate_update`` and ``rollback_update``.
"""
from imgui_bundle import imgui

import cyui
from gui import widgets


class UpdatesPanel:
    def __init__(self, app):
        self.app = app
        self.status = {}
        self.check = {}
        self.loaded = False
        self.error = ''
        self.message = ''
        self.repository = ''
        self.source = ''
        self.sha256 = ''
        self.auto_check = False

    # ------------------------------------------------------------------ state
    def refresh(self):
        try:
            self.status = self.app.jobs.run_sync('update_status', {}, timeout=30)
            application = self.status.get('application') or {}
            self.repository = application.get('repository', '')
            self.auto_check = bool(application.get('checkAutomatically'))
            self.error = ''
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
        self.loaded = True

    def _submit(self, operation, parameters, label):
        def done(job):
            self.refresh()
            outputs = job.get('outputs') or {}
            if operation == 'check_update':
                self.check = outputs
            if outputs.get('restartRequired'):
                self.message = self.app.tr('Recorded. Close and reopen the application to apply it.')
        self.app.jobs.submit(operation, parameters, callback=done, label=label)

    # ------------------------------------------------------------------- draw
    def draw(self):
        if not self.loaded:
            self.refresh()
        tr = self.app.tr
        cyui.panel_header(tr('Updates'), tr(
            'The application, the engines and the model weights are three separate streams. '
            'They have their own versions and their own licences, and an update never replaces '
            'the data folder.'))
        imgui.same_line()
        cyui.align_right(cyui.button_width(widgets.action('Refresh', cyui.icon.refresh, tr)))
        if cyui.button(widgets.action('Refresh', cyui.icon.refresh, tr), 'ghost'):
            self.refresh()
        if self.error:
            cyui.callout('error', self.error)
        if self.message:
            cyui.callout('success', self.message)
        cyui.space(6.0)

        self._draw_application()
        cyui.space(8.0)
        self._draw_engines()
        cyui.space(8.0)
        self._draw_models()

    # ------------------------------------------------------------ application
    def _draw_application(self):
        tr = self.app.tr
        application = self.status.get('application') or {}
        busy = self.app.jobs.is_running('check_update', 'stage_update', 'activate_update',
                                        'rollback_update')
        report = (self.check or {}).get('report') or {}
        newer = bool(report.get('newer'))
        if cyui.begin_card('##application-stream', '', 0.0, 'accent' if newer else 'neutral'):
            cyui.heading(tr('Application'), 3)
            imgui.same_line()
            cyui.badge(f"{tr('version')} {application.get('version', '?')}".upper())
            if newer:
                imgui.same_line()
                cyui.badge(f"{tr('Release available')}: {report.get('latest', '')}".upper(), 'success')
            cyui.space(4.0)
            if cyui.begin_properties('##application-source'):
                cyui.property(tr('GitHub repository (owner/name)'),
                              tr('Where the releases are read from; the manifest declares it.'))
                changed, value = imgui.input_text_with_hint('##repository', tr('No repository configured for this Tool yet.'),
                                                            self.repository)
                if changed:
                    self.repository = value
                cyui.property(tr('Check automatically at start'))
                changed, value = cyui.toggle_switch('##auto-check', self.auto_check)
                if changed:
                    self.auto_check = value
                cyui.end_properties()
            imgui.begin_disabled(busy)
            check = widgets.action('Check for an update', cyui.icon.sync, tr)
            if (cyui.button(check) if newer else cyui.primary_button(check)):
                self._submit('check_update',
                             {'stream': 'application', 'repository': self.repository.strip()},
                             'check_update')
            imgui.end_disabled()
            if report:
                if newer and report.get('asset'):
                    imgui.same_line()
                    imgui.begin_disabled(busy)
                    if cyui.primary_button(widgets.action('Stage this release', cyui.icon.download, tr)):
                        self._submit('stage_update',
                                     {'source': report['asset'], 'version': str(report.get('latest', ''))},
                                     'stage_update')
                    imgui.end_disabled()
                elif not newer:
                    imgui.same_line()
                    imgui.align_text_to_frame_padding()
                    cyui.text_dim(f"{tr('Latest release')}: {report.get('latest') or tr('unknown')}")
                if report.get('message'):
                    cyui.space(2.0)
                    cyui.callout('info' if report.get('configured', True) else 'warning', str(report['message']))
                if report.get('notes'):
                    cyui.space(2.0)
                    imgui.push_text_wrap_pos(0.0)
                    cyui.text_dim(str(report['notes'])[:600])
                    imgui.pop_text_wrap_pos()

            for job in self.app.jobs.running('check_update', 'stage_update'):
                widgets.progress(job, self.app.jobs)
                imgui.push_id('cancel-update-' + job['jobId'])
                if cyui.button(widgets.action('Cancel', cyui.icon.stop, tr)):
                    self.app.jobs.cancel(job['jobId'])
                imgui.pop_id()

            cyui.space(4.0)
            if cyui.begin_section(tr('Stage a release by hand') + '###manual-stage', False):
                cyui.text_faint(tr('Staging only unpacks and verifies; nothing is replaced.'))
                if cyui.begin_properties('##manual-stage-fields'):
                    cyui.property(tr('Release archive (URL or local .zip)'))
                    imgui.set_next_item_width(max(cyui.dp(80.0), imgui.get_content_region_avail().x
                                                  - imgui.get_frame_height() - cyui.dp(6.0)))
                    changed, value = imgui.input_text('##archive', self.source)
                    if changed:
                        self.source = value
                    imgui.same_line(0.0, cyui.dp(4.0))
                    if cyui.icon_button(cyui.icon.folder, tr('Choose a file...')):
                        self.app.dialogs.open_file('update-archive', tr('Choose the release archive'),
                                                   filters=['Zip', '*.zip', 'All files', '*'])
                    cyui.property(tr('Expected SHA-256 (optional)'))
                    changed, value = imgui.input_text('##sha256', self.sha256)
                    if changed:
                        self.sha256 = value
                    cyui.end_properties()
                imgui.begin_disabled(busy or not self.source.strip())
                if cyui.button(widgets.action('Stage', cyui.icon.download, tr)):
                    self._submit('stage_update',
                                 {'source': self.source.strip(), 'sha256': self.sha256.strip()},
                                 'stage_update')
                imgui.end_disabled()
                cyui.end_section()

            self._draw_staged(busy)
            self._draw_pending(busy)
            self._draw_backups(busy)
        cyui.end_card()

    def _draw_staged(self, busy):
        tr = self.app.tr
        staged = self.status.get('staged') or []
        if not staged:
            return
        cyui.space(4.0)
        cyui.section_title(tr('Staged, waiting for your decision'))
        for entry in staged:
            imgui.push_id('staged-' + entry['path'])
            imgui.align_text_to_frame_padding()
            imgui.text_unformatted(f"{entry.get('version', '?')}")
            imgui.same_line()
            cyui.text_dim(f"{entry.get('files', 0)} {tr('files')}, {tr('staged on')} {entry.get('stagedAt', '')}")
            cyui.tooltip(f"{entry['path']}\nSHA-256 {entry.get('sha256', '')}")
            imgui.same_line()
            imgui.begin_disabled(busy)
            if cyui.primary_button(tr('Activate at next start')):
                self._submit('activate_update', {'staged': entry['path']}, 'activate_update')
            imgui.end_disabled()
            imgui.pop_id()

    def _draw_pending(self, busy):
        tr = self.app.tr
        pending = self.status.get('pending')
        if not pending:
            return
        cyui.space(4.0)
        cyui.callout('warning', f"{tr('Waiting for a restart')}: {pending.get('mode', '')} "
                                f"{pending.get('fromVersion', '')} -> {pending.get('version', '')}")
        imgui.begin_disabled(busy)
        if cyui.button(tr('Cancel this change'), 'ghost'):
            self._submit('rollback_update', {'cancel': True}, 'cancel pending update')
        imgui.end_disabled()

    def _draw_backups(self, busy):
        tr = self.app.tr
        backups = self.status.get('backups') or []
        applied = self.status.get('lastApplied')
        if applied:
            cyui.space(4.0)
            cyui.text_faint(f"{tr('Last applied')}: {applied.get('fromVersion', '')} -> "
                            f"{applied.get('newVersion', '')} ({applied.get('appliedAt', '')})")
        if not backups:
            return
        cyui.space(4.0)
        cyui.section_title(tr('Backups kept'))
        for entry in backups:
            imgui.push_id('backup-' + entry['path'])
            imgui.align_text_to_frame_padding()
            imgui.text_unformatted(f"{entry.get('version', '?')}")
            imgui.same_line()
            cyui.text_dim(entry.get('savedAt', ''))
            cyui.tooltip(entry['path'])
            imgui.same_line()
            imgui.begin_disabled(busy)
            if cyui.button(tr('Restore this one at next start'), 'ghost', small=True):
                self._submit('rollback_update', {'backup': entry['path']}, 'rollback_update')
            imgui.end_disabled()
            imgui.pop_id()

    # ---------------------------------------------------------------- engines
    def _draw_engines(self):
        tr = self.app.tr
        engines = self.status.get('engines') or []
        installed = sum(1 for entry in engines if entry.get('installed'))
        if cyui.begin_card('##engine-stream'):
            cyui.heading(tr('Engines'), 3)
            imgui.same_line()
            cyui.badge(f"{installed}/{len(engines)} {tr('installed')}".upper())
            imgui.push_text_wrap_pos(0.0)
            cyui.text_dim(tr(
                'Each engine pins the upstream revision it was built against, in app/engines.json. '
                'Reinstalling an engine from the Installation tab checks out that exact revision.'))
            imgui.pop_text_wrap_pos()
            cyui.space(2.0)
            for entry in engines:
                cyui.status_dot(cyui.palette().success if entry.get('installed') else cyui.palette().textFaint)
                imgui.same_line(0.0, cyui.dp(4.0))
                imgui.text_unformatted(entry.get('engine', ''))
                sources = entry.get('sources') or {}
                if sources:
                    cyui.tooltip('\n'.join(f'{key}: {value}' for key, value in sources.items()))
            cyui.space(2.0)
            if cyui.button(widgets.action('Open the Installation tab', cyui.icon.download, tr), 'ghost'):
                self.app.select_tab('Installation')
        cyui.end_card()

    # ----------------------------------------------------------------- models
    def _draw_models(self):
        tr = self.app.tr
        models = self.status.get('models') or []
        installed = sum(1 for item in models if item.get('installed'))
        if cyui.begin_card('##model-stream'):
            cyui.heading(tr('Model weights'), 3)
            imgui.same_line()
            cyui.badge(f"{installed}/{len(models)} {tr('installed')}".upper())
            imgui.push_text_wrap_pos(0.0)
            cyui.text_dim(tr(
                'Weights follow their own catalogue (app/models/catalog.json) with their revision and '
                'their licence; see the Installation tab.'))
            imgui.pop_text_wrap_pos()
            pending = [item for item in models if not item.get('installed') and item.get('installable')]
            for item in pending:
                cyui.status_dot(cyui.palette().info)
                imgui.same_line(0.0, cyui.dp(4.0))
                imgui.text_unformatted(f"{item['id']}: {tr('can be installed')}")
        cyui.end_card()

    # ---------------------------------------------------------------- dialogs
    def accept_dialog(self, purpose, result):
        if str(purpose) != 'update-archive':
            return False
        path = result[0] if isinstance(result, (list, tuple)) else result
        if path:
            self.source = str(path)
        return True
