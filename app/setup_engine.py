"""Create or repair an engine environment declared in app/engines.json.

    python app/setup_engine.py geometry
    python app/setup_engine.py torch-cu124 [--cpu-only] [--sources-only] [--no-sources]
    python app/setup_engine.py --status-all

Environments are created at their final path (runtime/engines/<name>) with an interpreter
of the Python version the engine declares; a venv is never moved. PyTorch is installed first
from the wheel index declared for the engine, pinned by a constraints file so that a
later dependency cannot swap the CUDA build for a CPU wheel. Vendored sources are git
checkouts at pinned revisions. The last step is an import check inside the new
environment; nothing is reported installed before that check passes.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

APP = Path(__file__).resolve().parent
ROOT = APP.parent
RUNTIME = ROOT / 'runtime'
SPEC = json.loads((APP / 'engines.json').read_text('utf-8-sig'))


def log(message):
    print('[setup_engine] ' + message, flush=True)


def base_interpreter():
    # A venv shim cannot reliably create another venv: use the real interpreter.
    return getattr(sys, '_base_executable', None) or sys.executable


def interpreters_root():
    return RUNTIME / 'interpreters'


def interpreter_for(name):
    """Real interpreter of the version this engine declares.

    The six engines of this Tool do not share a Python version (3.9 for WHAM, 3.10 for the
    legacy multi-view stack, 3.11 for CUDA 12.4, 3.12 for the current ones), so the version
    cannot be the one running this script. Order: an interpreter already downloaded under
    runtime/interpreters, then the Windows ``py`` launcher, then ``uv python install``.
    """
    wanted = str(SPEC['engines'][name].get('python') or '').strip()
    if not wanted:
        return base_interpreter()
    current = '.'.join(str(part) for part in sys.version_info[:2])
    # The embeddable distribution of the binary release has no venv module: it can run the
    # application but not create an engine environment, so it is never offered here.
    if current == wanted and importlib.util.find_spec('venv') is not None:
        return base_interpreter()

    suffix = 'python.exe' if sys.platform == 'win32' else 'bin/python3'
    for candidate in sorted(interpreters_root().glob(f'cpython-{wanted}*')):
        executable = candidate / suffix
        if executable.is_file():
            return str(executable)

    # The uv shipped by the binary release comes first: it gives the same interpreter on every
    # machine. Then whatever Python the machine has, then a uv installed by the user.
    shipped_uv = RUNTIME / 'uv' / ('uv.exe' if sys.platform == 'win32' else 'uv')
    if sys.platform == 'win32' and not shipped_uv.is_file():
        probe = subprocess.run(['py', f'-{wanted}', '-c', 'import sys; print(sys.executable)'],
                               capture_output=True, text=True)
        if probe.returncode == 0 and probe.stdout.strip():
            return probe.stdout.strip()

    log(f'Python {wanted} is not available locally; asking uv to install it')
    interpreters_root().mkdir(parents=True, exist_ok=True)
    uv = str(shipped_uv) if shipped_uv.is_file() else 'uv'
    probe = subprocess.run([uv, 'python', 'install', wanted, '--install-dir', str(interpreters_root())],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        raise SystemExit(f'Python {wanted} is required by engine "{name}" and could not be installed.\n'
                         f'Install it yourself, or install uv (https://docs.astral.sh/uv/) and retry.\n'
                         + probe.stderr[-2000:])
    for candidate in sorted(interpreters_root().glob(f'cpython-{wanted}*')):
        executable = candidate / suffix
        if executable.is_file():
            return str(executable)
    raise SystemExit(f'uv reported success but no Python {wanted} was found under {interpreters_root()}')


def engine_root(name):
    return ROOT / SPEC['engines'][name]['directory']


def engine_python(name):
    root = engine_root(name)
    return root / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')


def sources_root():
    return RUNTIME / 'sources'


def run(command, **kwargs):
    log(' '.join(str(c) for c in command))
    subprocess.run([str(c) for c in command], check=True, **kwargs)


def windows_ca_bundle():
    """A PEM bundle of the roots Windows trusts, for interpreters that do not read that store.

    A network that inspects TLS presents its own root. Python built for this machine reads the
    Windows store through truststore, but that needs Python 3.10 and the WHAM engine is 3.9,
    so its pip rejected every download with "self signed certificate in certificate chain".
    Exporting the roots keeps verification on; disabling it with --trusted-host would not.
    """
    if sys.platform != 'win32':
        return None
    bundle = RUNTIME / 'downloads' / 'windows-ca.pem'
    if bundle.is_file() and bundle.stat().st_size > 1024:
        return bundle
    bundle.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$out = @(); "
        "foreach ($store in 'Root','CA') { "
        "  Get-ChildItem \"Cert:\\LocalMachine\\$store\", \"Cert:\\CurrentUser\\$store\" "
        "    -ErrorAction SilentlyContinue | ForEach-Object { "
        "      $b = [Convert]::ToBase64String($_.RawData, 'InsertLineBreaks'); "
        "      $out += \"-----BEGIN CERTIFICATE-----`n$b`n-----END CERTIFICATE-----\" } } ; "
        f"Set-Content -Path '{bundle}' -Value ($out -join \"`n\") -Encoding ascii")
    result = subprocess.run(['powershell', '-NoProfile', '-Command', script],
                            capture_output=True, text=True)
    if result.returncode != 0 or not bundle.is_file():
        log('could not export the Windows certificate store: ' + result.stderr[-200:])
        return None
    log(f'exported the Windows trusted roots to {bundle}')
    return bundle


def pip(python, *args, env=None):
    environment = dict(env or os.environ)
    if sys.platform == 'win32' and 'PIP_CERT' not in environment:
        bundle = windows_ca_bundle()
        if bundle is not None:
            environment['PIP_CERT'] = str(bundle)
    run([python, '-m', 'pip', *args], env=environment)


def install_sources(name):
    spec = SPEC['engines'][name]
    result = {}
    for source, item in spec.get('sources', {}).items():
        target = sources_root() / source
        target.parent.mkdir(parents=True, exist_ok=True)
        if not (target / '.git').is_dir():
            if target.exists() and any(target.iterdir()):
                raise SystemExit(f'{target} exists and is not a git checkout; remove it or fix it manually')
            run(['git', 'clone', '--no-checkout', '--filter=blob:none', item['repository'], str(target)])
        head = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        required = target / item['requiredFile']
        populated = required.is_file()
        if head.stdout.strip() != item['revision'] or not populated:
            if populated:
                dirty = subprocess.run(['git', '-C', str(target), 'status', '--porcelain'], capture_output=True, text=True).stdout.strip()
                if dirty:
                    raise SystemExit(f'{target} has local changes; refusing to move it to {item["revision"]}')
            if subprocess.run(['git', '-C', str(target), 'cat-file', '-e', item['revision'] + '^{commit}'], capture_output=True).returncode != 0:
                run(['git', '-C', str(target), 'fetch', '--depth', '1', 'origin', item['revision']])
            # --detach also populates the work tree of a --no-checkout clone.
            run(['git', '-C', str(target), 'checkout', '--detach', item['revision']])
        if not required.is_file():
            raise SystemExit(f'Required file missing after checkout: {required}')
        result[source] = {'path': str(target), 'revision': item['revision']}
        log(f'source {source} ready at {item["revision"][:12]}')
    return result


def wheels_root():
    return RUNTIME / 'downloads' / 'wheels'


def install_wheels(name, python, env):
    """Install the native wheels an engine declares, verified by SHA-256.

    These extensions are compiled against one exact torch ABI and are not on PyPI, so they
    are fetched from the release the engine publishes and checked before being installed.
    A wheel already downloaded and matching its digest is reused instead of fetched again.
    """
    import hashlib
    import urllib.request

    block = SPEC['engines'][name].get('wheels')
    if not block:
        return []
    if block.get('platform') and block['platform'] != sys.platform:
        raise SystemExit(f'Engine "{name}" declares native wheels for {block["platform"]} only. '
                         f'{block.get("note", "")}')
    target = wheels_root()
    target.mkdir(parents=True, exist_ok=True)
    installed = []
    for filename, digest in block['files'].items():
        path = target / filename
        if path.is_file():
            with path.open('rb') as handle:
                if hashlib.file_digest(handle, 'sha256').hexdigest() != digest:
                    log(f'{filename} does not match its digest, downloading it again')
                    path.unlink()
        if not path.is_file():
            url = block['baseUrl'] + filename
            log(f'downloading {filename}')
            partial = path.with_suffix(path.suffix + '.part')
            with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            with partial.open('rb') as handle:
                actual = hashlib.file_digest(handle, 'sha256').hexdigest()
            if actual != digest:
                partial.unlink(missing_ok=True)
                raise SystemExit(f'{filename} has digest {actual}, expected {digest}')
            partial.replace(path)
        pip(python, 'install', '--no-deps', str(path), env=env)
        installed.append({'wheel': filename, 'sha256': digest})
    return installed


def portable_cuda(block):
    """Download the official CUDA redistributables this engine needs, into the Tool.

    A CUDA build of PyTorch makes its own CMake package require a CUDA toolkit, even for an
    extension whose kernels would run on the CPU. Keeping that toolkit inside runtime/ means
    no driver is touched, no system installation is required and the machine PATH is left
    alone. Every archive is checked against the SHA-256 NVIDIA publishes in its manifest.
    """
    import hashlib
    import shutil
    import urllib.request
    import zipfile

    with urllib.request.urlopen(block['baseUrl'] + block['manifest'], timeout=60) as response:
        manifest = json.load(response)
    destination = ROOT / block['directory']
    cache = RUNTIME / 'downloads' / 'cuda'
    cache.mkdir(parents=True, exist_ok=True)
    for component in block['components']:
        item = manifest[component]['windows-x86_64']
        archive = cache / Path(item['relative_path']).name

        def valid():
            if not archive.is_file():
                return False
            with archive.open('rb') as stream:
                return hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256']

        if not valid():
            log(f'CUDA component {component}')
            with urllib.request.urlopen(block['baseUrl'] + item['relative_path'], timeout=600) as response, \
                    archive.open('wb') as stream:
                shutil.copyfileobj(response, stream)
        if not valid():
            raise SystemExit(f'NVIDIA archive SHA-256 mismatch: {component}')
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                relative = Path(*Path(member.filename).parts[1:])
                if not relative.parts or member.is_dir():
                    continue
                # Torch ships the CUDA math runtime DLLs; only headers and import libraries
                # are needed from the lib* components.
                if (component.startswith('lib') and relative.parts[0] not in ('include', 'lib')
                        and 'LICENSE' not in member.filename):
                    continue
                target = (destination / relative).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise SystemExit('Unsafe path inside an NVIDIA archive')
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
    return destination


def compiler_environment(version):
    """Load the MSVC toolchain into this process only; the machine PATH is untouched."""
    locator = (Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))
               / 'Microsoft Visual Studio/Installer/vswhere.exe')
    if not locator.is_file():
        raise SystemExit('Visual Studio 2022 C++ tools are required to build the native extensions')
    path = subprocess.check_output([str(locator), '-latest', '-products', '*', '-requires',
                                    'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                    '-property', 'installationPath'], text=True).strip()
    batch = Path(path) / 'VC/Auxiliary/Build/vcvars64.bat'
    if not batch.is_file():
        raise SystemExit('Visual Studio 2022 C++ tools are required to build the native extensions')
    # CUDA 12.4 supports MSVC 19.38; never let a newer default toolset be selected silently.
    output = subprocess.check_output(
        'cmd.exe /d /s /c "' + f'"{batch}" -vcvars_ver={version} >nul && set' + '"', text=True)
    for line in output.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            if key:
                os.environ[key] = value
    os.environ['DISTUTILS_USE_SDK'] = '1'
    os.environ['MSSdk'] = '1'


def install_native(name, python, env):
    """Compile the extensions an engine needs and that have no wheel for its ABI."""
    import shutil

    block = SPEC['engines'][name].get('nativeBuild')
    if not block:
        return {}
    if sys.platform != 'win32':
        raise SystemExit(f'Engine "{name}" builds native extensions, and only the Windows build '
                         f'is implemented here. {block.get("note", "")}')
    pip(python, 'install', 'setuptools', 'wheel', 'scikit-build-core>=1.0', 'pybind11>=2.10',
        'cmake>=3.24', 'ninja', env=env)
    compiler_environment(block.get('msvc', '14.38'))
    cuda = portable_cuda(block['cuda'])
    build_env = dict(os.environ)
    build_env.update({'CUDA_HOME': str(cuda), 'CUDA_PATH': str(cuda), 'CUDAToolkit_ROOT': str(cuda),
                      'PATH': str(cuda / 'bin') + os.pathsep + os.environ.get('PATH', ''),
                      # Ninja keeps the toolset selected above; the Visual Studio generator
                      # would ignore it.
                      'CMAKE_GENERATOR': 'Ninja',
                      'CMAKE_ARGS': f'-DCMAKE_CUDA_ARCHITECTURES={block["cuda"]["architectures"]}',
                      'PIP_KEYRING_PROVIDER': 'disabled', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'})
    if not shutil.which('nvcc', path=build_env['PATH']):
        raise SystemExit('nvcc was not found after installing the CUDA redistributables')
    built = {}
    for item in block['packages']:
        if 'spec' in item:
            target = item['spec']
        else:
            target = str(sources_root() / item['source'] / item['path'])
            if not Path(target).is_dir():
                raise SystemExit(f'{item["label"]}: {target} is missing from the checkout')
        log('building ' + item['label'])
        pip(python, 'install', '--no-build-isolation', '--no-cache-dir', target, env=build_env)
        built[item['label']] = target
    return built


def install_pip_extra(name, python, env):
    """Packages that need their own pip invocation: a legacy setup.py, or a pin ordering."""
    result = {}
    for item in SPEC['engines'][name].get('pipExtra', []):
        log(item.get('label', item['spec']))
        arguments = ['install']
        if item.get('noBuildIsolation'):
            # Their setup.py imports pkg_resources, which pip's isolated build environment
            # no longer provides; the engine's own setuptools does.
            arguments.append('--no-build-isolation')
        if item.get('index'):
            arguments += ['--index-url', item['index']]
        arguments.append(item['spec'])
        pip(python, *arguments, env=env)
        result[item.get('label', item['spec'])] = item['spec']
    return result


def install_wheel_indexes(name, python, env):
    """Packages that only exist on a project's own wheel index (PyTorch Geometric)."""
    result = {}
    for block in SPEC['engines'][name].get('wheelIndexes', []):
        log(block.get('label', block['url']))
        pip(python, 'install', *block['packages'], '-f', block['url'], env=env)
        result[block['url']] = block['packages']
    return result


