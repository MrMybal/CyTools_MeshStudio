"""Draw the form of every operation, one process each, and report which ones fail.

    runtime/python/Scripts/python.exe app/tests/validate_forms.py

A form is built from the operation's schema, so a control that a schema shape does not
support crashes only when that operation is selected. Rendering one operation and calling the
interface tested was the mistake this test exists to prevent: here every operation of the
manifest gets its own process, and a crash is reported against the operation that caused it
instead of taking the whole interface down.
"""
import json
from pathlib import Path
import subprocess
import sys
import time

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
REPORT = ROOT / 'data' / 'reports' / 'ui-operation.json'
OUTPUT = ROOT / 'data' / 'reports' / 'ui-forms.json'


def interpreter():
    candidate = ROOT / 'runtime' / 'python' / 'Scripts' / 'python.exe'
    if not candidate.exists():
        candidate = ROOT / 'runtime' / 'python' / 'bin' / 'python'
    return str(candidate if candidate.exists() else sys.executable)


def main():
    manifest = json.loads((APP / 'CyTool.json').read_text('utf-8'))
    operations = [item['id'] for item in manifest['operations']]
    results = []
    for index, operation in enumerate(operations, 1):
        REPORT.unlink(missing_ok=True)
        started = time.monotonic()
        process = subprocess.run(
            [interpreter(), str(APP / 'desktop.py'), f'--ui-test-operation={operation}'],
            capture_output=True, text=True, timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0)
        # The report existing is not enough: a run that showed another tab (the 3D viewer
        # reopens the last mesh and selects itself) writes it too, having drawn nothing.
        report = {}
        if REPORT.is_file():
            try:
                report = json.loads(REPORT.read_text('utf-8'))
            except ValueError:
                report = {}
        form_frames = int(report.get('formFrames', 0) or 0)
        drawn = bool(report.get('drawn')) and report.get('operation') == operation             and form_frames >= 3
        entry = {'operation': operation, 'drawn': drawn, 'formFrames': form_frames,
                 'returncode': process.returncode,
                 'seconds': round(time.monotonic() - started, 1)}
        if REPORT.is_file() and not drawn and process.returncode == 0:
            entry['error'] = f'the form was drawn in {form_frames} frame(s), not 3'
        if (not drawn or process.returncode != 0) and 'error' not in entry:
            trace = (process.stderr or '').strip().splitlines()
            entry['error'] = trace[-1] if trace else 'no output'
            entry['traceback'] = '\n'.join(trace[-18:])
        results.append(entry)
        state = f'ok ({form_frames} frames)' if drawn and process.returncode == 0 else 'FAILED'
        print(f'[{index:2}/{len(operations)}] {operation:<24} {state} '
              f'{entry.get("error", "")[:110]}', flush=True)

    failed = [item for item in results if not item['drawn'] or item['returncode'] != 0]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({'date': time.strftime('%Y-%m-%dT%H:%M:%S'),
                                  'operations': len(results), 'failed': len(failed),
                                  'results': results}, indent=2), encoding='utf-8')
    print(f'\n{len(results) - len(failed)}/{len(results)} forms drawn. Report: {OUTPUT}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
