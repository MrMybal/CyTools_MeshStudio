"""Exercise the update machinery on a fixture tree, without any network or GitHub account.

The staging, the verification, the activation, the swap performed at the next start and the
rollback all run here against a temporary root that looks like a delivered Tool. What is *not*
covered is the one call that needs the outside world: asking api.github.com for a real release.
That path is exercised with a release description read from a file, the same JSON GitHub
returns, so the parsing and the version comparison are tested while the HTTP request is not.

    runtime/python/Scripts/python.exe app/tests/test_updates.py
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from updates import UpdateError, Updater, version_tuple  # noqa: E402

PASSED, FAILED = [], []


def check(title, condition, detail=''):
    (PASSED if condition else FAILED).append(title)
    print(f'{"ok  " if condition else "FAIL"} {title}' + (f'  [{detail}]' if detail and not condition else ''))


def fake_app(folder, version, tool_id='cy.tool.meshstudio'):
    """The smallest tree the verification accepts as an app folder."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'CyTool.json').write_text(json.dumps(
        {'schemaVersion': 1, 'id': tool_id, 'name': 'CyTools_MeshStudio', 'version': version,
         'operations': [{'id': 'diagnose'}]}, indent=2), encoding='utf-8')
    for name in ('tool.py', 'desktop.py'):
        (folder / name).write_text(f'# {name} {version}\n', encoding='utf-8')
    for name in ('gui', 'meshstudio', 'workers'):
        (folder / name).mkdir(exist_ok=True)
        (folder / name / '__init__.py').write_text(f'VERSION = "{version}"\n', encoding='utf-8')
    return folder


def zip_of(folder, archive, prefix='app'):
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                bundle.write(path, f'{prefix}/{path.relative_to(folder).as_posix()}')
    return archive


