"""WHAM backend: a monocular video to 3D human motion, ported from CyTools_WHAM.

Three modes: inspect a video, probe the installation, and reconstruct SMPL poses. The
upstream engine needs Python 3.9 with torch 1.11+cu113, which is why it has an engine of its
own; its weights and the SMPL body model are gated and are not installed by default.

Upstream's build_body_model resets stdout to sys.__stdout__, so that name is pointed at
stderr before anything runs.
"""
import contextlib
import json
import math
import os
from pathlib import Path
import sys
import traceback


sys.path.insert(0, str(Path(__file__).resolve().parent))
from _protocol import WorkerError, inside, isolate_native_output, serve  # noqa: E402
from _legacy import legacy_handler  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'runtime' / 'sources' / 'WHAM'
MODELS = Path(os.environ.get('WHAM_ROOT') or ROOT / 'data' / 'models' / 'wham')
# What each mode needs on disk. dpvo.pth is only read when global motion is asked for, and
# SMPL_NEUTRAL.pkl is the file whose licence is accepted in person on smplify.is.tue.mpg.de.
REQUIRED = ['checkpoints/wham_vit_bedlam_w_3dpw.pth.tar', 'checkpoints/hmr2a.ckpt',
            'checkpoints/vitpose-h-multi-coco.pth', 'checkpoints/yolov8x.pt',
            'dataset/body_models/coco_aug_dict.pth', 'dataset/body_models/smpl_mean_params.npz',
            'dataset/body_models/J_regressor_wham.npy', 'dataset/body_models/J_regressor_h36m.npy',
            'dataset/body_models/J_regressor_feet.npy',
            'dataset/body_models/smpl/SMPL_NEUTRAL.pkl']

isolate_native_output()
# Upstream build_body_model resets stdout to sys.__stdout__; keep that away from the protocol.
sys.__stdout__ = sys.stderr


def progress(p, percent, step):
    target = Path(p['progress'])
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps({'percent': percent, 'step': step}), encoding='utf-8')
    tmp.replace(target)

def inspect(p):
    import cv2
    cap = cv2.VideoCapture(p['video'])
    try:
        if not cap.isOpened():
            raise ValueError('Video illisible ou codec non pris en charge.')
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        expected = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError('Frequence video invalide.')
        count, width, height = 0, 0, 0
        while True:
            ok, frame = cap.read()
            if not ok: break
            height, width = frame.shape[:2]
            if count == 0:
                cv2.imwrite(str(Path(p['output'])/'preview.jpg'), frame)
            count += 1
            if count % 30 == 0:
                progress(p, min(95, count/expected*95), 'Decodage : %d images' % count)
        if count == 0: raise ValueError('Aucune image decodable.')
        result = {'frames': count, 'fps': fps, 'width': width, 'height': height,
                  'duration': count/fps, 'preview': str(Path(p['output'])/'preview.jpg'),
                  'report': str(Path(p['output'])/'video.json')}
        Path(result['report']).write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    finally:
        cap.release()

def probe(p):
    sys.path.insert(0, p['source'])
    os.chdir(p['source'])
    checks = {}
    import importlib
    for name in ('torch', 'cv2', 'mmcv', 'mmpose', 'smplx', 'demo'):
        try:
            module = importlib.import_module(name)
            checks[name] = {'available': True, 'version': getattr(module, '__version__', 'unknown')}
        except Exception as exc:
            checks[name] = {'available': False, 'error': str(exc)}
    try:
        import torch
        checks['cuda'] = {'available': torch.cuda.is_available()}
    except ImportError:
        checks['cuda'] = {'available': False}
    checks['ready'] = all(v['available'] for v in checks.values())
    return checks

