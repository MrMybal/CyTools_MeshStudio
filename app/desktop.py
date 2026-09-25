"""Graphical entry point: the Dear ImGui interface of CyTools_MeshStudio.

The launcher at the root starts this file with the private interpreter, through ``pythonw``:
there is no console, so an unhandled exception would close the process with nothing on
screen — which is indistinguishable from "it does not start". Every failure here is written
to ``data/logs/interface.log`` and shown in a message box that names the reason and the log.

The most common one has a friendly text: the data directory is owned by one runtime at a
time, so a second instance cannot start while the first is open.
"""
from pathlib import Path
import runpy
import sys
import traceback

APP = Path(__file__).resolve().parent
ROOT = APP.parent
TITLE = 'CyTools_MeshStudio'


def log(message):
    """Keep the full failure where it can be read afterwards."""
    logs = ROOT / 'data' / 'logs'
    try:
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / 'interface.log').open('a', encoding='utf-8') as handle:
            handle.write(message + '\n')
    except OSError:
        pass


def show(message):
    """Say on screen why nothing opened; the log keeps the technical detail.

    ``MESHSTUDIO_NO_DIALOG=1`` writes to stderr instead of opening a modal box, so an
    automated run never blocks on a dialog nobody can close.
    """
    import os

    if os.environ.get('MESHSTUDIO_NO_DIALOG') == '1':
        sys.stderr.write(message + '\n')
        return
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message[:1500], TITLE, 0x10)
            return
        except Exception:  # noqa: BLE001
            pass
    sys.stderr.write(message + '\n')


def explain(error):
    text = str(error)
    if 'already owned by another runtime' in text:
        return ('CyTools_MeshStudio is already running.\n\n'
                'One instance owns the data folder at a time, so jobs and settings cannot be '
                'written by two of them. Close the open window and start it again.\n\n'
                'Si la fenêtre est déjà ouverte, la fermer avant de relancer.')
    return (f'{TITLE} could not start.\n\n{text}\n\n'
            f'Details: {ROOT / "data" / "logs" / "interface.log"}')


def main():
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    try:
        # An update activated during the previous session is applied first, by a separate
        # process that renames the folders while nothing of the interface is loaded yet.
        from updates import apply_at_startup

        applied = apply_at_startup(ROOT)
        if applied and not applied.get('applied') and applied.get('error'):
            log(f'Pending update not applied: {applied["error"]}')
        runpy.run_path(str(APP / 'gui' / 'main.py'), run_name='__main__')
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - nothing may escape without being shown
        log(traceback.format_exc())
        show(explain(exc))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
