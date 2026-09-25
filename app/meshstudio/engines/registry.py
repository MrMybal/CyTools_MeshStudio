"""Read app/engines.json and report the state of each engine environment.

Nothing here installs anything: installation is app/setup_engine.py, driven by the
``install_engine`` operation or the command line. No torch import ever happens in the
application process.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from ..paths import APP, ROOT, RUNTIME

SPEC_PATH = APP / 'engines.json'
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def spec():
    return json.loads(SPEC_PATH.read_text('utf-8-sig'))


def engine_names():
    return list(spec()['engines'])


def engine_for_backend(backend_id):
    for name, item in spec()['engines'].items():
        if backend_id in item.get('backends', []):
            return name
    return None


def engine_root(name):
    return ROOT / spec()['engines'][name]['directory']


def engine_python(name):
    root = engine_root(name)
    return root / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')


def source_path(source_name):
    return RUNTIME / 'sources' / source_name


def receipt(name):
    path = engine_root(name) / 'cytools-engine.json'
    try:
        return json.loads(path.read_text('utf-8'))
    except (OSError, ValueError):
        return None


def sources_status(name):
    """Presence and revision of every upstream checkout the engine needs."""
    result = {}
    for source, item in spec()['engines'][name].get('sources', {}).items():
        target = source_path(source)
        head = ''
        if (target / '.git').is_dir():
            head = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True,
                                  text=True, creationflags=_NO_WINDOW).stdout.strip()
        present = (target / item['requiredFile']).is_file()
        result[source] = {'present': present, 'revision': head, 'expected': item['revision'],
                          'license': item.get('license', ''), 'directory': str(target),
                          'ok': present and (head == item['revision'] or not head)}
    return result


def natives_status(name):
    """Presence of the native programs the engine drives (AutoRemesher, QuadWild)."""
    result = {}
    for native, item in spec()['engines'][name].get('natives', {}).items():
        directory = ROOT / item['directory']
        executable = directory / item['requiredFile']
        result[native] = {'present': executable.is_file(), 'executable': str(executable),
                          'directory': str(directory), 'label': item.get('label', native),
                          'license': item.get('license', ''), 'url': item.get('url', ''),
                          'ok': executable.is_file()}
    return result


def status(name):
    item = spec()['engines'][name]
    python = engine_python(name)
    report = receipt(name)
    sources = sources_status(name)
    natives = natives_status(name)
    installed = python.exists() and report is not None and all(s['ok'] for s in sources.values())
    state = 'Installed' if installed else 'Partial' if python.exists() else 'NotInstalled'
    return {'engine': name, 'label': item['label'], 'state': state, 'installed': installed,
            'python': str(python), 'pythonExists': python.exists(), 'report': report,
            'sources': sources, 'natives': natives, 'backends': item.get('backends', []),
            'pythonVersion': item.get('python', ''), 'estimatedBytes': item.get('estimatedBytes', 0),
            'cuda': bool(report and report.get('cuda')), 'device': (report or {}).get('device', ''),
            'torch': (report or {}).get('torch', ''), 'note': item.get('verificationNote', '')}


def status_all():
    return {name: status(name) for name in engine_names()}


def native_executable(backend_id, native_id=None):
    """Absolute path of a native program, or None when it is not installed."""
    name = engine_for_backend(backend_id)
    if name is None:
        return None
    natives = spec()['engines'][name].get('natives', {})
    item = natives.get(native_id or backend_id)
    if not item:
        return None
    candidate = ROOT / item['directory'] / item['requiredFile']
    return candidate if candidate.is_file() else None


def model_layout_root(name):
    layout = spec()['engines'][name].get('modelLayout')
    return (ROOT / layout['root']) if layout else None


def ensure_model_layout(name):
    """Give this engine the model folder names its upstream code expects.

    One canonical copy of every model lives in data/models under its catalogue id. An engine
    that hardcodes upstream names gets a directory of junctions (Windows) or symlinks (POSIX)
    pointing at those folders, created on demand. Nothing is copied, nothing is renamed, and a
    link whose target is missing is reported instead of silently left dangling.
    """
    layout = spec()['engines'][name].get('modelLayout')
    if not layout:
        return {}
    root = ROOT / layout['root']
    report = {}
    for relative, target in layout['links'].items():
        link = root / relative
        destination = ROOT / target
        state = 'Linked'
        if not destination.exists():
            state = 'TargetMissing'
        elif link.is_symlink() or (sys.platform == 'win32' and link.is_dir() and _is_junction(link)):
            state = 'Linked'
        elif link.exists():
            state = 'Occupied'  # a real folder is already there; leave the user's data alone
        else:
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                if sys.platform == 'win32':
                    # A junction needs no privilege, unlike a symlink outside Developer Mode.
                    subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(destination)],
                                   check=True, capture_output=True, creationflags=_NO_WINDOW)
                else:
                    link.symlink_to(destination, target_is_directory=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                state = f'Failed: {exc}'
        report[relative] = {'link': str(link), 'target': str(destination), 'state': state}
    return report


def _is_junction(path):
    try:
        return bool(path.stat(follow_symlinks=False).st_reparse_tag)
    except (OSError, AttributeError, ValueError):
        return False


def layout_environment(name):
    """Environment variables an engine needs to find its model layout."""
    layout = spec()['engines'][name].get('modelLayout')
    if not layout:
        return {}
    root = str(ROOT / layout['root'])
    return {key: value.replace('{root}', root).replace('/', os.sep)
            for key, value in (layout.get('env') or {}).items()}


def base_environment():
    """Environment for a worker running on the light application interpreter."""
    env = dict(os.environ)
    env.update({'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1'})
    env['PYTHONPATH'] = str(APP) + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    return env


def worker_environment(name):
    """Variables for a worker of this engine: offline caches, sources on the path."""
    env = dict(os.environ)
    env.update({'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1', 'HF_HUB_OFFLINE': '1',
                'TRANSFORMERS_OFFLINE': '1', 'DIFFUSERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
                'TOKENIZERS_PARALLELISM': 'false', 'HF_HOME': str(RUNTIME / 'huggingface'),
                'MESHSTUDIO_MODELS': str(ROOT / 'data' / 'models')})
    paths = [str(source_path(source)) for source in spec()['engines'][name].get('sources', {})
             if source not in spec()['engines'][name].get('installSources', [])]
    paths.append(str(APP))
    env['PYTHONPATH'] = os.pathsep.join(paths + ([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    ensure_model_layout(name)
    env.update(layout_environment(name))
    return env


def require(name):
    """Raise a CyToolError when the engine cannot run a job."""
    from cytools_core import CyToolError
    info = status(name)
    if not info['installed']:
        missing = [key for key, value in info['sources'].items() if not value['ok']]
        raise CyToolError(
            'MissingDependency',
            f'Engine "{name}" is not installed. Open Installation > Engines, '
            f'or run: python app/setup_engine.py {name}',
            recoverable=True,
            details={'engine': name, 'state': info['state'], 'missingSources': missing})
    return info


def require_native(backend_id, native_id=None):
    """Raise a CyToolError when a native program the backend drives is missing."""
    from cytools_core import CyToolError
    path = native_executable(backend_id, native_id)
    if path is None:
        raise CyToolError('MissingDependency',
                          f'The native program of backend "{backend_id}" is not installed. '
                          f'Open Installation > Engines to restore it.',
                          recoverable=True, details={'backend': backend_id})
    return path
