"""Cancel a running job and check that nothing keeps computing behind it.

    runtime/python/Scripts/python.exe app/tests/validate_cancel.py

A cancellation that only marks the job is not enough: the native program keeps the CPU and
the reservation is released under it. Two moments are exercised, on a long QuadWild remesh:

* **native** — the job is cancelled once ``quadwild.exe`` is really running under the worker.
  The whole process tree must be gone.
* **early** — the job is cancelled as soon as its worker is registered, at several small
  delays: this is when the worker's first progress messages are being handled. Reporting
  progress on a cancelled job raises, and an exception that left the wait loop there once
  let the worker go on and start the solver behind a job already marked Cancelled. A
  persistent worker may legitimately stay alive and idle after such a cancellation; what
  must never appear is the native solver.

The earlier version of this test stopped waiting as soon as the worker had any child — the
real interpreter under the virtual environment's launcher, which is always there — so it
cancelled at an arbitrary moment and passed or failed with the timing of the machine.
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
PARAMETERS = {'input': str(SPHERE), 'preRemesh': True, 'featureAngle': 35, 'scale': 0.2,
              'align': True, 'solverSeconds': 600}
TERMINAL = ('Completed', 'Failed', 'Cancelled')
EARLY_DELAYS = (0.0, 0.05, 0.15, 0.3)
#: How long the solver is looked for after an early cancellation.
WATCH_SECONDS = 12


#: A worker that answers the handshake, reports once, then "computes" for two minutes.
FAKE_WORKER = (
    "import sys, json, time\n"
    "print(json.dumps({'event': 'ready'}), flush=True)\n"
    "sys.stdin.readline()\n"
    "print(json.dumps({'event': '%s', 'percent': 5, 'message': 'working'}), flush=True)\n"
    "time.sleep(120)\n")


def reporting_race(event):
    """The cancellation lands while a progress (or log) message is being handled.

    Timing cannot aim at that window — it is the tenth of a second before one of the few
    messages a worker sends — so it is built here: the callback raises exactly as
    ``JobContext.progress`` does on a cancelled job, and the worker must not survive it.
    """
    from cytools_core import CyToolError
    from meshstudio.engines.workerhost import WorkerHost

    host = WorkerHost('cancel-race', [sys.executable, '-c', FAKE_WORKER % event],
                      idle_seconds=0, startup_timeout=30)
    host.start()
    pid = host.process.pid

    def cancelled(*_arguments):
        raise CyToolError('Cancelled', 'Cancelled while reporting')

    raised = ''
    try:
        host.request('compute', {}, cancelled=lambda: False, timeout=60, progress=cancelled, log=cancelled)
    except CyToolError as exc:
        raised = exc.code
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(item.is_running() for item in tree(pid)):
        time.sleep(0.1)
    survivors = [item.pid for item in tree(pid) if item.is_running()]
    for process in tree(pid):
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    return {'case': f'{event} handled on a cancelled job', 'raised': raised,
            'workerStillComputing': survivors}


def tree(pid):
    try:
        parent = psutil.Process(pid)
        return [parent] + parent.children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def native(processes):
    found = []
    for process in processes:
        try:
            if process.is_running() and process.name().lower().startswith('quad'):
                found.append(process)
        except psutil.NoSuchProcess:
            pass
    return found


def wait_for_worker(runtime, actor, job_id, need_native):
    """The pid of the job's worker once it is registered (and, if asked, running the solver)."""
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        state = runtime.get_job(actor, job_id)
        pids = [item['pid'] for item in state.get('artifactProcesses') or []]
        if state['state'] == 'Running' and pids:
            if not need_native or native(tree(pids[-1])):
                return pids[-1]
        if state['state'] in TERMINAL:
            raise SystemExit(f'The job finished before it could be cancelled: {state["state"]}')
        time.sleep(0.02)
    raise SystemExit('The worker never reached the expected point')


def cancel_and_wait(runtime, actor, job_id):
    started = time.monotonic()
    runtime.cancel(actor, job_id)
    state = runtime.get_job(actor, job_id)
    while state['state'] not in TERMINAL:
        if time.monotonic() - started > 60:
            raise SystemExit(f'The job stayed {state["state"]} 60s after the cancellation')
        time.sleep(0.05)
        state = runtime.get_job(actor, job_id)
    return state['state'], round(time.monotonic() - started, 2)


def main():
    if not SPHERE.is_file():
        raise SystemExit(f'Missing test input {SPHERE}')
    directory = DATA / 'test-runs' / 'cancel'
    directory.mkdir(parents=True, exist_ok=True)
    cases, failures = [], []

    # --- the cancellation lands while the worker's message is being handled
    for event in ('progress', 'log'):
        case = reporting_race(event)
        cases.append(case)
        if case['raised'] != 'Cancelled':
            failures.append(f'{case["case"]}: the cancellation was swallowed ({case["raised"] or "nothing raised"})')
        if case['workerStillComputing']:
            failures.append(f'{case["case"]}: the worker went on computing')

    with create_runtime(directory) as runtime:
        runtime.start()
        actor = runtime.authenticate(runtime.create_client('Cancellation test', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']

        # --- the solver is running
        job_id = runtime.submit(actor, session, 'remesh_field', dict(PARAMETERS))['jobId']
        worker = wait_for_worker(runtime, actor, job_id, need_native=True)
        watched = tree(worker)
        final, seconds = cancel_and_wait(runtime, actor, job_id)
        gone, alive = psutil.wait_procs(watched, timeout=30)
        cases.append({'case': 'native', 'finalState': final, 'cancelSeconds': seconds,
                      'watchedProcesses': len(watched), 'stillAlive': [item.pid for item in alive]})
        if final != 'Cancelled':
            failures.append(f'native: expected Cancelled, got {final}')
        if alive:
            failures.append(f'native: {len(alive)} process(es) survived the cancellation')

        # --- the worker has just been registered: its first progress messages are in flight
        for delay in EARLY_DELAYS:
            job_id = runtime.submit(actor, session, 'remesh_field', dict(PARAMETERS))['jobId']
            worker = wait_for_worker(runtime, actor, job_id, need_native=False)
            time.sleep(delay)
            final, seconds = cancel_and_wait(runtime, actor, job_id)
            solver, deadline = [], time.monotonic() + WATCH_SECONDS
            while time.monotonic() < deadline and not solver:
                solver = native(tree(worker))
                time.sleep(0.25)
            cases.append({'case': f'early +{delay}s', 'finalState': final, 'cancelSeconds': seconds,
                          'workerAlive': psutil.pid_exists(worker),
                          'solverBehindCancelledJob': [item.pid for item in solver]})
            if final != 'Cancelled':
                failures.append(f'early +{delay}s: expected Cancelled, got {final}')
            if solver:
                failures.append(f'early +{delay}s: the solver ran behind a cancelled job')
                for process in tree(worker):          # do not leave it running for ten minutes
                    try:
                        process.kill()
                    except psutil.NoSuchProcess:
                        pass

    evidence = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'operation': 'remesh_field',
                'cases': cases, 'failures': failures}
    report = DATA / 'reports' / 'cancel-validation.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    for case in cases:
        print(json.dumps(case))
    if failures:
        raise SystemExit('; '.join(failures))
    print(json.dumps({'passed': len(cases), 'failed': 0}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
