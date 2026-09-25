"""Updates for the three streams: the application, the engines and the model weights.

They are kept apart on purpose. The application is a GitHub release of the ``app`` folder; an
engine is a private environment rebuilt from ``app/engines.json`` by the Installation tab; the
weights follow ``app/models/catalog.json`` and ``app/models/install.json``. They have different
versions, different licences, and different reasons to change, so one never drags the others.

Two rules hold everywhere in this file: ``data/`` is never read, replaced or removed by an
update, and nothing is activated before it has been verified on disk. Activation itself is a
directory rename decided here but performed at the next start, by ``--apply`` in a separate
process, so the folder holding the running code is never swapped underneath it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

ARCHIVE_LIMIT = 512 * 1024 ** 2
DOWNLOAD_TIMEOUT = 60
USER_AGENT = 'CyTools_MeshStudio updater'


def version_tuple(text):
    parts = []
    for chunk in str(text or '').lstrip('vV').replace('-', '.').split('.'):
        digits = ''.join(character for character in chunk if character.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) or (0,)


def sha256_of(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member(name):
    path = PurePosixPath(name.replace('\\', '/'))
    if not name or ':' in name or path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Unsafe path inside the archive: {name}')
    return path


class UpdateError(Exception):
    """Refused for a reason the interface can show as it is."""


class NoRelease(UpdateError):
    """GitHub has no release to offer: an answer of the check, not a failure of it."""


class Updater:
    def __init__(self, root):
        self.root = Path(root).resolve()

    # ------------------------------------------------------------------ places
    @property
    def app(self):
        return self.root / 'app'

    @property
    def updates(self):
        return self.root / 'runtime' / 'updates'

    @property
    def backups(self):
        return self.root / 'runtime' / 'backups'

    @property
    def settings_file(self):
        return self.root / 'data' / 'settings' / 'updates.json'

    @property
    def pending_file(self):
        return self.updates / 'pending.json'

    def settings(self):
        default = {'applicationRepository': '', 'checkAutomatically': False}
        try:
            return {**default, **json.loads(self.settings_file.read_text('utf-8'))}
        except (OSError, ValueError):
            return default

    def save_settings(self, values):
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(json.dumps({**self.settings(), **values}, indent=2),
                                      encoding='utf-8')

    def manifest(self, folder=None):
        path = (folder or self.app) / 'CyTool.json'
        return json.loads(path.read_text('utf-8'))

    def current_version(self):
        try:
            return str(self.manifest().get('version', '0.0.0'))
        except (OSError, ValueError):
            return '0.0.0'

    def repository(self):
        """The GitHub repository (owner/name) the application stream reads its releases from.

        What was typed in the Updates tab wins; otherwise the repository the manifest declares,
        so a fresh installation knows where its updates come from without any setting.
        """
        typed = str(self.settings().get('applicationRepository', '') or '').strip().strip('/')
        if typed:
            return typed
        try:
            return str(self.manifest().get('repository', '') or '').strip().strip('/')
        except (OSError, ValueError):
            return ''

    # ------------------------------------------------------------------ check
    def check(self, stream='application', release=None):
        """What the stream offers. ``release`` short-circuits the network, for tests."""
        if stream == 'application':
            return self._check_application(release)
        if stream == 'engines':
            return self._check_engines()
        if stream == 'models':
            return self._check_models()
        raise UpdateError(f'Unknown stream "{stream}"')

    def _check_application(self, release=None):
        current = self.current_version()
        repository = self.repository()
        answer = {'stream': 'application', 'current': current, 'configured': bool(repository),
                  'repository': repository, 'latest': '', 'newer': False, 'notes': '',
                  'asset': '', 'assetBytes': 0, 'published': '', 'url': ''}
        if release is None:
            if not repository:
                answer['message'] = ('No GitHub repository is configured for this Tool. '
                                     'Set owner/name in the Updates tab to check releases.')
                return answer
            try:
                release = self._fetch_release(repository)
            except NoRelease as exc:
                answer['message'] = str(exc)   # a repository with nothing published yet
                return answer
        answer['latest'] = str(release.get('tag_name') or release.get('name') or '')
        answer['notes'] = str(release.get('body') or '')[:4000]
        answer['published'] = str(release.get('published_at') or '')
        answer['url'] = str(release.get('html_url') or '')
        asset = self._pick_asset(release)
        if asset:
            answer['asset'] = str(asset.get('browser_download_url') or '')
            answer['assetBytes'] = int(asset.get('size') or 0)
            answer['assetName'] = str(asset.get('name') or '')
        answer['newer'] = version_tuple(answer['latest']) > version_tuple(current)
        if not answer['asset']:
            answer['message'] = ('The release carries no .zip asset holding the app folder; '
                                 'nothing can be staged from it.')
        return answer

    @staticmethod
    def _pick_asset(release):
        assets = [item for item in (release.get('assets') or [])
                  if str(item.get('name', '')).lower().endswith('.zip')]
        for item in assets:                       # a name mentioning the app folder wins
            if 'app' in str(item.get('name', '')).lower():
                return item
        return assets[0] if assets else None

    def _fetch_release(self, repository):
        url = f'https://api.github.com/repos/{repository}/releases/latest'
        request = urllib.request.Request(url, headers={
            'Accept': 'application/vnd.github+json', 'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as answer:
                payload = answer.read(4 * 1024 ** 2)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                # GitHub answers 404 both for a repository without a release and for a
                # private one, which anonymous requests cannot see at all.
                raise NoRelease(f'No published release found for {repository} — or the '
                                'repository is private, which anonymous requests cannot read.') from exc
            raise UpdateError(f'GitHub answered {exc.code} for {repository}.') from exc
        except urllib.error.URLError as exc:
            raise UpdateError(f'GitHub is unreachable: {exc.reason}') from exc
        return json.loads(payload.decode('utf-8'))

    def _check_engines(self):
        """Engines are rebuilt, not downloaded as releases: report what they pin."""
        rows = []
        try:
            spec = json.loads((self.app / 'engines.json').read_text('utf-8'))['engines']
        except (OSError, ValueError, KeyError):
            spec = {}
        for name, engine in spec.items():
            marker = self.root / 'runtime' / 'engines' / name / 'cytools-engine.json'
            installed = marker.is_file()
            sources = {key: value.get('revision', '') for key, value in
                       (engine.get('sources') or {}).items()}
            rows.append({'engine': name, 'installed': installed, 'sources': sources,
                         'python': engine.get('python', '')})
        return {'stream': 'engines', 'engines': rows,
                'message': 'An engine is updated by reinstalling it from the Installation tab, '
                           'which checks out the revision pinned in app/engines.json.'}

    def _check_models(self):
        try:
            catalogue = json.loads((self.app / 'models' / 'catalog.json').read_text('utf-8'))
        except (OSError, ValueError):
            catalogue = {'models': []}
        try:
            plans = json.loads((self.app / 'models' / 'install.json').read_text('utf-8'))['models']
        except (OSError, ValueError, KeyError):
            plans = {}
        rows = [{'id': item['id'], 'revision': item.get('revision'),
                 'installed': bool(item.get('installed')), 'installable': item['id'] in plans,
                 'license': item.get('license', '')} for item in catalogue.get('models', [])]
        return {'stream': 'models', 'models': rows,
                'message': 'Weights follow their own catalogue and are installed or repaired '
                           'from the Installation tab; an update never replaces data/.'}

    # ------------------------------------------------------------------ stage
    def stage(self, source, expected_sha256='', version='', stream='application', progress=None):
        """Download or copy an archive, verify it, and unpack it under runtime/updates."""
        note = progress or (lambda percent, message: None)
        self.updates.mkdir(parents=True, exist_ok=True)
        downloads = self.root / 'runtime' / 'downloads'
        downloads.mkdir(parents=True, exist_ok=True)

        source = str(source)
        archive = downloads / f'update-{stream}-{int(time.time())}.zip'
        if source.lower().startswith(('http://', 'https://')):
            note(5, f'Downloading {source}')
            self._download(source, archive)
        else:
            local = Path(source).expanduser()
            if not local.is_file():
                raise UpdateError(f'Update archive not found: {local}')
            note(5, f'Reading {local.name}')
            shutil.copy2(local, archive)

        digest = sha256_of(archive)
        if expected_sha256 and digest.lower() != expected_sha256.strip().lower():
            archive.unlink(missing_ok=True)
            raise UpdateError('The archive does not match the expected SHA-256; nothing staged.')
        note(40, 'Archive verified')

        staged = self.updates / f'{stream}-{version or digest[:12]}'
        if staged.exists():
            shutil.rmtree(staged)
        self._extract(archive, staged)
        note(80, 'Archive unpacked')

        report = self.verify(staged)
        receipt = {'stream': stream, 'source': source, 'sha256': digest,
                   'archiveBytes': archive.stat().st_size, 'stagedAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'version': report['version'], 'files': report['files']}
        (staged / 'staged.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        archive.unlink(missing_ok=True)
        note(100, f'Staged {report["version"]} in {staged}')
        return {'staged': str(staged), **receipt, 'verified': report}

    def _download(self, url, destination):
        request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as answer, \
                    destination.open('wb') as sink:
                total = 0
                while True:
                    chunk = answer.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > ARCHIVE_LIMIT:
                        raise UpdateError('The update archive is larger than expected.')
                    sink.write(chunk)
        except urllib.error.URLError as exc:
            destination.unlink(missing_ok=True)
            raise UpdateError(f'Download failed: {exc}') from exc

    def _extract(self, archive, destination):
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if sum(info.file_size for info in entries) > ARCHIVE_LIMIT:
                raise UpdateError('The unpacked update is larger than expected.')
            seen = set()
            for info in entries:
                path = safe_member(info.filename)
                key = str(path).lower()
                if key in seen:
                    raise UpdateError(f'Duplicate path in the archive: {info.filename}')
                seen.add(key)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise UpdateError('The archive contains a symbolic link, which is refused.')
                if path.parts and path.parts[0] == 'data':
                    raise UpdateError('The archive carries a data/ folder; an update never '
                                      'replaces your data.')
            bundle.extractall(destination)

    def verify(self, staged):
        """Everything checked before an activation is even offered."""
        staged = Path(staged)
        folder = staged / 'app' if (staged / 'app' / 'CyTool.json').is_file() else staged
        manifest_file = folder / 'CyTool.json'
        if not manifest_file.is_file():
            raise UpdateError('The staged update holds no app/CyTool.json.')
        try:
            manifest = json.loads(manifest_file.read_text('utf-8'))
        except ValueError as exc:
            raise UpdateError(f'The staged manifest is not readable: {exc}') from exc
        current = self.manifest()
        if manifest.get('id') != current.get('id'):
            raise UpdateError(f'The staged update is for "{manifest.get("id")}", not '
                              f'"{current.get("id")}".')
        if (staged / 'data').exists() or (folder / 'data').exists():
            raise UpdateError('The staged update carries a data/ folder; refused.')
        missing = [name for name in ('tool.py', 'desktop.py', 'gui', 'meshstudio', 'workers')
                   if not (folder / name).exists()]
        if missing:
            raise UpdateError('The staged update is incomplete, missing: ' + ', '.join(missing))
        files = sum(1 for _ in folder.rglob('*') if _.is_file())
        return {'root': str(folder), 'version': str(manifest.get('version', '0.0.0')),
                'id': manifest.get('id', ''), 'files': files,
                'newer': version_tuple(manifest.get('version')) > version_tuple(current.get('version')),
                'operations': len(manifest.get('operations') or [])}

    # --------------------------------------------------------------- activate
    def activate(self, staged):
        """Verify, then record the swap for the next start. Nothing is moved here."""
        report = self.verify(staged)
        self.updates.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), self.updates / 'apply.py')
        pending = {'mode': 'update', 'source': report['root'], 'version': report['version'],
                   'requestedAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'fromVersion': self.current_version()}
        self.pending_file.write_text(json.dumps(pending, indent=2), encoding='utf-8')
        return {'pending': str(self.pending_file), 'restartRequired': True, **pending,
                'verified': report}

    def rollback(self, backup=''):
        """Record the reverse swap; the next start restores that backup."""
        candidates = self.backup_list()
        if not candidates:
            raise UpdateError('No backup to restore; nothing was ever activated here.')
        chosen = Path(backup) if backup else Path(candidates[0]['path'])
        if not (chosen / 'CyTool.json').is_file():
            raise UpdateError(f'{chosen} does not hold an app folder.')
        self.updates.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), self.updates / 'apply.py')
        pending = {'mode': 'rollback', 'source': str(chosen),
                   'version': json.loads((chosen / 'CyTool.json').read_text('utf-8')).get('version', ''),
                   'requestedAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'fromVersion': self.current_version()}
        self.pending_file.write_text(json.dumps(pending, indent=2), encoding='utf-8')
        return {'pending': str(self.pending_file), 'restartRequired': True, **pending}

    def cancel_pending(self):
        existed = self.pending_file.is_file()
        self.pending_file.unlink(missing_ok=True)
        return {'cancelled': existed}

    # ------------------------------------------------------------------ apply
    def apply_pending(self, run_in_subprocess=True, python=None):
        """Called at start-up. The swap runs in another process, never in this one."""
        if not self.pending_file.is_file():
            return {'applied': False, 'reason': 'nothing pending'}
        if not run_in_subprocess:
            return self.swap()
        script = self.updates / 'apply.py'
        if not script.is_file():
            shutil.copy2(Path(__file__), script)
        argv = [str(python or sys.executable), str(script), '--apply', '--root', str(self.root)]
        finished = subprocess.run(argv, cwd=str(self.root), capture_output=True, text=True,
                                  encoding='utf-8', errors='replace',
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                                  if sys.platform == 'win32' else 0)
        return {'applied': finished.returncode == 0, 'code': finished.returncode,
                'output': (finished.stdout or '') + (finished.stderr or '')}

    def swap(self):
        """The rename itself: current app aside, the staged one in its place."""
        pending = json.loads(self.pending_file.read_text('utf-8'))
        source = Path(pending['source'])
        if not (source / 'CyTool.json').is_file():
            self.pending_file.unlink(missing_ok=True)
            raise UpdateError(f'The pending update source disappeared: {source}')
        self.backups.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S')
        backup = self.backups / f'app-{self.current_version()}-{stamp}'
        os.replace(self.app, backup)
        try:
            # A rollback restores a backup in place; an update consumes its staged copy.
            if pending.get('mode') == 'rollback':
                shutil.copytree(source, self.app)
            else:
                os.replace(source, self.app)
        except OSError:
            os.replace(backup, self.app)          # put the working app back, whatever happened
            raise
        if pending.get('mode') != 'rollback':
            # The staged folder gave its app away; what is left is its receipt.
            parent = source.parent
            if parent.is_dir() and parent.parent == self.updates \
                    and {item.name for item in parent.iterdir()} <= {'staged.json'}:
                shutil.rmtree(parent, ignore_errors=True)
        record = {**pending, 'appliedAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
                  'backup': str(backup), 'newVersion': self.current_version()}
        (self.updates / 'active.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        self.pending_file.unlink(missing_ok=True)
        self.prune_backups()
        return {'applied': True, **record}

    def prune_backups(self, keep=3):
        for entry in self.backup_list()[keep:]:
            shutil.rmtree(entry['path'], ignore_errors=True)

    def backup_list(self):
        if not self.backups.is_dir():
            return []
        rows = []
        for folder in self.backups.iterdir():
            if not (folder / 'CyTool.json').is_file():
                continue
            try:
                version = json.loads((folder / 'CyTool.json').read_text('utf-8')).get('version', '')
            except (OSError, ValueError):
                version = ''
            rows.append({'path': str(folder), 'version': version,
                         'savedAt': time.strftime('%Y-%m-%dT%H:%M:%S',
                                                  time.localtime(folder.stat().st_mtime))})
        return sorted(rows, key=lambda row: row['savedAt'], reverse=True)

    def staged_list(self):
        if not self.updates.is_dir():
            return []
        rows = []
        for folder in self.updates.iterdir():
            receipt = folder / 'staged.json'
            if not receipt.is_file():
                continue
            try:
                rows.append({'path': str(folder), **json.loads(receipt.read_text('utf-8'))})
            except ValueError:
                continue
        return sorted(rows, key=lambda row: row.get('stagedAt', ''), reverse=True)

    def history(self):
        pending = None
        if self.pending_file.is_file():
            try:
                pending = json.loads(self.pending_file.read_text('utf-8'))
            except ValueError:
                pending = None
        active = None
        if (self.updates / 'active.json').is_file():
            try:
                active = json.loads((self.updates / 'active.json').read_text('utf-8'))
            except ValueError:
                active = None
        return {'current': self.current_version(), 'pending': pending, 'lastApplied': active,
                'staged': self.staged_list(), 'backups': self.backup_list()}


def apply_at_startup(root, python=None):
    """Used by desktop.py and tool.py before anything of the application is imported."""
    try:
        updater = Updater(root)
        if not updater.pending_file.is_file():
            return None
        return updater.apply_pending(python=python)
    except Exception as exc:  # noqa: BLE001 - a failed update must never block the start
        return {'applied': False, 'error': str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Update helper for CyTools_MeshStudio')
    parser.add_argument('--apply', action='store_true', help='perform the pending swap')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    updater = Updater(args.root)
    if args.apply:
        print(json.dumps(updater.swap(), indent=2))
        return 0
    print(json.dumps(updater.history(), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
