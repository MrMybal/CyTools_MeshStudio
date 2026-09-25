"""Scripted clicks through the Dear ImGui test engine.

    runtime/python/Scripts/python.exe app/desktop.py --ui-test-interactions

Real clicks on the real widgets, recorded in data/reports/ui-interactions.json. The first
scenario is the one a user performs without thinking: click every tool in the list, one after
another. A form that only renders when it happens to be selected first is not tested, and
that is exactly how eight operations shipped with a crash.

The only job submitted is a workflow on a picture that does not exist: it is refused on the
missing file before any model loads, which proves that Run answers on screen.
"""
import json
from pathlib import Path
import traceback

from imgui_bundle import imgui, hello_imgui

te = imgui.test_engine


class Recorder:
    def __init__(self, data):
        self.data = Path(data)
        self.results = []
        self.done = False

    def check(self, name, condition, detail=''):
        self.results.append({'check': name, 'ok': bool(condition), 'detail': str(detail)[:400]})

    def save(self):
        path = self.data / 'reports' / 'ui-interactions.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        summary = {'passed': sum(item['ok'] for item in self.results),
                   'failed': sum(not item['ok'] for item in self.results),
                   'checks': self.results}
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
        return summary


def wait(ctx, frames=2):
    for _ in range(frames):
        ctx.yield_()


def _exists(ctx, ref):
    try:
        return bool(ctx.item_exists(ref))
    except Exception:  # noqa: BLE001
        return False


def _combo(label):
    """A reference to the combo drawn under this label in the last frames, or None.

    The test engine does not find a combo from its label in this build: looked up that way, 0 of
    the 75 combos of the tool forms were found, and the check that opens them opened none. The
    widgets record the id of each combo they draw, and the id is what the engine finds.
    """
    from gui import widgets
    drawn = widgets.COMBO_IDS.get(label)
    if not drawn or drawn[0] < imgui.get_frame_count() - 3:
        return None
    return te.TestRef(drawn[1])


def register(app, runner, recorder):
    engine = hello_imgui.get_imgui_test_engine()
    test = te.register_test(engine, 'meshstudio', 'interactions')

    def run(ctx):
        try:
            _scenario(app, ctx, recorder)
        except Exception:  # noqa: BLE001
            recorder.check('scenario raised no exception', False, traceback.format_exc())
        finally:
            recorder.done = True

    test.test_func = run
    te.queue_test(engine, test)


