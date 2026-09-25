"""UniRig backend: a mesh to a skeleton and skinning weights, ported from CyTools_UniRig.

Four upstream stages run one after another, each in its own process (`workers/unirig/stage.py`):
extract, skeleton, skin, export. They are separate processes because the upstream entry points
call ``sys.exit`` and reconfigure logging, which would take the worker with them.

The upstream configuration is copied into the job workspace and rewritten there so the
checkout stays pristine: FlashAttention becomes eager attention (no wheel exists for this
ABI), the OPT tokenizer points at the local copy, and the checkpoints point at
``data/models/unirig``.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, isolate_native_output, memory_report, serve  # noqa: E402

isolate_native_output()

WORKERS = Path(__file__).resolve().parent
ROOT = WORKERS.parent.parent
SOURCE = ROOT / 'runtime' / 'sources' / 'UniRig'
MODELS = ROOT / 'data' / 'models' / 'unirig'

STAGES = (('extract', 'Extracting the geometry', 10.0),
          ('skeleton', 'Predicting the skeleton', 35.0),
          ('skin', 'Predicting the skinning weights', 65.0),
          ('export', 'Exporting the rig', 90.0))

OUTPUT_FILES = {'rigged_mesh': 'rigged.glb', 'skeleton': 'skeleton.json',
                'skin_weights': 'rig.npz', 'skeleton_fbx': 'skeleton.fbx',
                'skin_fbx': 'skin.fbx'}


def _source_revision():
    try:
        return subprocess.run(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                              if sys.platform == 'win32' else 0).stdout.strip()
    except Exception:  # noqa: BLE001
        return ''


def _prepare_configs(work, model_root):
    """Copy the upstream configuration into the job and point it at the local files."""
    shutil.copytree(SOURCE / 'configs', work / 'configs', dirs_exist_ok=True)
    for path in (work / 'configs').rglob('*.yaml'):
        text = path.read_text(encoding='utf-8')
        text = (text.replace('flash_attention_2', 'eager')
                    .replace('facebook/opt-350m', str(model_root / 'opt').replace('\\', '/')))
        if path.name == 'unirig_skin.yaml':
            text = text.replace('  __target__: ptv3obj', '  __target__: ptv3obj\n  enable_flash: False')
        if path.name == 'quick_inference.yaml':
            text = text.replace('num_workers: 1', 'num_workers: 0')
        if path.name.startswith('quick_inference_skeleton'):
            text = text.replace('experiments/skeleton/articulation-xl_quantization_256/model.ckpt',
                                str(model_root / 'skeleton.ckpt').replace('\\', '/'))
        if path.name == 'quick_inference_unirig_skin.yaml':
            text = text.replace('experiments/skin/articulation-xl/model.ckpt',
                                str(model_root / 'skin.ckpt').replace('\\', '/'))
        path.write_text(text, encoding='utf-8')


def mesh_to_rig(request, reporter):
    parameters = dict(request.get('parameters') or {})
    workspace = Path(request['workspace'])
    source = Path(parameters['mesh'])
    if source.suffix.lower() not in ('.glb', '.gltf', '.obj', '.fbx'):
        raise WorkerError('InvalidParameters',
                          f'UniRig accepts GLB, glTF, OBJ or FBX; got {source.suffix}')
    for required in ('skeleton.ckpt', 'skin.ckpt'):
        if not (MODELS / required).is_file():
            raise WorkerError('MissingModel', f'{required} is missing from {MODELS}', recoverable=True)
    if not (SOURCE / 'src/inference/download.py').is_file():
        raise WorkerError('MissingDependency', f'The UniRig checkout is missing from {SOURCE}',
                          recoverable=True)

    started = time.monotonic()
    work = inside(workspace, 'engine/.keep').parent
    outputs = inside(workspace, 'outputs/.keep').parent
    reporter.progress(4, 'Preparing', 'Copying the upstream configuration')
    _prepare_configs(work, MODELS)

    mesh = work / ('input' + source.suffix.lower())
    shutil.copyfile(source, mesh)

    env = {**os.environ,
           'PYTHONPATH': str(WORKERS) + os.pathsep + str(SOURCE),
           'MESHSTUDIO_UNIRIG_SOURCE': str(SOURCE),
           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
           'WANDB_MODE': 'disabled', 'PYTHONIOENCODING': 'utf-8',
           'CUDA_VISIBLE_DEVICES': str(parameters.get('gpu_index', 0))}

    def stage(label, arguments, percent, message):
        reporter.progress(percent, message)
        log_path = outputs / (label + '.log')
        with log_path.open('w', encoding='utf-8') as log:
            result = subprocess.run([sys.executable, str(WORKERS / 'unirig' / 'stage.py'), *arguments],
                                    cwd=str(work), env=env, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                                    if sys.platform == 'win32' else 0)
        if result.returncode != 0:
            tail = ''
            try:
                tail = log_path.read_text('utf-8', errors='replace')[-1500:]
            except OSError:
                pass
            raise WorkerError('EngineFailed', f'The {label} stage stopped with code {result.returncode}',
                              details={'log': str(log_path), 'tail': tail})

    faces = int(parameters.get('faces_target', 50000))
    seed = int(parameters.get('seed', 12345))
    stage('extract', ['extract', '--config=configs/data/quick_inference.yaml',
                      '--require_suffix=glb,obj,fbx', '--num_runs=1', '--id=0', '--time=job',
                      '--force_override=true', f'--faces_target_count={faces}',
                      '--input=' + mesh.name, '--output_dir=intermediate'],
          STAGES[0][2], STAGES[0][1])
    folder = work / 'intermediate' / 'input'
    if not (folder / 'raw_data.npz').is_file():
        raise WorkerError('EngineFailed', 'Extraction produced no raw_data.npz; see extract.log',
                          details={'log': str(outputs / 'extract.log')})

    common = ['--input=' + mesh.name, '--npz_dir=intermediate', f'--seed={seed}']
    stage('skeleton', ['predict', '--task=configs/task/quick_inference_skeleton_articulationxl_ar_256.yaml',
                       *common, '--output=' + str(outputs / 'skeleton.fbx')],
          STAGES[1][2], STAGES[1][1])
    stage('skin', ['predict', '--task=configs/task/quick_inference_unirig_skin.yaml',
                   *common, '--output=' + str(outputs / 'skin.fbx')],
          STAGES[2][2], STAGES[2][1])
    stage('export', ['export', str(folder), str(outputs), str(mesh)],
          STAGES[3][2], STAGES[3][1])

    files = {key: str(outputs / name) for key, name in OUTPUT_FILES.items()}
    for key, path in files.items():
        candidate = Path(path)
        if not candidate.is_file() or not candidate.stat().st_size:
            raise WorkerError('InvalidOutput', f'The rig is incomplete: {key} is missing ({path})')

    report = {}
    try:
        report = json.loads((outputs / 'skeleton.json').read_text('utf-8'))
    except (OSError, ValueError):
        pass
    reporter.progress(100, 'Done', f"{report.get('bones', '?')} bones, "
                                   f"{report.get('vertices', '?')} weighted vertices")
    # The schema of the absorbed Tool declares exactly these fields; the duration is
    # reported through the job, not smuggled into the outputs.
    reporter.log(f'Rigging finished in {time.monotonic() - started:.1f} s')
    return {**files, 'engine_revision': _source_revision()}


def diagnose_backend(request, reporter):
    import importlib

    checks = {'source_present': (SOURCE / 'src/inference/download.py').is_file(),
              'source_revision': _source_revision(),
              'models_verified': all((MODELS / name).is_file()
                                     for name in ('skeleton.ckpt', 'skin.ckpt')),
              'model_directory': str(MODELS), 'python': sys.version.split()[0],
              'dependencies': {}}
    for name in ('torch', 'transformers', 'lightning', 'spconv', 'bpy', 'open3d',
                 'trimesh', 'torch_scatter', 'torch_cluster'):
        try:
            module = importlib.import_module(name)
            checks['dependencies'][name] = getattr(module, '__version__', 'OK')
        except Exception as exc:  # noqa: BLE001
            checks['dependencies'][name] = f'{type(exc).__name__}: {exc}'
    try:
        import torch
        checks['cuda_available'] = torch.cuda.is_available()
        checks['gpu_name'] = torch.cuda.get_device_name(0) if checks['cuda_available'] else ''
    except Exception:  # noqa: BLE001
        checks['cuda_available'] = False
    checks['inference_validation'] = ('Not run by this report: readiness checks imports, the '
                                      'checkout and the two checkpoints only.')
    checks.update(memory_report())
    return checks


if __name__ == '__main__':
    raise SystemExit(serve({'mesh_to_rig': mesh_to_rig, 'diagnose': diagnose_backend}))
