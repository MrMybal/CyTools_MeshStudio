"""Object segmentation. Two implemented backends: SAM 2.1 and a classical fallback.

Both return the same contract so the rest of the pipeline never depends on which
one produced the mask: ``{'mask', 'boxes', 'method', 'confidence', 'notes'}``.
"""
import numpy as np

from . import imaging

SEGMENT_BACKENDS = ('sam2', 'classical', 'alpha')


def largest_component(mask):
    import cv2
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (mask > 127).astype(np.uint8), connectivity=8)
    if count <= 1:
        return mask
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = int(np.argmax(areas)) + 1
    return ((labels == keep).astype(np.uint8) * 255)


def refine(mask, radius=3):
    """Close pinholes and smooth the border without eating thin structures."""
    import cv2
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    mask = cv2.morphologyEx((mask > 127).astype(np.uint8) * 255, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    filled = mask.copy()
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return largest_component(filled)


def border_background_ratio(mask):
    """Fraction of the image border that the mask leaves as background."""
    border = np.concatenate([mask[0, :], mask[-1, :], mask[:, 0], mask[:, -1]])
    return float(np.mean(border <= 127))


def classical(rgb, *, border_fraction=0.04):
    """GrabCut initialised from the image border. No model and no network access."""
    import cv2
    height, width = rgb.shape[:2]
    inset_y = max(1, int(height * border_fraction))
    inset_x = max(1, int(width * border_fraction))
    state = np.full((height, width), cv2.GC_PR_FGD, dtype=np.uint8)
    state[:inset_y, :] = cv2.GC_BGD
    state[-inset_y:, :] = cv2.GC_BGD
    state[:, :inset_x] = cv2.GC_BGD
    state[:, -inset_x:] = cv2.GC_BGD
    centre_y, centre_x = height // 2, width // 2
    radius_y, radius_x = max(1, height // 6), max(1, width // 6)
    state[centre_y - radius_y:centre_y + radius_y, centre_x - radius_x:centre_x + radius_x] = cv2.GC_FGD
    background = np.zeros((1, 65), np.float64)
    foreground = np.zeros((1, 65), np.float64)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    cv2.grabCut(bgr, state, None, background, foreground, 5, cv2.GC_INIT_WITH_MASK)
    mask = np.where((state == cv2.GC_FGD) | (state == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    mask = refine(mask)
    coverage = float(np.mean(mask > 127))
    # A plausible object covers part of the frame and leaves the border alone.
    confidence = 0.0
    if 0.02 < coverage < 0.92:
        confidence = min(0.75, 0.35 + 0.4 * border_background_ratio(mask))
    notes = []
    if coverage <= 0.02 or coverage >= 0.92:
        notes.append('Classical segmentation did not isolate a plausible object; '
                     'the whole frame is used instead.')
        mask = np.full((height, width), 255, np.uint8)
    return {'mask': mask, 'method': 'classical-grabcut', 'confidence': round(confidence, 3),
            'notes': notes}


_SAM = {}


def sam2_model(model_dir, device):
    """Load SAM 2.1 through transformers once per worker process."""
    key = (str(model_dir), device)
    if key not in _SAM:
        import torch
        from transformers import Sam2Model, Sam2Processor
        processor = Sam2Processor.from_pretrained(str(model_dir))
        model = Sam2Model.from_pretrained(str(model_dir),
                                          dtype=torch.float32).to(device).eval()
        _SAM[key] = (processor, model)
    return _SAM[key]


def sam2(rgb, model_dir, device='cuda', *, points=None):
    """Prompt SAM 2.1 with a central box and a small point grid on the object."""
    import torch
    from PIL import Image
    processor, model = sam2_model(model_dir, device)
    height, width = rgb.shape[:2]
    box = [[[0.08 * width, 0.08 * height, 0.92 * width, 0.92 * height]]]
    if points is None:
        offsets = (0.5, 0.35, 0.65)
        points = [[[[width * x, height * y] for x in offsets for y in offsets]]]
        labels = [[[1] * (len(offsets) ** 2)]]
    else:
        points = [[[[float(x), float(y)] for x, y in points]]]
        labels = [[[1] * len(points[0][0])]]
    inputs = processor(images=Image.fromarray(rgb), input_boxes=box, input_points=points,
                       input_labels=labels, return_tensors='pt').to(device)
    with torch.inference_mode():
        outputs = model(**inputs, multimask_output=True)
    masks = processor.post_process_masks(outputs.pred_masks.cpu(),
                                         inputs['original_sizes'].cpu())[0]
    scores = outputs.iou_scores.detach().float().cpu().numpy().reshape(-1)
    masks = np.asarray(masks).reshape(-1, height, width)
    best = int(np.argmax(scores))
    mask = refine((masks[best] > 0).astype(np.uint8) * 255)
    coverage = float(np.mean(mask > 127))
    notes = []
    confidence = float(np.clip(scores[best], 0.0, 1.0))
    if coverage <= 0.01 or coverage >= 0.97:
        notes.append('SAM 2.1 returned an implausible mask coverage of %.1f%%; '
                     'the whole frame is used instead.' % (coverage * 100))
        mask = np.full((height, width), 255, np.uint8)
        confidence = min(confidence, 0.2)
    return {'mask': mask, 'method': 'sam2.1', 'confidence': round(confidence, 3), 'notes': notes}


def segment(rgb, alpha, *, backend, model_dir=None, device='cuda'):
    """Dispatch to the requested backend and always return a usable mask."""
    if backend == 'alpha':
        if alpha is None:
            return {'mask': np.full(rgb.shape[:2], 255, np.uint8), 'method': 'alpha-missing',
                    'confidence': 0.0,
                    'notes': ['The image has no alpha channel; the whole frame is used.']}
        mask = refine(imaging.binary_mask(alpha))
        return {'mask': mask, 'method': 'alpha-channel', 'confidence': 0.99, 'notes': []}
    if backend == 'sam2':
        if model_dir is None:
            raise ValueError('SAM 2.1 weights are not installed')
        result = sam2(rgb, model_dir, device)
    elif backend == 'classical':
        result = classical(rgb)
    else:
        raise ValueError('Unknown segmentation backend: ' + str(backend))
    if alpha is not None and result['confidence'] < 0.5:
        supplied = refine(imaging.binary_mask(alpha))
        if 0.01 < float(np.mean(supplied > 127)) < 0.97:
            result = {'mask': supplied, 'method': result['method'] + '+alpha-channel',
                      'confidence': 0.9,
                      'notes': result['notes'] + ['The supplied alpha channel was more reliable '
                                                  'than the segmentation backend.']}
    result['boundingBox'] = imaging.bounding_box(result['mask'])
    result['coverage'] = round(float(np.mean(result['mask'] > 127)), 4)
    return result