def main():
    root = Path(tempfile.mkdtemp(prefix='meshstudio-updates-'))
    try:
        fake_app(root / 'app', '0.1.0')
        (root / 'data' / 'inputs').mkdir(parents=True)
        keepsake = root / 'data' / 'inputs' / 'mine.txt'
        keepsake.write_text('the user data nothing may touch', encoding='utf-8')
        (root / 'runtime').mkdir()
        updater = Updater(root)

        check('the current version is read from the manifest', updater.current_version() == '0.1.0',
              updater.current_version())
        check('versions compare as numbers', version_tuple('v0.2.0') > version_tuple('0.1.9'))

        # ---------------------------------------------------------------- staging
        newer = fake_app(root / 'build' / 'app', '0.2.0')
        archive = zip_of(newer, root / 'build' / 'update.zip')
        staged = updater.stage(str(archive), version='0.2.0')
        check('an archive is staged under runtime/updates',
              Path(staged['staged']).is_dir() and staged['version'] == '0.2.0', staged)
        check('the staged copy is verified as newer', staged['verified']['newer'])
        check('the running app is untouched by staging', updater.current_version() == '0.1.0')

        # a wrong digest is refused and nothing is left behind
        try:
            updater.stage(str(archive), expected_sha256='00' * 32, version='bad')
            check('a wrong SHA-256 is refused', False)
        except UpdateError as exc:
            check('a wrong SHA-256 is refused', 'SHA-256' in str(exc), str(exc))
        check('the refused update left no staging folder',
              not (updater.updates / 'application-bad').exists())

        # an archive carrying data/ is refused
        data_archive = root / 'build' / 'with-data.zip'
        with zipfile.ZipFile(data_archive, 'w') as bundle:
            bundle.writestr('app/CyTool.json', '{}')
            bundle.writestr('data/settings/updates.json', '{}')
        try:
            updater.stage(str(data_archive), version='withdata')
            check('an archive carrying data/ is refused', False)
        except UpdateError as exc:
            check('an archive carrying data/ is refused', 'data' in str(exc).lower(), str(exc))

        # an archive of another Tool is refused
        other = fake_app(root / 'build' / 'other', '9.9.9', tool_id='cy.tool.somethingelse')
        try:
            updater.stage(str(zip_of(other, root / 'build' / 'other.zip')), version='other')
            check('an archive of another Tool is refused', False)
        except UpdateError as exc:
            check('an archive of another Tool is refused', 'cy.tool.somethingelse' in str(exc), str(exc))

        # an incomplete tree is refused
        partial = root / 'build' / 'partial'
        partial.mkdir(parents=True)
        (partial / 'CyTool.json').write_text(json.dumps(
            {'id': 'cy.tool.meshstudio', 'version': '0.3.0'}), encoding='utf-8')
        try:
            updater.stage(str(zip_of(partial, root / 'build' / 'partial.zip')), version='partial')
            check('an incomplete update is refused', False)
        except UpdateError as exc:
            check('an incomplete update is refused', 'incomplete' in str(exc), str(exc))

        # ------------------------------------------------------------- activation
        answer = updater.activate(staged['staged'])
        check('activation only records a pending request',
              answer['restartRequired'] and updater.pending_file.is_file()
              and updater.current_version() == '0.1.0', answer)
        check('the pending request is listed', updater.history()['pending'] is not None)

        applied = updater.apply_pending(run_in_subprocess=False)
        check('the next start swaps the folders', applied['applied'], applied)
        check('the new version is in place', updater.current_version() == '0.2.0',
              updater.current_version())
        check('the previous version is kept as a backup', len(updater.backup_list()) == 1,
              updater.backup_list())
        check('the data folder came through untouched',
              keepsake.read_text('utf-8') == 'the user data nothing may touch')
        check('no pending request is left', not updater.pending_file.is_file())

        # --------------------------------------------------------------- rollback
        rollback = updater.rollback()
        check('a rollback is recorded for the next start',
              rollback['restartRequired'] and rollback['mode'] == 'rollback', rollback)
        applied = updater.apply_pending(run_in_subprocess=False)
        check('the rollback restores the previous version',
              applied['applied'] and updater.current_version() == '0.1.0',
              updater.current_version())
        check('the rolled-back version is itself kept as a backup',
              len(updater.backup_list()) == 2, updater.backup_list())
        check('the data folder survived the rollback too',
              keepsake.read_text('utf-8') == 'the user data nothing may touch')

        check('an applied update leaves no half-empty staging folder',
              not Path(staged['staged']).exists(), staged['staged'])

        # a cancelled request leaves the application where it is
        again = updater.stage(str(archive), version='0.2.0-again')
        updater.activate(again['staged'])
        cancelled = updater.cancel_pending()
        check('a pending request can be dropped',
              cancelled['cancelled'] and not updater.pending_file.is_file(), cancelled)
        check('dropping it changed no version', updater.current_version() == '0.1.0',
              updater.current_version())

        # ------------------------------------------------------------ github shape
        release = {'tag_name': 'v0.3.0', 'name': 'MeshStudio 0.3.0', 'body': 'Notes',
                   'published_at': '2026-01-01T00:00:00Z', 'html_url': 'https://example.invalid',
                   'assets': [{'name': 'notes.txt', 'size': 10,
                               'browser_download_url': 'https://example.invalid/notes.txt'},
                              {'name': 'CyTools_MeshStudio-app-0.3.0.zip', 'size': 1234,
                               'browser_download_url': 'https://example.invalid/app.zip'}]}
        report = updater.check('application', release=release)
        check('a release description is read and compared',
              report['latest'] == 'v0.3.0' and report['newer']
              and report['asset'].endswith('app.zip'), report)
        empty = updater.check('application', release={'tag_name': 'v0.0.1', 'assets': []})
        check('an older release is not offered as an update', not empty['newer'], empty)
        check('a release without a zip says so', 'no .zip asset' in empty.get('message', ''), empty)

        no_repository = Updater(root).check('application')
        check('without a repository the answer says so, and asks for nothing',
              no_repository['configured'] is False and 'No GitHub repository' in no_repository['message'],
              no_repository)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print(json.dumps({'passed': len(PASSED), 'failed': len(FAILED)}))
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