def _scenario(app, ctx, recorder):
    app.select_tab('Tools')
    wait(ctx, 3)

    # --- click every tool of the list, the way a user browses them
    clicked, missing = 0, []
    combos_found, combos_tried = 0, 0
    for category in app.tools.categories:
        for operation in app.tools.by_category[category]:
            label = app.tr(operation['name'])
            ref = f'**/{label}'
            if not _exists(ctx, ref):
                missing.append(operation['id'])
                continue
            ctx.item_click(ref)
            wait(ctx, 2)
            clicked += 1
            if app.tools.selected != operation['id']:
                recorder.check(f"clicking {operation['id']} selects it", False, app.tools.selected)
                continue
            # The advanced section hides half of the controls of a ported operation.
            advanced = f"**/{app.tr('Advanced settings')}"
            if _exists(ctx, advanced):
                ctx.item_click(advanced)
                wait(ctx, 2)
                ctx.item_click(advanced)
                wait(ctx, 1)
            # Opening a combo is its own code path: the popup builds the item list.
            opened_combos = 0
            for field, schema in (operation['inputSchema'].get('properties') or {}).items():
                if not schema.get('enum') or opened_combos >= 3:
                    continue
                combo = _combo(app.tr(schema.get('title') or field.replace('_', ' ').capitalize()))
                combos_tried += 1
                if combo is None or not _exists(ctx, combo):
                    continue
                combos_found += 1
                ctx.item_click(combo)
                wait(ctx, 2)
                # Escape did not close it: every lookup after the first opened combo failed.
                ctx.popup_close_all()
                wait(ctx, 2)
                opened_combos += 1
    # Advanced fields stay folded, and three combos per form at most are opened.
    recorder.check('the combos of the tool forms are found and opened',
                   combos_found >= 40, f'{combos_found} opened of {combos_tried} tried')
    recorder.check('every tool of the list was clicked without crashing',
                   clicked >= len(app.tools.by_category) and not missing,
                   f'{clicked} clicked, missing refs: {missing}')

    # --- the other tabs
    for name in ('Workflows', 'Installation', 'Updates', 'Tools'):
        app.select_tab(name)
        wait(ctx, 4)
        recorder.check(f'tab {name} drawn', True, '')

    # --- the updates tab drives the real operations, and says what it cannot do
    app.select_tab('Updates')
    wait(ctx, 4)
    recorder.check('updates read the application version',
                   bool((app.updates.status.get('application') or {}).get('version')),
                   app.updates.status.get('application'))
    check_button = f"**/{app.tr('Check for an update')}"
    recorder.check('updates offer the check button', _exists(ctx, check_button), check_button)
    recorder.check('updates list the engines and the weights',
                   bool(app.updates.status.get('engines')) and bool(app.updates.status.get('models')),
                   [len(app.updates.status.get('engines') or []),
                    len(app.updates.status.get('models') or [])])
    # The repository comes from the manifest when nothing was typed, and the button really
    # asks GitHub: the interface's client once lacked the network permission, so the check was
    # refused before any request left — a button that exists is not a button that works.
    recorder.check('updates know the repository of the Tool without any setting',
                   app.updates.repository == 'MrMybal/CyTools_MeshStudio', app.updates.repository)
    if _exists(ctx, check_button):
        app.updates.check = {}
        app.jobs.error = ''
        ctx.item_click(check_button)
        for _ in range(1200):                       # up to the network timeout
            ctx.yield_()
            if app.updates.check or app.jobs.error:
                break
        report = (app.updates.check or {}).get('report') or {}
        recorder.check('the release check is accepted and answered',
                       bool(app.updates.check) and 'lacks operation permissions' not in app.jobs.error,
                       app.jobs.error or report)
        recorder.check('the release check names the repository and says what it found',
                       report.get('repository') == 'MrMybal/CyTools_MeshStudio' and bool(report.get('message')),
                       report)

    # --- the workflow editor: add a step, then remove it
    app.select_tab('Workflows')
    wait(ctx, 3)
    add = f"**/{app.tr('Add step')}"
    if _exists(ctx, add):
        before = len(app.workflows.document['steps'])
        ctx.item_click(add)
        wait(ctx, 3)
        recorder.check('Add step adds a step',
                       len(app.workflows.document['steps']) == before + 1,
                       len(app.workflows.document['steps']))
        remove = f"**/{app.tr('Remove')}"
        if _exists(ctx, remove):
            ctx.item_click(remove)
            wait(ctx, 3)
            recorder.check('Remove takes it away',
                           len(app.workflows.document['steps']) == before,
                           len(app.workflows.document['steps']))
    else:
        recorder.check('Add step button exists', False, add)

    # --- the LocalMesh+ workflow: its texturing step takes three inputs from three steps, and
    #     the editor must show and let the user change the two extra ones.
    app.workflows.refresh()
    wanted = next((item for item in app.workflows.workflows
                   if item.get('name') == 'Image to production mesh (LocalMesh+)'), None)
    recorder.check('the LocalMesh+ workflow is listed', wanted is not None,
                   [item.get('name') for item in app.workflows.workflows])
    if wanted is not None:
        entry = f"**/{wanted.get('name')} ({wanted.get('stepCount', 0)})"
        if _exists(ctx, entry):
            ctx.item_click(entry)
        else:
            app.workflows._load(wanted)
        wait(ctx, 3)
        steps = app.workflows.document['steps']
        texture = next((step for step in steps if step['operation'] == 'texture_mesh'), {})
        recorder.check('its texturing step carries two extra inputs',
                       len(texture.get('extra_inputs') or []) == 2, texture.get('extra_inputs'))
        position = next((index for index, step in enumerate(steps)
                         if step['operation'] == 'texture_mesh'), 0) + 1
        header = f"**/{position}. {app.tr(app.operation('texture_mesh')['name'])}"
        if _exists(ctx, header):
            ctx.item_open(header)
            wait(ctx, 4)
            extra = '**/###extra-inputs'
            if _exists(ctx, extra):
                ctx.item_open(extra)
                wait(ctx, 4)
            recorder.check('the extra inputs are editable in the step',
                           _exists(ctx, f"**/{app.tr('Add an input')}"), extra)
        else:
            recorder.check('the texturing step header exists', False, header)

        # Run must always answer. The scheduler once refused this workflow (it reserved 24 GiB
        # for an unticked optional step) and the panel showed nothing. With a picture that does
        # not exist the job is accepted, then fails on the file before any model is loaded — so
        # the message proves both that the reservation fits and that the error is on screen.
        if _exists(ctx, header):
            ctx.item_close(header)          # an open step pushes Run out of the view
            wait(ctx, 4)
        app.jobs.error = ''
        app.workflows.input_folder = ''
        app.workflows.input_file = 'D:/no-such-folder/no-such-picture.png'
        run = f"**/{app.tr('Run the workflow')}"
        if _exists(ctx, run):
            ctx.item_click(run)
            for _ in range(240):
                ctx.yield_()
                if not app.jobs.is_running('run_workflow') and app.workflows.shown_error:
                    break
            shown = app.workflows.shown_error
            recorder.check('Run answers with a visible message', bool(shown), shown)
            recorder.check('the workflow was accepted by the scheduler',
                           'No GPU fits' not in shown and 'InsufficientVRAM' not in shown, shown)
            recorder.check('the message names the missing picture',
                           'no-such-picture.png' in shown, shown)
        else:
            recorder.check('the Run button exists', False, run)
        app.workflows.input_file = ''
        app.jobs.error = ''

    # --- every saved workflow opens in the editor, and a workflow that takes the files of a
    #     folder together (four photographs of one subject) shows it and keeps it when run
    for item in list(app.workflows.workflows):
        entry = f"**/{item.get('name')} ({item.get('stepCount', 0)})"
        if _exists(ctx, entry):
            ctx.item_click(entry)
        else:
            app.workflows._load(item)
        wait(ctx, 2)
        recorder.check(f'workflow "{item.get("name")}" opens in the editor',
                       app.workflows.document.get('name') == item.get('name')
                       and len(app.workflows.document['steps']) == item.get('stepCount'),
                       app.workflows.document.get('name'))
    together = next((item for item in app.workflows.workflows
                     if item.get('input_mode') == 'together'), None)
    recorder.check('a saved workflow takes its folder together', together is not None,
                   [item.get('input_mode') for item in app.workflows.workflows])
    if together is not None:
        entry = f"**/{together.get('name')} ({together.get('stepCount', 0)})"
        if _exists(ctx, entry):
            ctx.item_click(entry)
        else:
            app.workflows._load(together)
        wait(ctx, 3)
        combo = _combo(app.tr('Files of the folder'))
        recorder.check('the folder mode is shown with the workflow',
                       combo is not None and _exists(ctx, combo)
                       and app.workflows.document.get('input_mode') == 'together',
                       app.workflows.document.get('input_mode'))
        if combo is not None and _exists(ctx, combo):
            # a real click on the selector, then on the other choice, changes the document
            for wanted_mode, choice in (('each', 'One run per file'),
                                        ('together', 'All files together, as the views of one subject')):
                ctx.item_click(_combo(app.tr('Files of the folder')))
                wait(ctx, 3)
                item = f"**/{app.tr(choice)}"
                if _exists(ctx, item):
                    ctx.item_click(item)
                    wait(ctx, 3)
                ctx.popup_close_all()
                wait(ctx, 2)
                recorder.check(f'choosing "{choice}" sets the workflow to {wanted_mode}',
                               app.workflows.document.get('input_mode') == wanted_mode,
                               app.workflows.document.get('input_mode'))
        recorder.check('the document sent to Run keeps the folder mode',
                       app.workflows._document().get('input_mode') == 'together',
                       app.workflows._document().get('input_mode'))

    # --- the tabs the façade owns: they draw their content only when selected, so they had
    #     never been exercised either. Advanced operations builds a form for every operation.
    import ui_common

    for name in ('3D Viewer', 'Application log', 'Advanced operations', 'Options'):
        ref = f'**/{ui_common.label(name)}'
        if not _exists(ctx, ref):
            recorder.check(f'facade tab {name} exists', False, ref)
            continue
        ctx.item_click(ref)
        wait(ctx, 5)
        recorder.check(f'facade tab {name} drawn without crashing', True, '')
    app.select_tab('Tools')
    wait(ctx, 3)

    # --- the installation tab reads diagnose
    app.select_tab('Installation')
    wait(ctx, 4)
    refresh = f"**/{app.tr('Refresh')}"
    if _exists(ctx, refresh):
        ctx.item_click(refresh)
        wait(ctx, 6)
    recorder.check('installation reports the engines', bool(app.models.engines),
                   list(app.models.engines))
    recorder.check('installation reports the models', len(app.models.models) > 0,
                   len(app.models.models))
    # A model that is declared but absent must offer its installation, and a file whose licence
    # is accepted in person must show its page and its import button rather than a dead row.
    installable = [item for item in app.models.models if item.get('installable')]
    recorder.check('an installable model is listed', bool(installable),
                   [item['id'] for item in app.models.models])
    manual = [entry for item in app.models.models
              for entry in item.get('manualFiles') or [] if not entry.get('present')]
    if manual:
        button = f"**/{app.tr('Import the file...')}"
        recorder.check('the licensed file offers its import button', _exists(ctx, button), button)
        recorder.check('the licensed file names its page',
                       all(entry.get('page') for entry in manual),
                       [entry['target'] for entry in manual])