def reconstruct(p):
    import types
    import numpy as np
    import torch
    import joblib
    if not torch.cuda.is_available():
        raise RuntimeError('WHAM demande CUDA NVIDIA ; aucun GPU CUDA accessible.')
    sys.path.insert(0, p['source'])
    os.chdir(p['source'])
    from configs import constants
    for namespace in (constants.BMODEL, constants.KEYPOINTS):
        for key, val in vars(namespace).copy().items():
            if isinstance(val, str) and val.startswith('dataset/'):
                setattr(namespace, key, str(Path(p['models'])/val))
    import demo
    from lib.models.preproc import detector, extractor
    detector.ROOT_DIR = extractor.ROOT_DIR = p['models']
    if p['global_motion'] and not demo._run_global:
        raise RuntimeError('DPVO absent : mouvement global indisponible. Choisir coordonnees camera.')
    if p['global_motion']:
        from lib.models.preproc import slam
        slam.ROOT_DIR = p['models']
    cfg = demo.get_cfg_defaults()
    cfg.merge_from_file('configs/yamls/demo.yaml')
    cfg.TRAIN.CHECKPOINT = str(Path(p['models'])/'checkpoints/wham_vit_bedlam_w_3dpw.pth.tar')
    cfg.FLIP_EVAL = p['flip_eval']
    cfg.DEVICE = 'cuda'
    torch.cuda.set_device(p['gpu_index'])
    demo.args = types.SimpleNamespace(run_smplify=p['refine'])
    progress(p, 5, 'Chargement SMPL et WHAM')
    demo.smpl = demo.build_body_model(cfg.DEVICE, cfg.TRAIN.BATCH_SIZE*cfg.DATASET.SEQLEN)
    network = demo.build_network(cfg, demo.smpl)
    network.eval()
    base_track = demo.DetectionModel.track
    def track(self, img, fps, length):
        result = base_track(self, img, fps, length)
        progress(p, 10+45*self.frame_id/max(1,length), 'Detection %d/%d' % (self.frame_id,length))
        return result
    demo.DetectionModel.track = track
    base_extract = demo.FeatureExtractor.run
    def extract(self, *args, **kwargs):
        progress(p, 58, 'Extraction des caracteristiques')
        result = base_extract(self, *args, **kwargs)
        progress(p, 78, 'Reconstruction des personnes')
        return result
    demo.FeatureExtractor.run = extract
    demo.run(cfg, p['video'], p['output'], network, run_global=p['global_motion'], save_pkl=True, visualize=False)
    raw = Path(p['output'])/'wham_output.pkl'
    results = joblib.load(raw)  # Only this worker's freshly generated result, never arbitrary input pickle.
    return export_motion(results,network.smpl.J_regressor.detach().cpu().numpy(),p)

def export_motion(results,regressor,p):
    import numpy as np
    if not results: raise ValueError('Aucune personne suivie pendant au moins 30 images.')
    arrays, persons = {}, []
    for person, values in results.items():
        entry = {'id': int(person)}
        arrays['person_%s_joints_camera' % person] = np.einsum('jv,fvc->fjc',regressor,np.asarray(values['verts']))
        if not np.isfinite(arrays['person_%s_joints_camera' % person]).all():
            raise ValueError('Articulations non finies.')
        keys = ['pose', 'trans', 'betas', 'frame_ids']
        if p['global_motion']: keys += ['pose_world', 'trans_world']
        for key in keys:
            array = np.asarray(values[key])
            if not np.issubdtype(array.dtype, np.number) or not np.isfinite(array).all():
                raise ValueError('WHAM a produit des valeurs non finies.')
            arrays['person_%s_%s' % (person,key)] = array
            entry[key] = list(array.shape)
        persons.append(entry)
    result_path = Path(p['output'])/'motion.npz'
    np.savez_compressed(str(result_path), **arrays)
    report = Path(p['output'])/'motion.json'
    report.write_text(json.dumps({'persons': persons, 'coordinates': 'world' if p['global_motion'] else 'camera',
                                 'poseRepresentation': 'SMPL axis-angle, radians', 'translationUnit': 'metres'}, indent=2))
    progress(p, 100, 'Exports verifies')
    return {'motion': str(result_path), 'report': str(report), 'people': len(persons),
            'coordinates': 'world' if p['global_motion'] else 'camera'}

