"""Understanding backend: masks, relative depth, camera cues and synthetic views.

Ported from CyTools_MeshConstruct. The models only supply visual constraints; they never
produce geometry, and the fitting engine that does is a separate process on the CPU.
Models are loaded one at a time on purpose: three of them do not fit next to a diffusion
pipeline on a 24 GiB card.
"""
import json
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _protocol import isolate_native_output, serve  # noqa: E402
from _legacy import legacy_handler  # noqa: E402

isolate_native_output()
import time
from pathlib import Path


def note(output, percent, step):
    try: (Path(output) / 'progress.json').write_text(json.dumps({'percent': percent, 'step': step}), encoding='utf-8')
    except OSError: pass


def pick_device(requested):
    import torch
    if requested == 'cpu': return 'cpu'
    if torch.cuda.is_available(): return 'cuda'
    if requested == 'cuda':
        raise RuntimeError('DeviceUnavailable: CUDA was requested but PyTorch sees no CUDA device')
    return 'cpu'


def prior_box(rgba):
    """Rough object box from alpha or a border-colour background model (no learning)."""
    import cv2, numpy as np
    h, w = rgba.shape[:2]
    if rgba.shape[2] == 4 and 0.01 < (rgba[..., 3] > 127).mean() < 0.98:
        ys, xs = np.nonzero(rgba[..., 3] > 127)
        return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], 'alpha', rgba[..., 3] > 127
    lab = cv2.cvtColor(np.ascontiguousarray(rgba[..., :3]), cv2.COLOR_RGB2LAB).astype(np.float32)
    b = max(2, min(h, w) // 40)
    border = np.concatenate([lab[:b].reshape(-1, 3), lab[-b:].reshape(-1, 3), lab[:, :b].reshape(-1, 3), lab[:, -b:].reshape(-1, 3)])
    median = np.median(border, 0)
    spread = float(np.median(np.linalg.norm(border - median, axis=1)))
    if spread < 12.0:
        rough = np.linalg.norm(lab - median, axis=2) > max(10.0, 3.5 * spread + 6.0)
        rough = cv2.morphologyEx(rough.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
        if 0.005 < rough.mean() < 0.95:
            ys, xs = np.nonzero(rough)
            return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], 'border-colour', rough
    return [w // 12, h // 12, w - w // 12, h - h // 12], 'central', None


def prompt_points(rough, count=6):
    """Well-spread positive clicks inside a reliable prior: detached or differently coloured parts
    (far wing, fin) are then kept in the same object mask."""
    import cv2, numpy as np
    distance = cv2.distanceTransform(rough.astype(np.uint8), cv2.DIST_L2, 5)
    radius = max(8, int(0.12 * max(rough.shape)))
    points = []
    for _ in range(count):
        y, x = np.unravel_index(int(np.argmax(distance)), distance.shape)
        if distance[y, x] < 2: break
        points.append([float(x), float(y)])
        cv2.circle(distance, (int(x), int(y)), radius, 0, -1)
    return points


def segment(items, folder, device, output, results):
    import numpy as np, torch
    from PIL import Image
    from transformers import Sam2Model, Sam2Processor
    started = time.monotonic()
    processor = Sam2Processor.from_pretrained(folder)
    model = Sam2Model.from_pretrained(folder, dtype=torch.float32).to(device).eval()
    load_seconds = time.monotonic() - started
    for index, item in enumerate(items):
        note(output, 5 + 40 * index / len(items), 'SAM 2.1: ' + item['name'])
        image = Image.open(item['image']); image.load()
        rgba = np.asarray(image.convert('RGBA'))
        h, w = rgba.shape[:2]
        rough = None
        if item.get('box'):
            x0, y0, x1, y1 = item['box']; box, source = [int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)], 'user-box'
        else:
            box, source, rough = prior_box(rgba if image.mode in ('RGBA', 'LA', 'PA') else rgba[..., :3])
        rgb = Image.fromarray(rgba[..., :3])
        prompts = {'input_boxes': [[[float(v) for v in box]]]}
        points = prompt_points(rough) if rough is not None else []
        if points:
            prompts.update(input_points=[[points]], input_labels=[[[1] * len(points)]])
        inputs = processor(images=rgb, return_tensors='pt', **prompts).to(device)
        with torch.inference_mode():
            outputs = model(**inputs, multimask_output=True)
        masks = processor.post_process_masks(outputs.pred_masks.cpu(), inputs['original_sizes'])[0][0]   # (3, H, W)
        scores = outputs.iou_scores.float().cpu().numpy().reshape(-1)
        # Prefer the candidate that fills the prompt box best: the whole object, not a part.
        area = max((box[2] - box[0]) * (box[3] - box[1]), 1)
        inside = [float(m[box[1]:box[3] + 1, box[0]:box[2] + 1].sum()) / area for m in masks.numpy()]
        best = int(np.argmax([s * (0.5 + min(f, 1.0)) for s, f in zip(scores, inside)]))
        mask = masks[best].numpy().astype(bool)
        if rough is not None:   # a plain background is itself strong evidence: never lose a part of it
            import cv2
            mask |= cv2.erode(rough.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
            source += '+prior-union'
        path = Path(output) / f"{index:02d}_mask.png"
        Image.fromarray((mask * 255).astype(np.uint8)).save(path)
        results[item['name']].update(mask=str(path), maskMethod='sam2.1(' + source + ')', maskConfidence=round(float(scores[best]), 4),
                                     maskBox=box, maskAreaRatio=round(float(mask.mean()), 4))
    peak = torch.cuda.max_memory_allocated() if device == 'cuda' else 0
    del model, processor
    if device == 'cuda': torch.cuda.empty_cache()
    return {'loadSeconds': round(load_seconds, 2), 'peakVramBytes': int(peak)}


def depth(items, folder, device, output, results):
    import numpy as np, torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    started = time.monotonic()
    processor = AutoImageProcessor.from_pretrained(folder)
    model = AutoModelForDepthEstimation.from_pretrained(folder).to(device).eval()
    load_seconds = time.monotonic() - started
    if device == 'cuda': torch.cuda.reset_peak_memory_stats()
    for index, item in enumerate(items):
        note(output, 50 + 40 * index / len(items), 'Depth Anything V2: ' + item['name'])
        image = Image.open(item['image']).convert('RGB')
        inputs = processor(images=image, return_tensors='pt').to(device)
        with torch.inference_mode():
            outputs = model(**inputs)
        post = processor.post_process_depth_estimation(outputs, target_sizes=[(image.height, image.width)])
        value = post[0]['predicted_depth'].float().cpu().numpy()      # relative inverse depth: larger = closer
        lo, hi = float(value.min()), float(value.max())
        value = (value - lo) / max(hi - lo, 1e-9)
        path = Path(output) / f"{index:02d}_depth.npy"
        np.save(path, value.astype(np.float16))
        Image.fromarray((value * 255).astype(np.uint8)).save(Path(output) / f"{index:02d}_depth.png")
        results[item['name']].update(depth=str(path), depthKind='relative inverse depth, affine-invariant (not metric)')
    peak = torch.cuda.max_memory_allocated() if device == 'cuda' else 0
    del model, processor
    if device == 'cuda': torch.cuda.empty_cache()
    return {'loadSeconds': round(load_seconds, 2), 'peakVramBytes': int(peak)}


def camera_cues(items, spec, device, output, results):
    """Perspective Fields (Paramnet-360Cities-edina-centered): roll, pitch and vertical field of view of each real
    picture. It was trained on scenes: on a cut-out object over a plain background the cue is weak, which is why
    the Tool keeps it as a cue with a confidence, below any user angle."""
    import sys as _sys
    import numpy as np, torch, cv2
    _sys.path.insert(0, spec['engine'])
    weights = str(Path(spec['path']) / 'paramnet_360cities_edina_rpf.pth')
    original = torch.hub.load_state_dict_from_url
    torch.hub.load_state_dict_from_url = lambda url, map_location=None, **kw: torch.load(weights, map_location=map_location or 'cpu', weights_only=False)
    try:
        from perspective2d import PerspectiveFields
        started = time.monotonic()
        model = PerspectiveFields('Paramnet-360Cities-edina-centered').eval().to(device)
    finally:
        torch.hub.load_state_dict_from_url = original
    load_seconds = time.monotonic() - started
    if device == 'cuda': torch.cuda.reset_peak_memory_stats()
    for index, item in enumerate(items):
        note(output, 92 + 6 * index / len(items), 'Perspective Fields: ' + item['name'])
        bgr = cv2.imread(item['image'], cv2.IMREAD_COLOR)
        if bgr is None:
            from PIL import Image
            bgr = cv2.cvtColor(np.asarray(Image.open(item['image']).convert('RGB')), cv2.COLOR_RGB2BGR)
        h, w = bgr.shape[:2]
        from PIL import Image as _Image
        context = prior_box(np.asarray(_Image.open(item['image']).convert('RGBA')))[1]
        scene = context == 'central'       # a real scene around the object; alpha / plain background = cut-out
        prediction = model.inference(img_bgr=bgr)
        roll, pitch, vfov = (float(prediction[k].cpu().item()) for k in ('pred_roll', 'pred_pitch', 'pred_general_vfov'))
        # Tool field of view = along the longest side of the full picture.
        fov = vfov if h >= w else float(np.degrees(2 * np.arctan(np.tan(np.radians(vfov) / 2) * w / h)))
        results[item['name']]['cameraCue'] = {'source': 'perspective-fields', 'roll': round(roll, 2), 'pitch': round(pitch, 2),
                                              'elevation': round(PITCH_TO_ELEVATION * pitch, 2), 'verticalFov': round(vfov, 2), 'fov': round(fov, 2),
                                              'usable': bool(scene), 'confidence': 0.6 if scene else 0.1,
                                              'note': None if scene else 'cut-out object on a plain background: the network was trained on scenes, the cue is reported but not used'}
    peak = torch.cuda.max_memory_allocated() if device == 'cuda' else 0
    del model
    if device == 'cuda': torch.cuda.empty_cache()
    return {'loadSeconds': round(load_seconds, 2), 'peakVramBytes': int(peak)}


PITCH_TO_ELEVATION = -1.0     # camera pitched down (negative pitch) = camera above the object (positive elevation); checked in VALIDATION.md
ZERO123_VIEWS = [(30, 20), (90, -10), (150, 20), (210, -10), (270, 20), (330, -10)]   # v1.2: azimuth relative to the input, absolute elevation
ZERO123_FOV = 30.0


def synthesize(p, device, output):
    """Zero123++ v1.2: six views at known poses from one real picture. They are hypotheses of the
    unseen sides: the fitting engine gives them a reduced weight and never lets them override a photograph."""
    import numpy as np, torch
    from PIL import Image
    from diffusers import DiffusionPipeline, EulerAncestralDiscreteScheduler
    if device != 'cuda':
        raise RuntimeError('DeviceUnavailable: Zero123++ view synthesis is only supported on a CUDA GPU in this Tool')
    folder = Path(p['synthesis']['path'])
    note(output, 3, 'Zero123++: loading')
    started = time.monotonic()
    pipe = DiffusionPipeline.from_pretrained(str(folder), custom_pipeline=str(folder / 'pipeline'), torch_dtype=torch.float16, local_files_only=True)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config, timestep_spacing='trailing')
    pipe.to(device)
    load_seconds = time.monotonic() - started
    torch.cuda.reset_peak_memory_stats()
    source = p['synthesis']['source']
    rgba = np.asarray(Image.open(source['image']).convert('RGBA')).copy()
    if source.get('mask'):
        mask = np.asarray(Image.open(source['mask']).convert('L').resize((rgba.shape[1], rgba.shape[0]))) > 127
    else:
        mask = prior_box(rgba)[2]
        if mask is None: mask = np.ones(rgba.shape[:2], bool)
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    side = int(max(x1 - x0, y1 - y0) / 0.85)                       # object fills 85 % of a white square
    canvas = np.full((side, side, 3), 255, np.uint8)
    crop, keep = rgba[y0:y1, x0:x1, :3], mask[y0:y1, x0:x1]
    oy, ox = (side - crop.shape[0]) // 2, (side - crop.shape[1]) // 2
    region = canvas[oy:oy + crop.shape[0], ox:ox + crop.shape[1]]
    region[keep] = crop[keep]
    condition = Image.fromarray(canvas).resize((512, 512), Image.LANCZOS)
    condition.save(Path(output) / 'zero123_condition.png')
    steps = int(p['synthesis'].get('steps', 36))
    def progress(pipeline, step, timestep, kwargs):
        note(output, 10 + 80 * (step + 1) / steps, f'Zero123++: step {step + 1}/{steps}')
        return kwargs
    generator = torch.Generator(device=device).manual_seed(int(p['synthesis'].get('seed', 0)))
    try:
        sheet = pipe(condition, num_inference_steps=steps, guidance_scale=float(p['synthesis'].get('guidance', 4.0)),
                     generator=generator, callback_on_step_end=progress).images[0]
    except TypeError:      # pipeline revision without step callbacks
        sheet = pipe(condition, num_inference_steps=steps, guidance_scale=float(p['synthesis'].get('guidance', 4.0)), generator=generator).images[0]
    sheet.save(Path(output) / 'zero123_sheet.png')
    width, height = sheet.size[0] // 2, sheet.size[1] // 3
    views = []
    for index, (azimuth, elevation) in enumerate(ZERO123_VIEWS):
        row, col = divmod(index, 2)
        tile = sheet.crop((col * width, row * height, (col + 1) * width, (row + 1) * height))
        path = Path(output) / f'zero123_{index}_az{azimuth:03d}_el{elevation:+03d}.png'
        tile.save(path)
        views.append({'image': str(path), 'generatorAzimuth': azimuth, 'elevation': elevation, 'fov': ZERO123_FOV})
    peak = torch.cuda.max_memory_allocated()
    del pipe
    torch.cuda.empty_cache()
    note(output, 100, 'Zero123++: views generated')
    return {'generated': views, 'stats': {'model': p['synthesis']['id'], 'device': device, 'steps': steps, 'seed': int(p['synthesis'].get('seed', 0)),
                                           'loadSeconds': round(load_seconds, 2), 'peakVramBytes': int(peak)}}


def execute(p):
    if p.get('task') == 'diagnose':
        info = {'python': sys.version.split()[0]}
        try:
            import torch, transformers
            try:
                import diffusers; info['diffusers'] = diffusers.__version__
            except ImportError: info['diffusers'] = None
            info.update(torch=torch.__version__, transformers=transformers.__version__, cuda=torch.cuda.is_available(),
                        cudaRuntime=torch.version.cuda,
                        device=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                        sam2=hasattr(transformers, 'Sam2Model'))
        except Exception as exc:
            return {'error': {'code': 'MissingDependency', 'message': str(exc)}}
        return info
    import torch
    output = Path(p['output']); output.mkdir(parents=True, exist_ok=True)
    device = pick_device(p.get('device', 'auto'))
    if p.get('task') == 'synthesize':
        return synthesize(p, device, output)
    results = {item['name']: {} for item in p['images']}
    stats = {'device': device, 'torch': torch.__version__}
    if device == 'cuda':
        stats['deviceName'] = torch.cuda.get_device_name(0); torch.cuda.reset_peak_memory_stats()
    # Sequential loading: one model in memory at a time.
    wanted = [i for i in p['images'] if i.get('needMask', True)]
    if p.get('segmentation') and wanted:
        stats['segmentation'] = {'model': p['segmentation']['id'], **segment(wanted, p['segmentation']['path'], device, output, results)}
    if p.get('depth'):
        stats['depth'] = {'model': p['depth']['id'], **depth(p['images'], p['depth']['path'], device, output, results)}
    if p.get('camera'):
        stats['camera'] = {'model': p['camera']['id'], **camera_cues([i for i in p['images'] if i.get('kind', 'real') == 'real'], p['camera'], device, output, results)}
    note(output, 100, 'Understanding complete')
    return {'views': results, 'stats': stats}


def _classify(exc):
    text = str(exc)
    if text.startswith('DeviceUnavailable'):
        return 'DeviceUnavailable', text
    if 'out of memory' in text.lower():
        return 'InsufficientVRAM', text
    return 'UnderstandingFailed', text[:2000]


if __name__ == '__main__':
    handler = legacy_handler(execute, classify=_classify)
    raise SystemExit(serve({'understand': handler, 'synthesize': handler, 'diagnose': handler}))
