"""Serve a ported one-shot worker through the persistent protocol.

The workers taken from the absorbed Tools were written for the SDK's one-shot ProcessWorker:
they read one JSON request on stdin, print one JSON answer, and report progress by rewriting
``<output>/progress.json`` because their parent polled that file. Their logic is tested, so it
is kept as it is; this adapter gives them the persistent protocol instead of rewriting them.

It does three things: it forwards the progress file to the reporter while the call runs, it
turns the ``{'error': {...}}`` convention into a protocol error, and it keeps the process
alive between requests so a resident model survives.
"""
import json
from pathlib import Path
import threading
import time

from _protocol import WorkerError


class ProgressWatcher:
    """Forward a worker's progress file to the job, without polling it after the call."""

    def __init__(self, path, reporter, interval=0.2):
        self.path = Path(path)
        self.reporter = reporter
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None
        self._last = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._loop, daemon=True, name='progress-watcher')
        self._thread.start()
        return self

    def __exit__(self, *_exception):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._read()          # one last read: the final tick often lands after the call
        return False

    def _loop(self):
        while not self._stop.wait(self.interval):
            self._read()

    def _read(self):
        try:
            payload = json.loads(self.path.read_text('utf-8'))
        except (OSError, ValueError):
            return
        percent = payload.get('percent')
        step = payload.get('step') or payload.get('stage') or ''
        if percent is None:
            return
        key = (round(float(percent), 1), step)
        if key == self._last:
            return
        self._last = key
        self.reporter.progress(float(percent), str(step))


def raise_for_error(result, default_code='BackendFailure'):
    """Turn the ported ``{'error': {...}}`` convention into a protocol error."""
    if isinstance(result, dict) and isinstance(result.get('error'), dict):
        error = result['error']
        raise WorkerError(error.get('code') or default_code,
                          error.get('message') or 'The worker reported an error',
                          details=error.get('details'),
                          recoverable=error.get('code') in ('MissingDependency', 'MissingModel',
                                                            'DeviceUnavailable', 'OutOfMemory',
                                                            'InsufficientVRAM'))
    return result


def legacy_handler(execute, progress_of=None, classify=None):
    """Wrap ``execute(parameters)`` into a protocol handler.

    ``progress_of(parameters, workspace)`` says where that worker writes its progress file;
    the default is ``<parameters['output'] or workspace>/progress.json``.
    """
    def handler(request, reporter):
        parameters = dict(request.get('parameters') or {})
        workspace = Path(request.get('workspace') or '.')
        if progress_of is not None:
            path = progress_of(parameters, workspace)
        else:
            path = Path(parameters.get('output') or workspace) / 'progress.json'
        started = time.monotonic()
        reporter.progress(1, 'Starting')
        try:
            with ProgressWatcher(path, reporter):
                result = execute(parameters)
        except Exception as exc:  # noqa: BLE001
            if classify is not None:
                code, message = classify(exc)
                raise WorkerError(code, message) from exc
            raise
        result = raise_for_error(result)
        reporter.progress(100, 'Done', f'{time.monotonic() - started:.1f} s')
        return result
    return handler
