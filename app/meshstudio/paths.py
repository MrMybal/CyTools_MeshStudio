"""Stable locations of the Tool's app/data/runtime folders. No side effects on import."""
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
DATA = ROOT / 'data'
RUNTIME = ROOT / 'runtime'

INPUTS = DATA / 'inputs'
MODELS = DATA / 'models'
JOBS = DATA / 'jobs'
SETTINGS = DATA / 'settings'
LOGS = DATA / 'logs'
REPORTS = DATA / 'reports'
WORKFLOWS = DATA / 'workflows'
PRESETS = DATA / 'presets'
LIBRARY = DATA / 'library'

ENGINES = RUNTIME / 'engines'
SOURCES = RUNTIME / 'sources'
DOWNLOADS = RUNTIME / 'downloads'
UPDATES = RUNTIME / 'updates'
BACKUPS = RUNTIME / 'backups'

DATA_FOLDERS = (INPUTS, MODELS, JOBS, SETTINGS, LOGS, REPORTS, WORKFLOWS, PRESETS, LIBRARY)


def base_python():
    """Interpreter of the light application environment (runtime/python).

    A developer's clone holds a virtual environment there (``Scripts/python.exe``); the binary
    release holds the embeddable distribution (``python.exe`` at the root of the folder).
    """
    if sys.platform == 'win32':
        candidates = (RUNTIME / 'python' / 'Scripts' / 'python.exe', RUNTIME / 'python' / 'python.exe')
    else:
        candidates = (RUNTIME / 'python' / 'bin' / 'python',)
    return next((item for item in candidates if item.exists()), Path(sys.executable))


def engine_python(name):
    """Interpreter of a heavy engine environment (runtime/engines/<name>)."""
    root = ENGINES / name
    if sys.platform == 'win32':
        return root / 'Scripts' / 'python.exe'
    return root / 'bin' / 'python'


def model_path(*parts):
    """Absolute path inside data/models."""
    return MODELS.joinpath(*parts)


def ensure_data_layout():
    for folder in DATA_FOLDERS:
        folder.mkdir(parents=True, exist_ok=True)
