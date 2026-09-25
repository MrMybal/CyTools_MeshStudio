"""Worker-side half of the JSON-lines protocol (see audiostudio/engines/workerhost.py).

A worker script defines handlers and calls ``serve(handlers)``. Handlers receive
``(request, reporter)`` and return a JSON-serialisable result, or raise ``WorkerError``
for expected failures. ``reporter.progress(percent, step, message)`` and
``reporter.log(message, level)`` stream events while the request runs.

``sys.stdout`` is redirected to stderr before any heavy import so that library noise
never corrupts the protocol; only this module writes to the real stdout.
"""
import json
import os
import sys
import threading
import traceback

PROTOCOL = sys.stdout
sys.stdout = sys.stderr
_write_lock = threading.Lock()


class WorkerError(Exception):
    def __init__(self, code, message, details=None, recoverable=False):
        super().__init__(message)
        self.code = code
        self.details = details
        self.recoverable = recoverable


def emit(message):
    with _write_lock:
        try:
            PROTOCOL.write(json.dumps(message, ensure_ascii=False, allow_nan=False) + '\n')
            PROTOCOL.flush()
        except (OSError, ValueError):
            pass


class Reporter:
    def __init__(self, request_id):
        self.request_id = request_id
        self._last = None

    def progress(self, percent, step='', message='', **extra):
        percent = max(0.0, min(100.0, float(percent)))
        key = (round(percent, 1), step, message)
        if key == self._last:
            return
        self._last = key
        payload = {'id': self.request_id, 'event': 'progress', 'percent': percent}
        if step:
            payload['step'] = str(step)
        if message:
            payload['message'] = str(message)
        payload.update({k: v for k, v in extra.items() if isinstance(v, (int, float, str, bool))})
        emit(payload)

    def log(self, message, level='Info'):
        emit({'id': self.request_id, 'event': 'log', 'level': level, 'message': str(message)[:16000]})

    def resident(self, **info):
        emit({'id': self.request_id, 'event': 'resident', 'resident': info})


def classify(exc):
    """Map common Python/library exceptions to CyTools error codes."""
    text = str(exc)
    lowered = text.lower()
    if isinstance(exc, WorkerError):
        return exc.code, text, exc.details, exc.recoverable
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return 'MissingDependency', text, None, True
    if isinstance(exc, FileNotFoundError):
        return 'MissingModel', text, None, True
    if 'out of memory' in lowered or 'cuda error' in lowered and 'memory' in lowered:
        return 'InsufficientVRAM', text, None, True
    if isinstance(exc, PermissionError):
        return 'AccessDenied', text, None, False
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return 'InvalidParameters', text, None, False
    return 'InferenceFailed', text, None, False


def serve(handlers, on_start=None):
    """Main loop: reads requests from stdin until EOF or a shutdown request."""
    if on_start:
        try:
            on_start()
        except Exception as exc:
            emit({'event': 'fatal', 'message': str(exc)})
            raise
    emit({'event': 'ready', 'pid': os.getpid(), 'python': sys.version.split()[0]})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            emit({'event': 'log', 'level': 'Warning', 'message': 'Ignored malformed request line'})
            continue
        request_id = str(request.get('id', ''))
        op = request.get('op', '')
        if op == 'shutdown':
            emit({'id': request_id, 'ok': True, 'result': {'shutdown': True}})
            break
        handler = handlers.get(op)
        reporter = Reporter(request_id)
        if handler is None:
            emit({'id': request_id, 'ok': False, 'code': 'InvalidParameters', 'message': 'Unknown worker operation: ' + str(op)})
            continue
        try:
            result = handler(request, reporter)
            json.dumps(result, allow_nan=False)
            emit({'id': request_id, 'ok': True, 'result': result})
        except Exception as exc:  # every failure becomes a protocol error, the process stays alive
            code, message, details, recoverable = classify(exc)
            sys.stderr.write(traceback.format_exc())
            sys.stderr.flush()
            emit({'id': request_id, 'ok': False, 'code': code, 'message': message, 'details': details, 'recoverable': recoverable,
                  'traceback': traceback.format_exc()[-4000:]})
    return 0


def isolate_native_output():
    """Keep the protocol safe from libraries that write to file descriptor 1 directly.

    Swapping ``sys.stdout`` is enough for Python code, but a CUDA extension printing from C
    writes to the descriptor, not to the object, and one such line in the middle of a JSON
    message kills the job. This duplicates the real descriptor 1 for the protocol, then
    points descriptors 1 and 2 at the worker's stderr, which the host already collects into
    ``data/logs/worker-<backend>.log``.

    Call it once, before importing anything heavy.
    """
    global PROTOCOL
    try:
        duplicated = os.dup(1)
    except OSError:
        return PROTOCOL
    PROTOCOL = os.fdopen(duplicated, 'w', encoding='utf-8', buffering=1)
    try:
        os.dup2(2, 1)
    except OSError:
        pass
    sys.stdout = sys.stderr
    return PROTOCOL


class SessionStore:
    """Heavy intermediates kept in the worker between two requests of one chain.

    Splitting a pipeline into workflow steps is only worth it if the steps can hand each
    other what they produced: writing a TRELLIS volume to disk and reading it back would
    cost more than recomputing it. A step therefore passes a ``session`` key, and what it
    leaves here is what the next step picks up.

    The store is deliberately small. It holds at most ``limit`` sessions and evicts the
    least recently used one, so a client that forgets to release a session costs one slot,
    not the card. ``release`` drops a session immediately, and everything disappears when
    the worker exits — which is also what a cancellation does, since the host kills it.
    """

    def __init__(self, limit=2, on_evict=None):
        self.limit = limit
        self.on_evict = on_evict
        self._entries = {}

    def get(self, key, default=None):
        entry = self._entries.get(key)
        if entry is None:
            return default
        self._entries[key] = self._entries.pop(key)  # most recently used last
        return entry

    def require(self, key, field=None):
        entry = self.get(key)
        if entry is None:
            raise WorkerError('MissingSession',
                              f'No resident session "{key}". Run the step that creates it first, '
                              'or run the whole operation in one call.', recoverable=True)
        if field is not None and field not in entry:
            raise WorkerError('MissingSession',
                              f'Session "{key}" carries no "{field}" yet.', recoverable=True)
        return entry if field is None else entry[field]

    def put(self, key, **values):
        entry = self._entries.pop(key, {})
        entry.update(values)
        self._entries[key] = entry
        while len(self._entries) > self.limit:
            oldest, dropped = next(iter(self._entries.items()))
            del self._entries[oldest]
            if self.on_evict:
                try:
                    self.on_evict(oldest, dropped)
                except Exception:
                    pass
        return entry

    def release(self, key):
        dropped = self._entries.pop(key, None)
        if dropped is not None and self.on_evict:
            try:
                self.on_evict(key, dropped)
            except Exception:
                pass
        return dropped is not None

    def keys(self):
        return list(self._entries)


def inside(workspace, path):
    """Ensure an output path is inside the job workspace; returns the resolved path."""
    from pathlib import Path
    workspace = Path(workspace).resolve()
    target = (workspace / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if not target.is_relative_to(workspace):
        raise WorkerError('AccessDenied', 'Output path escapes the job workspace')
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def memory_report():
    info = {}
    try:
        import psutil
        process = psutil.Process()
        memory = process.memory_info()
        info['workerMemoryBytes'] = int(getattr(memory, 'peak_wset', memory.rss))
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            info['vramPeakBytes'] = int(torch.cuda.max_memory_reserved())
            info['vramAllocatedBytes'] = int(torch.cuda.memory_allocated())
            info['gpuName'] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return info