def install_environment(name, cpu_only=False):
    spec = SPEC['engines'][name]
    root = engine_root(name)
    python = engine_python(name)
    if not python.exists():
        root.parent.mkdir(parents=True, exist_ok=True)
        run([interpreter_for(name), '-m', 'venv', str(root)])
    pip(python, 'install', '--upgrade', 'pip', 'wheel')
    env = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_KEYRING_PROVIDER='disabled')
    torch_spec = spec.get('torch')
    constraints = []
    if torch_spec:
        block = torch_spec['cpu'] if cpu_only else torch_spec
        pip(python, 'install', '--index-url', block['index'], *block['packages'], env=env)
        constraints = [p.split('+')[0] for p in block['packages']]
        (root / 'cytools-constraints.txt').write_text('\n'.join(constraints) + '\n', 'utf-8')
    # The native extensions go in before anything can pull a different torch under them.
    install_wheels(name, python, env)
    requirements = APP / spec['requirements']
    args = ['install', '-r', str(requirements)]
    if constraints:
        args += ['-c', str(root / 'cytools-constraints.txt')]
    pip(python, *args, env=env)
    install_pip_extra(name, python, env)
    install_wheel_indexes(name, python, env)
    install_native(name, python, env)
    for source in spec.get('installSources', []):
        checkout = sources_root() / source
        if not checkout.is_dir():
            raise SystemExit(f'Engine "{name}" installs the source "{source}", which is not checked out')
        args = ['install', str(checkout)]
        if constraints:
            args += ['-c', str(root / 'cytools-constraints.txt')]
        pip(python, *args, env=env)
    return python


