"""QuadWild Bi-MDF backend: field aligned quadrangulation of a triangulated mesh.

Ported from CyTools_QuadWild, including its two native stages (field and patches, then
Bi-MDF quadrangulation) and the documented quirk of the official v0.0.2 Windows binary:
it raises 0x80000003 *after* writing a valid result. That exception is only tolerated when
the binary is the exact build it was observed on (checked by SHA-256) and the native
statistics file proves the export completed; the result then carries a warning.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, serve  # noqa: E402
import meshio  # noqa: E402

# Official quad_from_patches.exe of the v0.0.2 release, the build the quirk was observed on.
KNOWN_BINARY = '5c43c16e4838bf0d4498eef32628dc28ac769f0448805e3da793b2311b7cba34'
KNOWN_CODE = 2147483651  # 0x80000003, raised after the export on Windows
#: QuadWild keeps its paths in fixed buffers: in a working folder whose path reached 267
#: characters it died at the preparation step with 0xC0000409 (a stack buffer overrun),
#: while the same mesh went through at 64. The longest file it writes there is refused first.
PATH_LIMIT = 240


def _executable(directory, name):
    return Path(directory) / (name + ('.exe' if sys.platform == 'win32' else ''))


def _run(argv, cwd, log_path, reporter):
    with Path(log_path).open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(x) for x in argv], cwd=str(cwd), stdout=log,
                                   stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0)
        while process.poll() is None:
            time.sleep(0.25)
        return process.returncode


def remesh(request, reporter):
    parameters = request.get('parameters') or {}
    workspace = Path(request['workspace'])
    engine_dir = Path(request['engine'])
    quadwild = _executable(engine_dir, 'quadwild')
    from_patches = _executable(engine_dir, 'quad_from_patches')
    config_dir = engine_dir / 'config'
    for required in (quadwild, from_patches, config_dir / 'main_config' / 'flow.txt'):
        if not required.exists():
            raise WorkerError('MissingDependency', f'QuadWild is incomplete: {required} is missing',
                              recoverable=True)

    source = Path(parameters['input'])
    if source.suffix.lower() != '.obj':
        raise WorkerError('InvalidParameters', 'QuadWild requires a triangulated OBJ file')
    reporter.progress(2, 'Validating', 'Reading the input mesh')
    work = inside(workspace, 'work/mesh.obj')
    try:
        vertices, faces = meshio.normalise_obj(source, work, require_triangles=True,
                                               max_bytes=128 * 1024 ** 2)
    except meshio.MeshError as exc:
        raise WorkerError('InvalidInput', str(exc)) from exc
    if len(faces) > 1_000_000:
        raise WorkerError('InvalidInput', 'QuadWild is limited to one million triangles here')
    reporter.log(f'Input: {len(vertices)} vertices, {len(faces)} triangles')

    work_dir = work.parent
    longest = len(str((work_dir / 'mesh_rem_p0.obj').resolve()))
    if longest > PATH_LIMIT:
        raise WorkerError('InvalidInput',
                          f'The working folder of this job has a path of {longest} characters; '
                          f'QuadWild cannot handle more than about {PATH_LIMIT} and stops with '
                          'an error code. Install the Tool in a folder with a shorter path.',
                          recoverable=True)
    if not (work_dir / 'config').exists():
        shutil.copytree(config_dir, work_dir / 'config')

    prep = work_dir / 'prep.txt'
    prep.write_text(f"do_remesh {int(parameters['preRemesh'])}\n"
                    f"sharp_feature_thr {parameters['featureAngle']}\n"
                    f"alpha 0.01\nscaleFact {parameters['scale']}\n", encoding='utf-8')
    flow = 'flow.txt' if parameters.get('align', True) else 'flow_noalign.txt'
    config = (work_dir / 'config' / 'main_config' / flow).read_text('utf-8')
    config = '\n'.join(
        ('scaleFact ' + str(parameters['scale'])) if line.startswith('scaleFact ')
        else ('timeLimit ' + str(parameters['solverSeconds'])) if line.startswith('timeLimit ')
        else line
        for line in config.splitlines()) + '\n'
    main = work_dir / 'main.txt'
    main.write_text(config, encoding='utf-8')

    warnings = []
    reporter.progress(10, 'Field and patches', 'Preparing the cross field (no internal progress)')
    code = _run([quadwild, work, '2', prep], work_dir, inside(workspace, 'outputs/preparation.log'), reporter)
    if code:
        raise WorkerError('EngineFailed', f'Preparation stopped with code {code}',
                          details={'log': str(workspace / 'outputs/preparation.log')})
    patches = work_dir / 'mesh_rem_p0.obj'
    if not patches.is_file():
        raise WorkerError('EngineFailed', 'The engine produced no patch file')

    reporter.progress(55, 'Quadrangulation', f'Bi-MDF solver, limited to {parameters["solverSeconds"]}s')
    native_stats = work_dir / 'native-stats.json'
    log_path = inside(workspace, 'outputs/quadrangulation.log')
    code = _run([from_patches, patches, '1', main, native_stats], work_dir, log_path, reporter)
    if code:
        tolerated = (code == KNOWN_CODE
                     and hashlib.sha256(from_patches.read_bytes()).hexdigest() == KNOWN_BINARY
                     and native_stats.is_file())
        native = {}
        if native_stats.is_file():
            try:
                native = json.loads(native_stats.read_text('utf-8'))
            except ValueError:
                native = {}
        if not (tolerated and native.get('runtimes') and 'quant_eval' in native):
            raise WorkerError('EngineFailed', f'Quadrangulation stopped with code {code}. See {log_path}',
                              details={'log': str(log_path)})
        reporter.log('Official v0.0.2 binary: known exception after a valid export; the final report is present.',
                     level='Warning')
        warnings.append('QuadWild v0.0.2 on Windows raises 0x80000003 after writing a valid result.')

    candidates = list(work_dir.glob('*_quadrangulation_smooth.obj'))
    if len(candidates) != 1:
        raise WorkerError('InvalidOutput', 'The final quad mesh is missing or ambiguous')
    reporter.progress(90, 'Checking', 'Verifying that every face is a quad')
    final = inside(workspace, 'outputs/quad.obj')
    quad_vertices, quad_faces = meshio.read_obj(candidates[0])
    meshio.write_obj(final, quad_vertices, quad_faces)
    stats = meshio.statistics(quad_vertices, quad_faces)
    if stats['quads'] != stats['faces']:
        raise WorkerError('InvalidOutput', 'The result contains non quadrangular faces', details=stats)

    report_path = inside(workspace, 'outputs/report.json')
    report_path.write_text(json.dumps({'before': meshio.statistics(vertices, faces), 'after': stats,
                                       'parameters': parameters, 'warnings': warnings}, indent=2),
                           encoding='utf-8')
    reporter.progress(100, 'Done', f'{stats["faces"]} quads')
    declared = {key: stats[key] for key in ('vertices', 'faces', 'quads', 'triangles')}
    return {'file': str(final), 'report': str(report_path), 'mimeType': 'model/obj',
            'warnings': warnings, **declared}


def diagnose(request, reporter):
    engine_dir = Path(request.get('engine') or '')
    required = [_executable(engine_dir, 'quadwild'), _executable(engine_dir, 'quad_from_patches'),
                engine_dir / 'config' / 'main_config' / 'flow.txt']
    return {'installed': all(item.exists() for item in required), 'engine': str(engine_dir),
            'source': 'https://github.com/cgg-bern/quadwild-bimdf', 'modelsRequired': False,
            'platform': sys.platform, 'missing': [str(item) for item in required if not item.exists()]}


if __name__ == '__main__':
    raise SystemExit(serve({'remesh': remesh, 'diagnose': diagnose}))
