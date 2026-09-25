"""The Updates tab: the three streams, and what can be done with each.

The application is a GitHub release of the ``app`` folder: check, stage, verify, activate at the
next start, roll back. The engines are rebuilt from the revisions pinned in ``app/engines.json``
by the Installation tab, and the weights follow their own catalogue, so those two streams are
reported here but acted on there. No button in this panel touches ``data/``.

Everything goes through the same operations as the CLI and MCP: ``update_status``,
``check_update``, ``stage_update``, ``activate_update`` and ``rollback_update``.
"""
from imgui_bundle import imgui

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
        imgui.text_wrapped(tr(
            'The application, the engines and the model weights are three separate streams. '
            'They have their own versions and their own licences, and an update never replaces '
            'the data folder.'))
        if imgui.button(tr('Refresh')):
            self.refresh()
        if self.error:
            widgets.status_line(self.error, error=True)
        if self.message:
            widgets.status_line(self.message)
        imgui.separator()

        self._draw_application()
        imgui.separator()
        self._draw_engines()
        imgui.separator()
        self._draw_models()

    # ------------------------------------------------------------ application
    def _draw_application(self):
        tr = self.app.tr
        application = self.status.get('application') or {}
        busy = self.app.jobs.is_running('check_update', 'stage_update', 'activate_update',
                                        'rollback_update')
        imgui.text(f"{tr('Application')}  —  {tr('version')} {application.get('version', '?')}")
        imgui.indent()

        imgui.set_next_item_width(420.0)
        changed, value = imgui.input_text(tr('GitHub repository (owner/name)'), self.repository)
        if changed:
            self.repository = value
        changed, value = imgui.checkbox(tr('Check automatically at start'), self.auto_check)
        if changed:
            self.auto_check = value
        imgui.begin_disabled(busy)
        if imgui.button(tr('Check for an update')):
            self._submit('check_update',
                         {'stream': 'application', 'repository': self.repository.strip()},
                         'check_update')
        imgui.end_disabled()
        if not self.repository.strip():
            imgui.same_line()
            imgui.text_disabled(tr('No repository configured for this Tool yet.'))

        report = (self.check or {}).get('report') or {}
        if report:
            latest = report.get('latest') or tr('unknown')
            if report.get('newer'):
                imgui.text_colored((0.45, 0.85, 0.55, 1.0),
                                   f"{tr('Release available')}: {latest}")
                if report.get('asset') and imgui.small_button(tr('Stage this release')):
                    self._submit('stage_update',
                                 {'source': report['asset'], 'version': str(latest)},
                                 'stage_update')
            else:
                imgui.text_disabled(f"{tr('Latest release')}: {latest}")
            if report.get('message'):
                widgets.status_line(str(report['message']), error=not report.get('configured', True))
            if report.get('notes'):
                imgui.text_wrapped(str(report['notes'])[:600])

        # Staging by hand: a file someone downloaded, or any direct URL.
        imgui.set_next_item_width(420.0)
        changed, value = imgui.input_text(tr('Release archive (URL or local .zip)'), self.source)
        if changed:
            self.source = value
        imgui.same_line()
        if imgui.button(tr('Choose a file...')):
            self.app.dialogs.open_file('update-archive', tr('Choose the release archive'),
                                       filters=['Zip', '*.zip', 'All files', '*'])
        imgui.set_next_item_width(420.0)
        changed, value = imgui.input_text(tr('Expected SHA-256 (optional)'), self.sha256)
        if changed:
            self.sha256 = value
        imgui.begin_disabled(busy or not self.source.strip())
        if imgui.button(tr('Stage')):
            self._submit('stage_update',
                         {'source': self.source.strip(), 'sha256': self.sha256.strip()},
                         'stage_update')
        imgui.end_disabled()
        imgui.same_line()
        imgui.text_disabled(tr('Staging only unpacks and verifies; nothing is replaced.'))

        for job in self.app.jobs.running('check_update', 'stage_update'):
            progress = job.get('progress') or {}
            imgui.progress_bar(float(progress.get('percent', 0.0)) / 100.0, (-1, 0),
                               self.app.jobs.progress_text(job))
            imgui.push_id('cancel-update-' + job['jobId'])
            if imgui.button(tr('Cancel')):
                self.app.jobs.cancel(job['jobId'])
            imgui.pop_id()

        self._draw_staged(busy)
        self._draw_pending(busy)
        self._draw_backups(busy)
        imgui.unindent()

    def _draw_staged(self, busy):
        tr = self.app.tr
        staged = self.status.get('staged') or []
        if not staged:
            return
        imgui.text(tr('Staged, waiting for your decision'))
        for entry in staged:
            imgui.push_id('staged-' + entry['path'])
            imgui.bullet_text(f"{entry.get('version', '?')}  ({entry.get('files', 0)} "
                              f"{tr('files')}, {tr('staged on')} {entry.get('stagedAt', '')})")
            if imgui.is_item_hovered():
                imgui.set_tooltip(f"{entry['path']}\nSHA-256 {entry.get('sha256', '')}")
            imgui.begin_disabled(busy)
            if imgui.small_button(tr('Activate at next start')):
                self._submit('activate_update', {'staged': entry['path']}, 'activate_update')
            imgui.end_disabled()
            imgui.pop_id()

    def _draw_pending(self, busy):
        tr = self.app.tr
        pending = self.status.get('pending')
        if not pending:
            return
        imgui.text_colored((0.95, 0.75, 0.35, 1.0),
                           f"{tr('Waiting for a restart')}: {pending.get('mode', '')} "
                           f"{pending.get('fromVersion', '')} -> {pending.get('version', '')}")
        imgui.begin_disabled(busy)
        if imgui.small_button(tr('Cancel this change')):
            self._submit('rollback_update', {'cancel': True}, 'cancel pending update')
        imgui.end_disabled()

    def _draw_backups(self, busy):
        tr = self.app.tr
        backups = self.status.get('backups') or []
        applied = self.status.get('lastApplied')
        if applied:
            imgui.text_disabled(f"{tr('Last applied')}: {applied.get('fromVersion', '')} -> "
                                f"{applied.get('newVersion', '')} ({applied.get('appliedAt', '')})")
        if not backups:
            return
        imgui.text(tr('Backups kept'))
        for entry in backups:
            imgui.push_id('backup-' + entry['path'])
            imgui.bullet_text(f"{entry.get('version', '?')}  ({entry.get('savedAt', '')})")
            if imgui.is_item_hovered():
                imgui.set_tooltip(entry['path'])
            imgui.begin_disabled(busy)
            if imgui.small_button(tr('Restore this one at next start')):
                self._submit('rollback_update', {'backup': entry['path']}, 'rollback_update')
            imgui.end_disabled()
            imgui.pop_id()

    # ---------------------------------------------------------------- engines
    def _draw_engines(self):
        tr = self.app.tr
        imgui.text(tr('Engines'))
        imgui.indent()
        imgui.text_wrapped(tr(
            'Each engine pins the upstream revision it was built against, in app/engines.json. '
            'Reinstalling an engine from the Installation tab checks out that exact revision.'))
        for entry in self.status.get('engines') or []:
            state = tr('installed') if entry.get('installed') else tr('not installed')
            imgui.bullet_text(f"{entry.get('engine', '')} — {state}")
            sources = entry.get('sources') or {}
            if sources and imgui.is_item_hovered():
                imgui.set_tooltip('\n'.join(f'{key}: {value}' for key, value in sources.items()))
        if imgui.button(tr('Open the Installation tab')):
            self.app.select_tab('Installation')
        imgui.unindent()

    # ----------------------------------------------------------------- models
    def _draw_models(self):
        tr = self.app.tr
        models = self.status.get('models') or []
        installed = sum(1 for item in models if item.get('installed'))
        imgui.text(f"{tr('Model weights')}  —  {installed}/{len(models)} {tr('installed')}")
        imgui.indent()
        imgui.text_wrapped(tr(
            'Weights follow their own catalogue (app/models/catalog.json) with their revision and '
            'their licence; see the Installation tab.'))
        pending = [item for item in models if not item.get('installed') and item.get('installable')]
        for item in pending:
            imgui.bullet_text(f"{item['id']}: {tr('can be installed')}")
        imgui.unindent()

    # ---------------------------------------------------------------- dialogs
    def accept_dialog(self, purpose, result):
        if str(purpose) != 'update-archive':
            return False
        path = result[0] if isinstance(result, (list, tuple)) else result
        if path:
            self.source = str(path)
        return True
