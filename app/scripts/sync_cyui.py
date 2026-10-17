"""Copy the Python port of CyUI into this Tool, unchanged, and record which one it is.

    runtime/python/Scripts/python.exe app/scripts/sync_cyui.py [path/to/CyImgui_Interface]

Without an argument the library is read from CYUI_LIBRARY, or else from a CyImgui_Interface
folder two levels above the Tool.

CyUI (the CyDAW / Shaderixel / CyEngineHub look for Dear ImGui) lives in its own library;
its Python port is the single module python/cyui.py. The Tool carries a copy as app/cyui.py so
that a clone and a release run without the library, and app/cyui.json says where the copy
came from and its SHA-256, so a later sync shows what changed. The copy is never edited here:
a change belongs in the library, then comes back with this script. Only the line endings
are normalised to LF, as Git stores them, so the recorded SHA-256 matches a clone.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
DEFAULT_LIBRARY = Path(os.environ.get('CYUI_LIBRARY') or ROOT.parent.parent / 'CyImgui_Interface')


def main():
    library = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIBRARY
    source = library / 'python' / 'cyui.py'
    licence = library / 'LICENSE'
    if not source.is_file():
        raise SystemExit(f'No CyUI Python port at {source}')
    if not licence.is_file():
        raise SystemExit(f'No LICENSE at {licence}: the copy must travel with its licence text.')
    data = source.read_bytes().replace(b'\r\n', b'\n')
    target = APP / 'cyui.py'
    previous = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else ''
    digest = hashlib.sha256(data).hexdigest()
    target.write_bytes(data)
    (ROOT / 'LICENCES' / 'CyUI-MIT.txt').write_bytes(licence.read_bytes().replace(b'\r\n', b'\n'))
    record = {'library': 'CyUI', 'source': 'python/cyui.py', 'licence': 'MIT',
              'sha256': digest, 'bytes': len(data),
              'sourceModified': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(source.stat().st_mtime))}
    (APP / 'cyui.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(('unchanged' if previous == digest else 'updated') + f': app/cyui.py {digest[:12]} ({len(data)} bytes)')


if __name__ == '__main__':
    main()
