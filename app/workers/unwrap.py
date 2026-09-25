"""Isolated xatlas process.

xatlas is native code and is known to abort on some valid meshes, for example a perfectly
regular dense sphere. Running it here means such a failure kills one short-lived process
instead of the job worker, and the caller can fall back to the built-in grid unwrapper.

Usage: unwrap.py INPUT.npz OUTPUT.npz
"""
import sys

import numpy as np


def main():
    data = np.load(sys.argv[1])
    import xatlas
    mapping, faces, uv = xatlas.parametrize(np.ascontiguousarray(data['vertices'], np.float32),
                                            np.ascontiguousarray(data['faces'], np.uint32))
    if len(faces) == 0 or len(uv) == 0:
        raise ValueError('xatlas produced an empty atlas')
    np.savez(sys.argv[2], mapping=np.asarray(mapping, np.int64), faces=np.asarray(faces, np.int64),
             uv=np.asarray(uv, np.float64))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
