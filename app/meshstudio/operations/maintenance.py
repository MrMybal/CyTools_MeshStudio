"""Diagnostics, the model catalogue and engine installation."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from cytools_core import CyToolError

from ..paths import APP, ROOT, MODELS, LOGS
from ..engines import registry as engines
from ..backends import registry as backends

CATALOG = APP / 'models' / 'catalog.json'
INSTALL_PLAN = APP / 'models' / 'install.json'


def catalogue():
    try:
        return json.loads(CATALOG.read_text('utf-8'))
    except (OSError, ValueError):
        return {'schemaVersion': 1, 'models': [], 'totalBytes': 0}


def install_plans():
    """What an absent model needs to become installable, when that is known."""
    try:
        return json.loads(INSTALL_PLAN.read_text('utf-8'))['models']
    except (OSError, ValueError, KeyError):
        return {}


def plan_files(plan):
    """(required file, label) for every file the plan is supposed to leave on disk."""
    for item in plan.get('items', []):
        if item.get('optional'):
            continue
        if item['kind'] == 'gdrive-tar':
            for name in item.get('provides', []):
                yield f'{item["target"]}/{name}', item['label']
        elif item['kind'] == 'huggingface':
            base = item.get('target', '.').strip('/')
            for entry in item['files']:
                yield (f'{base}/{entry["path"]}' if base not in ('', '.') else entry['path']), item['label']
        else:
            yield item['target'], item['label']


def model_state(item, plan=None):
    """Installed, partial or missing, decided from the files on disk.

    The catalogue records what was found the day it was built, so a model that was never
    installed has nothing to check. Its install plan does list the files it needs, and those
    are what decides the state here: a half-downloaded model must not read as ready.
    """
    directory = ROOT / item['directory']
    if not directory.is_dir():
        return 'NotInstalled', [name for name, _ in plan_files(plan or {})]
    missing = []
    for check in item.get('verify', []):
        path = directory / check['path']
        if not path.is_file():
            missing.append(check['path'])
        elif check.get('sizeBytes') and path.stat().st_size != check['sizeBytes']:
            missing.append(check['path'] + ' (wrong size)')
    for name, _label in plan_files(plan or {}):
        if not (directory / name).is_file() and name not in missing:
            missing.append(name)
    if missing and not any((directory / name).is_file() for name, _ in plan_files(plan or {})) \
            and not item.get('verify'):
        return 'NotInstalled', missing
    return ('Installed' if not missing else 'Partial'), missing


def register(runtime, services):
    def list_models(context, parameters):
        data = catalogue()
        plans = install_plans()
        family = (parameters.get('family') or '').strip().lower()
        installed_only = bool(parameters.get('installed_only'))
        rows, total = [], 0
        for item in data['models']:
            if family and item['family'].lower() != family:
                continue
            plan = plans.get(item['id'])
            state, missing = model_state(item, plan)
            if installed_only and state != 'Installed':
                continue
            total += item['sizeBytes']
            directory = ROOT / item['directory']
            manual = [{'target': entry['target'], 'label': entry['label'],
                       'page': entry.get('page', ''), 'note': entry.get('note', ''),
                       'accepts': entry.get('accepts', []),
                       'present': (directory / entry['target']).is_file()}
                      for entry in (plan or {}).get('items', []) if entry['kind'] == 'manual']
            rows.append({'id': item['id'], 'name': item['name'], 'family': item['family'],
                         'engine': item['engine'], 'backends': item['backends'], 'state': state,
                         'missingFiles': missing, 'sizeBytes': item['sizeBytes'],
                         'revision': item['revision'], 'license': item['license'],
                         'nonCommercial': item['nonCommercial'], 'gated': item['source']['gated'],
                         'source': item['source']['url'], 'required': item['required'],
                         'purpose': item['purpose'], 'directory': str(directory),
                         'installable': plan is not None, 'manualFiles': manual})
        return {'models': rows, 'totalBytes': total, 'directory': str(MODELS)}

    def diagnose(context, parameters):
        wanted = (parameters.get('engine') or '').strip()
        warnings = []
        engine_status = engines.status_all()
        if wanted:
            engine_status = {key: value for key, value in engine_status.items() if key == wanted}
            if not engine_status:
                raise CyToolError('InvalidParameters', f'Unknown engine "{wanted}"')

        catalog_rows = list_models(context, {})['models']
        by_id = {row['id']: row for row in catalog_rows}

        backend_rows = []
        for backend in backends.BACKENDS.values():
            if wanted and backend.engine != wanted:
                continue
            state = engine_status.get(backend.engine) or engines.status(backend.engine)
            missing_models = [model for model in backend.models
                              if by_id.get(model, {}).get('state') != 'Installed']
            script = backend.worker_script()
            ready = state['installed'] and not missing_models and script.is_file()
            backend_rows.append({
                'id': backend.id, 'label': backend.label, 'engine': backend.engine,
                'engineState': state['state'], 'ready': ready,
                'worker': str(script), 'workerPresent': script.is_file(),
                'models': list(backend.models), 'missingModels': missing_models,
                'natives': [state['natives'][name] for name in backend.natives
                            if name in state.get('natives', {})],
                'device': 'CPU' if backend.engine == 'geometry' else 'CUDA',
                'note': backend.note})
            if not script.is_file():
                warnings.append(f'Backend "{backend.id}" has no worker script yet: {script.name}')

        natives = {}
        for name, info in engine_status.items():
            natives.update(info.get('natives') or {})
            if info['state'] != 'Installed':
                warnings.append(f'Engine "{name}" is {info["state"].lower()}.')

        report = {'engines': engine_status, 'backends': backend_rows, 'models': catalog_rows,
                  'natives': natives, 'warnings': warnings,
                  'platform': {'os': platform.platform(), 'python': sys.version.split()[0],
                               'machine': platform.machine(), 'cpuCount': os.cpu_count(),
                               'dataRoot': str(ROOT / 'data'), 'modelsBytes': catalogue()['totalBytes']}}

        if parameters.get('deep'):
            for name, info in engine_status.items():
                if not info['installed']:
                    continue
                context.cancellation.check()
                probe = subprocess.run(
                    [info['python'], '-c',
                     'import json,sys;d={"python":sys.version.split()[0]}\n'
                     'try:\n import torch;d["torch"]=torch.__version__;d["cuda"]=torch.cuda.is_available();'
                     'd["device"]=torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"\n'
                     'except Exception as exc: d["torch"]=""\n'
                     'print(json.dumps(d))'],
                    capture_output=True, text=True,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0)
                try:
                    info['live'] = json.loads(probe.stdout.strip().splitlines()[-1])
                except (ValueError, IndexError):
                    info['live'] = {'error': probe.stderr[-500:]}
        return report

    def install_engine(context, parameters):
        name = parameters['engine']
        if name not in engines.spec()['engines']:
            raise CyToolError('InvalidParameters', f'Unknown engine "{name}"')
        before = engines.status(name)
        if before['installed'] and not parameters.get('repair') and not parameters.get('sources_only'):
            return {'engine': name, 'state': 'Installed', 'python': before['python'],
                    'torch': before['torch'], 'cuda': before['cuda'], 'seconds': 0.0,
                    'sources': before['sources'], 'log_file': '',
                    'warnings': ['Already installed; pass repair=true to reinstall.']}

        LOGS.mkdir(parents=True, exist_ok=True)
        log_path = LOGS / f'install-{name}-{time.strftime("%Y%m%d-%H%M%S")}.log'
        argv = [sys.executable, str(APP / 'setup_engine.py'), name]
        if parameters.get('device') == 'cpu':
            argv.append('--cpu-only')
        if parameters.get('sources_only'):
            argv.append('--sources-only')

        context.progress(2, currentStep='Starting', statusMessage=f'Installing engine "{name}"')
        started = time.monotonic()
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen(argv, cwd=str(ROOT), stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                       errors='replace', bufsize=1,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0)
            percent = 5.0
            for line in process.stdout:
                log.write(line)
                log.flush()
                line = line.strip()
                if not line:
                    continue
                percent = min(95.0, percent + 0.4)
                context.progress(percent, currentStep='Installing', statusMessage=line[:200])
                try:
                    context.cancellation.check()
                except CyToolError:
                    process.terminate()
                    process.wait(timeout=30)
                    raise
            code = process.wait()
        seconds = round(time.monotonic() - started, 2)
        after = engines.status(name)
        if code != 0:
            raise CyToolError('InstallationFailed',
                              f'The installation of engine "{name}" failed (code {code}). See {log_path}',
                              recoverable=True, details={'log': str(log_path), 'engine': name})
        context.progress(100, currentStep='Done', statusMessage=after['state'])
        return {'engine': name, 'state': after['state'], 'python': after['python'],
                'torch': after['torch'], 'cuda': after['cuda'], 'seconds': seconds,
                'sources': after['sources'], 'log_file': str(log_path),
                'warnings': [] if after['installed'] else ['The engine is still not reported as installed.']}

    def install_model(context, parameters):
        name = parameters['model']
        plans = install_plans()
        plan = plans.get(name)
        if plan is None:
            raise CyToolError('InvalidParameters',
                              f'No install plan for model "{name}". Installable models: '
                              f'{", ".join(sorted(plans)) or "none"}',
                              details={'installable': sorted(plans)})
        row = next((item for item in catalogue()['models'] if item['id'] == name), None)
        before = model_state(row, plan)[0] if row else 'NotInstalled'
        if before == 'Installed' and not parameters.get('repair'):
            return {'model': name, 'state': before, 'directory': str(ROOT / plan['directory']),
                    'missingFiles': [], 'manualFiles': [], 'seconds': 0.0, 'log_file': '',
                    'warnings': ['Already installed; pass repair=true to download it again.']}

        LOGS.mkdir(parents=True, exist_ok=True)
        log_path = LOGS / f'install-model-{name}-{time.strftime("%Y%m%d-%H%M%S")}.log'
        argv = [sys.executable, str(APP / 'scripts' / 'install_model.py'), name]
        if parameters.get('repair'):
            argv.append('--repair')
        if parameters.get('skip_optional'):
            argv.append('--skip-optional')

        context.progress(2, currentStep='Starting', statusMessage=f'Installing model "{name}"')
        started = time.monotonic()
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen(argv, cwd=str(ROOT), stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                       errors='replace', bufsize=1,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0)
            percent = 5.0
            for line in process.stdout:
                log.write(line)
                log.flush()
                line = line.strip()
                if not line:
                    continue
                # gdown redraws one progress line; keep the percentage it prints when there is one.
                percent = min(95.0, percent + 0.5)
                context.progress(percent, currentStep='Downloading', statusMessage=line[:200])
                try:
                    context.cancellation.check()
                except CyToolError:
                    process.terminate()
                    process.wait(timeout=30)
                    raise
            code = process.wait()
        seconds = round(time.monotonic() - started, 2)
        if code != 0:
            raise CyToolError('InstallationFailed',
                              f'The installation of model "{name}" failed (code {code}). '
                              f'See {log_path}', recoverable=True,
                              details={'log': str(log_path), 'model': name})
        rows = list_models(context, {})['models']
        after = next((row for row in rows if row['id'] == name), None) or {}
        pending = [entry for entry in after.get('manualFiles', []) if not entry['present']]
        context.progress(100, currentStep='Done', statusMessage=after.get('state', 'Unknown'))
        return {'model': name, 'state': after.get('state', 'Unknown'),
                'directory': str(ROOT / plan['directory']),
                'missingFiles': after.get('missingFiles', []), 'manualFiles': pending,
                'seconds': seconds, 'log_file': str(log_path),
                'warnings': [f'{entry["label"]} must be accepted and downloaded from '
                             f'{entry["page"]}, then imported here.' for entry in pending]}

    def import_model_file(context, parameters):
        """Put in place a file whose licence the user accepted on its own page.

        The application never asks for those credentials; it takes the file the user already
        downloaded, checks it really is that file, copies it in and records its hash.
        """
        import shutil
        import zipfile

        name = parameters['model']
        plan = install_plans().get(name)
        if plan is None:
            raise CyToolError('InvalidParameters', f'No install plan for model "{name}"')
        wanted = (parameters.get('target') or '').replace('\\', '/')
        manual = [entry for entry in plan['items'] if entry['kind'] == 'manual']
        entry = next((item for item in manual if item['target'] == wanted),
                     manual[0] if len(manual) == 1 and not wanted else None)
        if entry is None:
            raise CyToolError('InvalidParameters',
                              f'Unknown file to import for "{name}". Expected one of: '
                              f'{", ".join(item["target"] for item in manual)}')

        source = Path(parameters['file']).expanduser()
        if not source.is_file():
            raise CyToolError('MissingInput', f'File not found: {source}', recoverable=True)
        accepts = [suffix.lower() for suffix in entry.get('accepts', [])]
        if accepts and source.suffix.lower() not in accepts:
            raise CyToolError('InvalidInput',
                              f'Unsupported file for "{entry["label"]}": {source.suffix}. '
                              f'Expected one of {", ".join(accepts)}')
        limit = int(entry.get('maxBytes') or 512 * 1024 ** 2)

        directory = ROOT / plan['directory']
        target = directory / entry['target']
        target.parent.mkdir(parents=True, exist_ok=True)
        staged = target.with_name(target.name + '.partial')
        context.progress(10, currentStep='Reading', statusMessage=source.name)
        if zipfile.is_zipfile(source):
            names = entry.get('archiveNames') or [Path(entry['target']).name]
            with zipfile.ZipFile(source) as bundle:
                candidates = [info for info in bundle.infolist()
                              if Path(info.filename).name in names and not info.is_dir()]
                if len(candidates) != 1:
                    raise CyToolError('InvalidInput',
                                      f'The archive should contain exactly one of '
                                      f'{", ".join(names)}; it contains {len(candidates)}.')
                if candidates[0].file_size > limit:
                    raise CyToolError('InvalidInput', 'The file inside the archive is too large.')
                with bundle.open(candidates[0]) as reader, staged.open('wb') as sink:
                    shutil.copyfileobj(reader, sink)
        else:
            if source.stat().st_size > limit:
                raise CyToolError('InvalidInput', f'{source.name} is larger than expected.')
            shutil.copy2(source, staged)

        context.progress(70, currentStep='Verifying', statusMessage=entry['label'])
        sys.path.insert(0, str(APP / 'scripts'))
        try:
            import install_model as installer
            installer.verify_binary(staged)
            staged.replace(target)
            installer.record(directory, target)
        except ValueError as exc:
            staged.unlink(missing_ok=True)
            raise CyToolError('InvalidInput', str(exc)) from exc
        finally:
            if str(APP / 'scripts') in sys.path:
                sys.path.remove(str(APP / 'scripts'))

        rows = list_models(context, {})['models']
        after = next((row for row in rows if row['id'] == name), {})
        context.progress(100, currentStep='Done', statusMessage=after.get('state', 'Unknown'))
        return {'model': name, 'file': str(target), 'sizeBytes': target.stat().st_size,
                'state': after.get('state', 'Unknown'),
                'missingFiles': after.get('missingFiles', [])}

    def _updater():
        if str(APP) not in sys.path:
            sys.path.insert(0, str(APP))
        import updates
        return updates

    def _update_error(exc):
        module = _updater()
        if isinstance(exc, module.UpdateError):
            return CyToolError('UpdateRefused', str(exc), recoverable=True)
        return CyToolError('UpdateFailed', f'{type(exc).__name__}: {exc}', recoverable=True)

    def update_status(context, parameters):
        """Where the three streams stand, without touching the network."""
        module = _updater()
        updater = module.Updater(ROOT)
        history = updater.history()
        return {'application': {'version': history['current'],
                                'repository': updater.repository(),
                                'checkAutomatically': bool(updater.settings().get('checkAutomatically'))},
                'pending': history['pending'], 'lastApplied': history['lastApplied'],
                'staged': history['staged'], 'backups': history['backups'],
                'engines': updater.check('engines')['engines'],
                'models': updater.check('models')['models']}

    def check_update(context, parameters):
        module = _updater()
        updater = module.Updater(ROOT)
        stream = (parameters.get('stream') or 'application').strip()
        if parameters.get('repository'):
            updater.save_settings({'applicationRepository': str(parameters['repository']).strip()})
        release = None
        if parameters.get('release_file'):
            path = Path(parameters['release_file']).expanduser()
            if not path.is_file():
                raise CyToolError('MissingInput', f'Release description not found: {path}')
            release = json.loads(path.read_text('utf-8'))
        context.progress(20, currentStep='Checking', statusMessage=stream)
        try:
            answer = updater.check(stream, release=release) if stream == 'application' \
                else updater.check(stream)
        except Exception as exc:  # noqa: BLE001
            raise _update_error(exc) from exc
        context.progress(100, currentStep='Done', statusMessage=answer.get('latest', stream))
        return {'stream': stream, 'report': answer,
                'message': str(answer.get('message', '')),
                'updateAvailable': bool(answer.get('newer'))}

    def stage_update(context, parameters):
        module = _updater()
        updater = module.Updater(ROOT)
        source = str(parameters.get('source') or '').strip()
        if not source:
            raise CyToolError('MissingInput',
                              'Give the release asset to stage: its URL, or a local .zip.')
        context.progress(5, currentStep='Staging', statusMessage=source[:120])

        def note(percent, message):
            context.progress(float(percent), currentStep='Staging', statusMessage=str(message)[:200])
            context.cancellation.check()

        try:
            return updater.stage(source, expected_sha256=str(parameters.get('sha256') or ''),
                                 version=str(parameters.get('version') or ''), progress=note)
        except CyToolError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _update_error(exc) from exc

    def activate_update(context, parameters):
        module = _updater()
        updater = module.Updater(ROOT)
        staged = str(parameters.get('staged') or '').strip()
        if not staged:
            rows = updater.staged_list()
            if not rows:
                raise CyToolError('MissingInput', 'Nothing is staged; stage an update first.')
            staged = rows[0]['path']
        context.progress(30, currentStep='Verifying', statusMessage=staged)
        try:
            answer = updater.activate(staged)
        except Exception as exc:  # noqa: BLE001
            raise _update_error(exc) from exc
        context.progress(100, currentStep='Done',
                         statusMessage='Restart the application to apply it')
        return answer

    def rollback_update(context, parameters):
        module = _updater()
        updater = module.Updater(ROOT)
        try:
            if parameters.get('cancel'):
                return {'restartRequired': False, 'mode': 'cancel', 'pending': '',
                        'version': updater.current_version(), 'fromVersion': updater.current_version(),
                        **updater.cancel_pending()}
            return updater.rollback(str(parameters.get('backup') or ''))
        except Exception as exc:  # noqa: BLE001
            raise _update_error(exc) from exc

    runtime.register('list_models', list_models)
    runtime.register('diagnose', diagnose)
    runtime.register('update_status', update_status)
    runtime.register('check_update', check_update,
                     estimate=lambda parameters, backend, model: {'ramBytes': 256 * 1024 ** 2})
    runtime.register('stage_update', stage_update,
                     estimate=lambda parameters, backend, model: {'ramBytes': 512 * 1024 ** 2,
                                                                  'diskBytes': 1024 ** 3})
    runtime.register('activate_update', activate_update)
    runtime.register('rollback_update', rollback_update)
    runtime.register('install_model', install_model,
                     estimate=lambda parameters, backend, model: {
                         'ramBytes': 1 * 1024 ** 3, 'diskBytes': 8 * 1024 ** 3})
    runtime.register('import_model_file', import_model_file,
                     estimate=lambda parameters, backend, model: {
                         'ramBytes': 512 * 1024 ** 2, 'diskBytes': 512 * 1024 ** 2})
    registered = {'list_models': list_models, 'diagnose': diagnose,
                  'install_engine': install_engine, 'install_model': install_model,
                  'import_model_file': import_model_file, 'update_status': update_status,
                  'check_update': check_update, 'stage_update': stage_update,
                  'activate_update': activate_update, 'rollback_update': rollback_update}
    runtime.register('install_engine', install_engine,
                     estimate=lambda parameters, backend, model: {
                         'ramBytes': 2 * 1024 ** 3,
                         'diskBytes': engines.spec()['engines'].get(parameters.get('engine', ''), {})
                         .get('estimatedBytes', 8 * 1024 ** 3)})
    return registered