def verify(name, cpu_only=False):
    spec = SPEC['engines'][name]
    python = engine_python(name)
    modules = spec.get('verify', [])
    script = (
        'import importlib, json, sys\n'
        'report = {"python": sys.version.split()[0], "modules": {}}\n'
        f'for name in {modules!r}:\n'
        '    try:\n'
        '        module = importlib.import_module(name)\n'
        '        report["modules"][name] = getattr(module, "__version__", "ok")\n'
        '    except Exception as exc:\n'
        '        report["modules"][name] = "ERROR: " + str(exc)\n'
        'try:\n'
        '    import torch\n'
        '    report["torch"] = torch.__version__\n'
        '    report["cuda"] = torch.cuda.is_available()\n'
        '    report["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"\n'
        'except Exception:\n'
        '    pass\n'
        'print(json.dumps(report))\n'
    )
    env = dict(os.environ)
    for source in spec.get('sources', {}):
        if source in spec.get('installSources', []):
            continue  # installed as a package; its checkout must not shadow it
        env['PYTHONPATH'] = str(sources_root() / source) + os.pathsep + env.get('PYTHONPATH', '')
    sys.path.insert(0, str(APP))
    from meshstudio.engines import registry as engine_registry
    layout = engine_registry.ensure_model_layout(name)
    for relative, item in layout.items():
        log(f'model layout {relative}: {item["state"]}')
    env.update(engine_registry.layout_environment(name))
    env.setdefault('HF_HUB_OFFLINE', '1')
    # Some checks cannot be an import: an extension may need a stand-in module installed
    # first, or a real device. The engine declares them as statements, run in the same
    # process right after the imports.
    for statement in spec.get('verifyStatements', []):
        script += ('try:\n'
                   '    exec({code!r})\n'
                   '    report["modules"][{label!r}] = "ok"\n'
                   'except Exception as exc:\n'
                   '    report["modules"][{label!r}] = "ERROR: " + str(exc)\n'
                   ).format(code=statement['code'], label=statement['label'])
    script += 'print(json.dumps(report))\n'
    output = subprocess.run([str(python), '-c', script], capture_output=True, text=True, env=env, cwd=str(ROOT))
    if output.returncode != 0:
        raise SystemExit('Verification process failed:\n' + output.stderr[-4000:])
    report = json.loads(output.stdout.strip().splitlines()[-1])
    failed = {k: v for k, v in report['modules'].items() if str(v).startswith('ERROR')}
    if failed:
        raise SystemExit('Missing modules in ' + name + ': ' + json.dumps(failed, indent=2))
    if spec.get('torch') and not cpu_only and not report.get('cuda'):
        raise SystemExit('CUDA is not available in the new environment (torch ' + str(report.get('torch')) + ')')
    return report