def _execute(parameters):
    Path(parameters['output']).mkdir(parents=True, exist_ok=True)
    mode = parameters.get('mode', 'inspect')
    return {'inspect': inspect, 'probe': probe, 'reconstruct': reconstruct}[mode](parameters)


def _missing(global_motion):
    wanted = list(REQUIRED) + (['checkpoints/dpvo.pth'] if global_motion else [])
    return [name for name in wanted if not (MODELS / name).is_file()]


def _prepare(mode, parameters, workspace):
    """Give the ported code the paths it expects, and refuse early when a weight is absent.

    The upstream code reads its checkpoints deep inside model construction, so an absent file
    would surface as a stack trace about a pickle. The check belongs here, where it can name
    the files and the page where their licence is accepted.
    """
    output = inside(workspace, 'outputs/.keep').parent
    output.mkdir(parents=True, exist_ok=True)
    prepared = dict(parameters)
    prepared.update(mode=mode, source=str(SOURCE), models=str(MODELS), output=str(output),
                    progress=str(output / 'progress.json'))
    prepared.setdefault('global_motion', False)
    prepared.setdefault('flip_eval', True)
    prepared.setdefault('refine', False)
    prepared.setdefault('gpu_index', 0)
    if mode == 'reconstruct':
        if not (SOURCE / 'demo.py').is_file():
            raise WorkerError('MissingDependency',
                              f'The WHAM sources are absent from {SOURCE}. Install the "wham" '
                              'engine from the Installation tab.', recoverable=True)
        missing = _missing(bool(prepared['global_motion']))
        if missing:
            smpl = 'dataset/body_models/smpl/SMPL_NEUTRAL.pkl'
            hint = ('Install the model "wham" from the Installation tab. '
                    + ('The SMPL body model is downloaded in person from '
                       'https://smplify.is.tue.mpg.de, then imported there. '
                       if smpl in missing else ''))
            raise WorkerError('MissingModel',
                              f'{len(missing)} WHAM file(s) are missing from {MODELS}: '
                              f'{", ".join(missing[:4])}{"..." if len(missing) > 4 else ""}. {hint}',
                              details={'missing': missing, 'directory': str(MODELS)},
                              recoverable=True)
    return prepared


def _classify(exc):
    if isinstance(exc, ImportError):
        return 'MissingDependency', str(exc)
    if isinstance(exc, FileNotFoundError):
        return 'MissingModel', str(exc)
    return 'InferenceFailed', f'{type(exc).__name__}: {exc}'


_BASE = legacy_handler(
    _execute,
    progress_of=lambda parameters, workspace: Path(parameters.get('progress')
                                                   or Path(parameters.get('output', workspace)) / 'progress.json'),
    classify=_classify)


def _handler(mode):
    def handle(request, reporter):
        workspace = Path(request.get('workspace') or '.')
        prepared = dict(request)
        prepared['parameters'] = _prepare(mode, dict(request.get('parameters') or {}), workspace)
        return _BASE(prepared, reporter)
    return handle


def diagnose(request, reporter):
    """What is installed, without loading anything: the panel calls this on a cold machine."""
    missing = _missing(True)
    return {'engine': 'WHAM', 'python': sys.version.split()[0], 'models': str(MODELS),
            'source': str(SOURCE), 'sourcePresent': (SOURCE / 'demo.py').is_file(),
            'missing': missing, 'ready': not _missing(False) and (SOURCE / 'demo.py').is_file(),
            'globalMotionReady': not missing}


if __name__ == '__main__':
    raise SystemExit(serve({'reconstruct': _handler('reconstruct'),
                            'inspect_video': _handler('inspect'),
                            'probe': _handler('probe'),
                            'diagnose': diagnose}))
