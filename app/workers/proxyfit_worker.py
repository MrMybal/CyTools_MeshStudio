"""Proxy fitting backend: the deterministic engine of CyTools_MeshConstruct.

No AI import lives here. The models supply masks, relative depth and camera cues; this
process turns them into a support volume, cross-section lofts and fitted primitives.
"""
import json
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _protocol import isolate_native_output, serve  # noqa: E402
from _legacy import legacy_handler  # noqa: E402

isolate_native_output()
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def execute(p):
    try:
        import numpy, cv2, scipy, trimesh, xatlas  # noqa: F401
    except ImportError as exc:
        return {'error': {'code': 'MissingDependency', 'message': str(exc)}}
    if p.get('task') == 'diagnose':
        from importlib.metadata import version
        from proxyfit import ENGINE_VERSION
        from proxyfit.primitives import TYPES
        return {'engine': 'CyTools proxy fitting', 'engineVersion': ENGINE_VERSION, 'python': sys.version.split()[0],
                'packages': {n: version(n) for n in ('numpy', 'opencv-python-headless', 'scipy', 'trimesh', 'xatlas')},
                'primitiveTypes': TYPES}
    from proxyfit import pipeline
    output = Path(p['output'])
    def note(percent, step):
        lo, hi = p.get('progressRange', [0, 100])
        try: (output / 'progress.json').write_text(json.dumps({'percent': round(lo + (hi - lo) * percent / 100, 1), 'step': step}), encoding='utf-8')
        except OSError: pass
    output.mkdir(parents=True, exist_ok=True)
    runner = pipeline.analyze if p['task'] == 'analyze' else pipeline.construct
    return runner({'views': p['views'], 'options': p.get('options', {})}, output, note)


def _classify(exc):
    if isinstance(exc, MemoryError):
        return 'OutOfMemory', 'Not enough RAM for this grid resolution'
    if isinstance(exc, ValueError):
        return 'InvalidInput', str(exc)
    return 'ConstructionFailed', f'{type(exc).__name__}: {exc}'


if __name__ == '__main__':
    handler = legacy_handler(execute, classify=_classify)
    raise SystemExit(serve({'construct': handler, 'analyze': handler, 'diagnose': handler}))