def status(name):
    spec = SPEC['engines'][name]
    python = engine_python(name)
    info = {'engine': name, 'label': spec['label'], 'python': str(python), 'installed': False, 'sources': {}, 'report': None}
    for source, item in spec.get('sources', {}).items():
        target = sources_root() / source
        head = ''
        if (target / '.git').is_dir():
            head = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        info['sources'][source] = {'present': (target / item['requiredFile']).is_file(), 'revision': head, 'expected': item['revision']}
    receipt = engine_root(name) / 'cytools-engine.json'
    if python.exists() and receipt.is_file():
        try:
            info['report'] = json.loads(receipt.read_text('utf-8'))
            info['installed'] = all(v['present'] and v['revision'] == v['expected'] for v in info['sources'].values())
        except ValueError:
            info['report'] = None
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('engine', nargs='?', choices=list(SPEC['engines']))
    parser.add_argument('--cpu-only', action='store_true')
    parser.add_argument('--sources-only', action='store_true')
    parser.add_argument('--no-sources', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--status-all', action='store_true')
    args = parser.parse_args()
    if args.status_all:
        print(json.dumps({name: status(name) for name in SPEC['engines']}, indent=2))
        return 0
    if not args.engine:
        parser.error('engine name required')
    if args.status:
        print(json.dumps(status(args.engine), indent=2))
        return 0
    if not args.no_sources:
        install_sources(args.engine)
    if args.sources_only:
        return 0
    install_environment(args.engine, cpu_only=args.cpu_only)
    report = verify(args.engine, cpu_only=args.cpu_only)
    report['cpuOnly'] = bool(args.cpu_only)
    receipt = engine_root(args.engine) / 'cytools-engine.json'
    receipt.write_text(json.dumps(report, indent=2), 'utf-8')
    log('engine ' + args.engine + ' ready: ' + json.dumps(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
