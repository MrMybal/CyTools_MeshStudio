"""Cancel a running job and check that the worker process is really gone.

    runtime/python/Scripts/python.exe app/tests/validate_cancel.py

A cancellation that only marks the job is not enough: the native program keeps the CPU and
the reservation. This submits a long QuadWild remesh, cancels it while the native solver is
running, and then verifies that the worker and its children have exited.
"""
import json
from pathlib import Path
import sys
import time

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

import psutil  # noqa: E402

from tool import create_runtime  # noqa: E402

DATA = ROOT / 'data'
SPHERE = DATA / 'inputs' / 'test-sphere.obj'


def main():
    if not SPHERE.is_file():
        raise SystemExit(f'Missing test input {SPHERE}')
    directory = DATA / 'test-runs' / 'cancel'
    directory.mkdir(parents=True, exist_ok=True)

    with create_runtime(directory) as runtime:
        runtime.start()
        actor = runtime.authenticate(runtime.create_client('Cancellation test', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']
        job = runtime.submit(actor, session, 'remesh_field', {
            'input': str(SPHERE), 'preRemesh': True, 'featureAngle': 35,
            'scale': 0.2, 'align': True, 'solverSeconds': 600})
        job_id = job['jobId']

        deadline = time.monotonic() + 60
        pids = []
        while time.monotonic() < deadline:
            state = runtime.get_job(actor, job_id)
            processes = state.get('artifactProcesses') or []
            if processes:
                pids = [item['pid'] for item in processes]
            if state['state'] == 'Running' and pids:
                children = []
                for pid in pids:
                    try:
                        children = psutil.Process(pid).children(recursive=True)
                    except psutil.NoSuchProcess:
                        pass
                if children:
                    break
            if state['state'] in ('Completed', 'Failed', 'Cancelled'):
                raise SystemExit(f'The job finished before it could be cancelled: {state["state"]}')
            time.sleep(0.2)

        watched = []
        for pid in pids:
            try:
                parent = psutil.Process(pid)
                watched = [parent] + parent.children(recursive=True)
            except psutil.NoSuchProcess:
                pass
        started_cancel = time.monotonic()
        runtime.cancel(actor, job_id)

        deadline = time.monotonic() + 60
        state = runtime.get_job(actor, job_id)
        while state['state'] not in ('Cancelled', 'Failed', 'Completed'):
            if time.monotonic() > deadline:
                raise SystemExit(f'The job stayed {state["state"]} 60s after the cancellation')
            time.sleep(0.2)
            state = runtime.get_job(actor, job_id)
        cancel_seconds = round(time.monotonic() - started_cancel, 2)

        gone, alive = psutil.wait_procs(watched, timeout=30)
        evidence = {
            'date': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'operation': 'remesh_field',
            'finalState': state['state'],
            'cancelSeconds': cancel_seconds,
            'watchedProcesses': [item.pid for item in watched],
            'stoppedProcesses': [item.pid for item in gone],
            'stillAlive': [item.pid for item in alive],
        }
        report = DATA / 'reports' / 'cancel-validation.json'
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps(evidence))
        if state['state'] != 'Cancelled':
            raise SystemExit(f'Expected Cancelled, got {state["state"]}')
        if alive:
            raise SystemExit(f'{len(alive)} process(es) survived the cancellation: {[p.pid for p in alive]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
