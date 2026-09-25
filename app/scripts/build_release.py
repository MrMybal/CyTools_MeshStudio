"""Build the release archives of CyTools_MeshStudio from a committed tree.

    runtime/python/Scripts/python.exe app/scripts/build_release.py [--ref HEAD] [--skip-launcher]

Two archives land in runtime/build/release/, with their SHA-256 in SHA256SUMS.txt:

* ``CyTools_MeshStudio-<version>-app.zip`` — ``git archive`` of the commit: the application
  alone, in the layout the Updates tab stages (the updater prefers the asset whose name
  says "app", so this is what an installed Tool downloads to update itself).
* ``CyTools_MeshStudio-<version>-windows-x64.zip`` — the same tree under one top folder, plus
  what makes it start on a Windows machine with nothing installed: the launcher compiled from
  app/launcher.cpp, an embeddable CPython carrying the application's packages
  (runtime/python), uv (runtime/uv) so that the Installation tab can build the engine
  environments, and the two native programs of the geometry engine (runtime/natives).

Every third-party part is downloaded from its release page, pinned by URL and SHA-256, and
kept in runtime/downloads/release/. Nothing is copied from this machine's own runtime, so the
archive holds exactly what the pins say. The engines and the weights are not in it: they are
installed by the Tool itself, from app/engines.json and app/models/install.json.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
CACHE = ROOT / 'runtime' / 'downloads' / 'release'
OUT = ROOT / 'runtime' / 'build' / 'release'
NAME = 'CyTools_MeshStudio'
USER_AGENT = 'CyTools_MeshStudio release builder'

#: pip put into the embeddable distribution (it ships without one); pinned like the rest.
PIP_VERSION = '26.2.1'

#: The third-party parts of the binary archive. Changing a version means changing its URL
#: and its SHA-256 here, on purpose; a download whose digest differs is refused.
PARTS = [
    {'id': 'python-embed', 'label': 'CPython 3.12.10, embeddable distribution (Windows x64)',
     'url': 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip',
     'sha256': '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3',
     'license': 'PSF-2.0', 'homepage': 'https://www.python.org', 'into': 'runtime/python'},
    {'id': 'uv', 'label': 'uv 0.12.19 (Windows x64)',
     'url': 'https://github.com/astral-sh/uv/releases/download/0.12.19/uv-x86_64-pc-windows-msvc.zip',
     'sha256': '6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0',
     'license': 'MIT OR Apache-2.0', 'homepage': 'https://github.com/astral-sh/uv',
     'into': 'runtime/uv', 'only': ['uv.exe']},
    {'id': 'autoremesher', 'label': 'AutoRemesher 1.2.0 (Windows x64)',
     'url': 'https://github.com/huxingyi/autoremesher/releases/download/1.2.0/autoremesher-1.2.0-win32-x86_64.zip',
     'sha256': 'f6184622cef84f0bcf032a0474df44e2076f4c10c159f1af0cb7230259af7476',
     'license': 'MIT', 'homepage': 'https://github.com/huxingyi/autoremesher',
     'into': 'runtime/natives/autoremesher-1.2.0'},
    {'id': 'quadwild', 'label': 'QuadWild Bi-MDF v0.0.2 (Windows binaries)',
     'url': 'https://github.com/cgg-bern/quadwild-bimdf/releases/download/v0.0.2/windows-binaries.zip',
     'sha256': '006c98d5e52d4992b70e929c5b95237efaa35aae8eb293bb0e6c3b933e569424',
     'license': 'GPL-3.0', 'homepage': 'https://github.com/cgg-bern/quadwild-bimdf',
     'into': 'runtime/natives/quadwild-bimdf-v0.0.2'},
]


def log(message):
    print(message, flush=True)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(part):
    """The part's archive from the cache, downloaded when absent, always verified."""
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / part['url'].rsplit('/', 1)[-1]
    if not target.is_file() or sha256_of(target) != part['sha256']:
        log(f'  downloading {part["label"]}')
        request = urllib.request.Request(part['url'], headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as answer, open(target, 'wb') as handle:
            shutil.copyfileobj(answer, handle)
    digest = sha256_of(target)
    if digest != part['sha256']:
        target.unlink(missing_ok=True)
        raise SystemExit(f'{part["label"]}: SHA-256 {digest} does not match the pinned '
                         f'{part["sha256"]}; the download was discarded.')
    return target


def run(argv, **extra):
    log('  $ ' + ' '.join(str(item) for item in argv))
    subprocess.run([str(item) for item in argv], check=True, **extra)


def version_of(ref):
    manifest = subprocess.run(['git', 'show', f'{ref}:app/CyTool.json'], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout
    return str(json.loads(manifest).get('version', '0.0.0'))


def build_launcher():
    """Compile app/launcher.cpp with MSVC, through the x64 developer environment."""
    found = sorted(path for base in ('C:/Program Files', 'C:/Program Files (x86)')
                   for path in Path(base).glob('Microsoft Visual Studio/*/*/VC/Auxiliary/Build/vcvars64.bat'))
    if not found:
        raise SystemExit('No Visual Studio with the C++ tools was found (vcvars64.bat); pass '
                         '--skip-launcher to reuse the launcher already at the Tool root.')
    script = APP / 'build_launcher.ps1'
    # cmd.exe must receive one raw command line: passed as a list, Python would quote the whole
    # "call ... && powershell ..." as a single argument and cmd would not find the batch file.
    line = (f'cmd.exe /c call "{found[-1]}" >nul && powershell -NoProfile -ExecutionPolicy Bypass '
            f'-File "{script}"')
    log('  $ ' + line)
    subprocess.run(line, check=True, cwd=str(ROOT))
    launcher = ROOT / f'{NAME}.exe'
    if not launcher.is_file():
        raise SystemExit('The launcher was not produced.')
    return launcher


def embed_python(stage, archive):
    """The embeddable distribution, with pip and the application's packages."""
    target = stage / 'runtime' / 'python'
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(target)
    pth = next(target.glob('python3*._pth'))
    # The stock file hides site-packages and disables site: both are needed for pip.
    pth.write_text(f'{pth.stem.replace("._pth", "")}.zip\n.\nLib\\site-packages\nimport site\n',
                   encoding='ascii')
    site_packages = target / 'Lib' / 'site-packages'
    site_packages.mkdir(parents=True, exist_ok=True)
    run([sys.executable, '-m', 'pip', 'install', '--quiet', '--no-warn-script-location',
         '--target', site_packages, f'pip=={PIP_VERSION}'])
    python = target / 'python.exe'
    run([python, '-m', 'pip', 'install', '--quiet', '--no-warn-script-location',
         '-r', stage / 'app' / 'requirements.txt'])
    for cache in list(target.rglob('__pycache__')):
        shutil.rmtree(cache, ignore_errors=True)
    check = ('import cytools_core, imgui_bundle, moderngl, trimesh, numpy, PIL, mcp, gdown; '
             'from importlib.metadata import version; print("cytools-core", version("cytools-core"))')
    run([python, '-c', check])
    return target


def extract_into(archive, target, only=None):
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if only and name not in only:
                continue
            bundle.extract(name, target)


def zip_folder(folder, archive, prefix=''):
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                bundle.write(path, prefix + path.relative_to(folder).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--ref', default='HEAD', help='the commit to build (default HEAD)')
    parser.add_argument('--skip-launcher', action='store_true',
                        help='reuse the launcher at the Tool root instead of compiling it')
    args = parser.parse_args()

    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if args.ref == 'HEAD' and dirty:
        log('WARNING: the working tree has uncommitted changes; the archive is built from HEAD, '
            'not from them.')
    version = version_of(args.ref)
    commit = subprocess.run(['git', 'rev-parse', '--short', args.ref], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    log(f'{NAME} {version} from {args.ref} ({commit})')

    OUT.mkdir(parents=True, exist_ok=True)
    stage_root = OUT / 'stage'
    shutil.rmtree(stage_root, ignore_errors=True)
    stage = stage_root / NAME
    stage.mkdir(parents=True)

    # 1. the application: exactly the committed tree
    app_zip = OUT / f'{NAME}-{version}-app.zip'
    run(['git', 'archive', '--format=zip', '-o', app_zip, args.ref], cwd=ROOT)
    with zipfile.ZipFile(app_zip) as bundle:
        bundle.extractall(stage)
    log(f'  {app_zip.name}: {app_zip.stat().st_size // 1024} KiB')

    # 2. the launcher
    launcher = (ROOT / f'{NAME}.exe') if args.skip_launcher else build_launcher()
    shutil.copy2(launcher, stage / launcher.name)

    # 3. the third-party parts, pinned
    parts = {part['id']: fetch(part) for part in PARTS}
    embed_python(stage, parts['python-embed'])
    for part in PARTS:
        if part['id'] == 'python-embed':
            continue
        extract_into(parts[part['id']], stage / part['into'], part.get('only'))
    for part in PARTS:
        required = {'uv': 'uv.exe', 'autoremesher': 'autoremesher.exe', 'quadwild': 'quadwild.exe',
                    'python-embed': 'pythonw.exe'}[part['id']]
        if not (stage / part['into'] / required).is_file():
            raise SystemExit(f'{part["label"]}: {required} is missing after extraction.')

    # 4. what the archive is made of, kept inside it
    (stage / 'runtime' / 'RELEASE.json').write_text(json.dumps({
        'name': NAME, 'version': version, 'commit': commit, 'pip': PIP_VERSION,
        'parts': [{key: part[key] for key in ('id', 'label', 'url', 'sha256', 'license', 'homepage')}
                  for part in PARTS]}, indent=2) + '\n', encoding='utf-8')

    # 5. the binary archive, under one top folder
    binary_zip = OUT / f'{NAME}-{version}-windows-x64.zip'
    zip_folder(stage, binary_zip, prefix=f'{NAME}/')
    log(f'  {binary_zip.name}: {binary_zip.stat().st_size // (1024 * 1024)} MiB')

    sums = OUT / 'SHA256SUMS.txt'
    sums.write_text(''.join(f'{sha256_of(item)}  {item.name}\n' for item in (app_zip, binary_zip)),
                    encoding='ascii')
    log(sums.read_text('ascii').rstrip())
    shutil.rmtree(stage_root, ignore_errors=True)
    log(f'done: {OUT}')


if __name__ == '__main__':
    main()
