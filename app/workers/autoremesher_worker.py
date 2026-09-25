"""AutoRemesher 1.2.0 backend: quad dominant remeshing of an OBJ.

Ported from CyTools_AutoRemesher. The native program reports no progress of its own, so
the steps around it are reported instead and the log is kept in the job workspace. The
process is started in its own group so that a cancellation really kills it: the host
terminates the whole tree, and this worker waits for the child before answering.
"""
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, serve  # noqa: E402
import meshio  # noqa: E402

ARGUMENTS = (('target-quads', 'target_quads'), ('edge-scaling', 'edge_scaling'),
             ('sharp-edge', 'sharp_edge'), ('smooth-normal', 'smooth_normal'),
             ('adaptivity', 'adaptivity'), ('anisotropy', 'anisotropy'))


def remesh(request, reporter):
    parameters = request.get('parameters') or {}
    workspace = Path(request['workspace'])
    engine = Path(request['engine'])
    if not engine.is_file():
        raise WorkerError('MissingDependency', f'AutoRemesher is not installed at {engine}', recoverable=True)
    source = Path(parameters['input_file'])
    if source.suffix.lower() != '.obj':
        raise WorkerError('InvalidParameters', 'AutoRemesher only accepts an OBJ file')

    reporter.progress(2, 'Validating', 'Reading the input OBJ')
    staged = inside(workspace, 'work/source.obj')
    before = meshio.statistics(*meshio.normalise_obj(source, staged))
    reporter.log(f'Input: {before["vertices"]} vertices, {before["faces"]} faces')

    output = inside(workspace, 'outputs/remeshed.obj')
    report_txt = inside(workspace, 'outputs/engine-report.txt')
    log_path = inside(workspace, 'outputs/engine.log')
    argv = [str(engine), '--input', str(staged), '--output', str(output), '--report', str(report_txt)]
    for flag, key in ARGUMENTS:
        if key in parameters:
            argv += ['--' + flag, str(parameters[key])]

    reporter.progress(10, 'Remeshing', 'AutoRemesher is running (it reports no internal progress)')
    started = time.monotonic()
    with log_path.open('wb') as log:
        process = subprocess.Popen(
            argv, cwd=str(workspace), stdout=log, stderr=log,
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0)
        while process.poll() is None:
            time.sleep(0.25)
        code = process.returncode
    seconds = round(time.monotonic() - started, 2)
    if code:
        tail = ''
        try:
            tail = log_path.read_text('utf-8', errors='replace')[-1500:]
        except OSError:
            pass
        raise WorkerError('EngineFailed', f'AutoRemesher stopped with code {code} after {seconds}s',
                          details={'log': str(log_path), 'tail': tail})

    reporter.progress(92, 'Checking', 'Verifying the produced topology')
    vertices, faces = meshio.read_obj(output)
    stats = meshio.statistics(vertices, faces)
    if not stats['quads']:
        raise WorkerError('InvalidOutput', 'The engine produced no quad face', details=stats)

    report = {'before': before, 'after': stats, 'seconds': seconds, 'geometryOnly': True,
              'parameters': {key: parameters.get(key) for _flag, key in ARGUMENTS},
              'engineVersion': request.get('version', ''),
              'note': 'UV sets and materials of the input are not carried over by AutoRemesher.'}
    report_path = inside(workspace, 'outputs/report.json')
    import json
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    reporter.progress(100, 'Done', f'{stats["quads"]} quads out of {stats["faces"]} faces')
    declared = {key: stats[key] for key in ('vertices', 'faces', 'quads', 'nonQuads', 'quadRatio')}
    return {'file': str(output), 'report': str(report_path), 'log': str(log_path),
            'mimeType': 'model/obj', **declared}


def diagnose(request, reporter):
    engine = Path(request.get('engine') or '')
    return {'installed': engine.is_file(), 'engine': str(engine),
            'version': request.get('version', ''), 'modelsRequired': False,
            'platform': sys.platform, 'python': sys.version.split()[0]}


if __name__ == '__main__':
    raise SystemExit(serve({'remesh': remesh, 'diagnose': diagnose}))
