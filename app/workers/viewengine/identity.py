"""Same-object verification and generated-view consistency, from measurable evidence.

Every signal is computed on the segmented object, never on the background, and each
one is reported separately so a low aggregate can be explained rather than trusted.
"""
import numpy as np

from . import imaging, pose

_EMBEDDER = {}
# Weights of the individual signals in the aggregate confidence. They are reported
# in the output so a caller can recompute the aggregate with its own policy.
IDENTITY_WEIGHTS = {'embedding': 0.45, 'features': 0.2, 'colour': 0.2, 'silhouette': 0.15}
SUSPICIOUS_BELOW = 0.55


def embedder(model_dir, device):
    if str(model_dir) not in _EMBEDDER:
        import torch
        from transformers import AutoImageProcessor, AutoModel
        processor = AutoImageProcessor.from_pretrained(str(model_dir))
        model = AutoModel.from_pretrained(str(model_dir), dtype=torch.float32).to(device).eval()
        _EMBEDDER[str(model_dir)] = (processor, model)
    return _EMBEDDER[str(model_dir)]


def embed(images, model_dir, device='cuda'):
    """L2-normalised DINOv2 CLS embeddings of the cropped, masked objects."""
    import torch
    from PIL import Image
    processor, model = embedder(model_dir, device)
    inputs = processor(images=[Image.fromarray(x) for x in images], return_tensors='pt').to(device)
    with torch.inference_mode():
        output = model(**inputs)
    vectors = output.last_hidden_state[:, 0].float().cpu().numpy()
    return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)


def colour_histogram(rgb, mask, bins=24):
    """Hue/saturation histogram of the object pixels only."""
    import cv2
    selection = mask > 127
    if not selection.any():
        return np.zeros(bins * bins, dtype=np.float32)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    values = hsv[selection]
    histogram, _, _ = np.histogram2d(values[:, 0], values[:, 1], bins=bins,
                                     range=[[0, 180], [0, 256]])
    histogram = histogram.astype(np.float32).reshape(-1)
    return histogram / max(histogram.sum(), 1.0)


def histogram_intersection(first, second):
    return float(np.minimum(first, second).sum())


def silhouette_similarity(first, second):
    """Scale-free silhouette agreement from aspect, fill, solidity and Hu moments."""
    aspect = 1.0 - min(1.0, abs(first['aspect'] - second['aspect']) /
                       max(first['aspect'], second['aspect'], 1e-6))
    fill = 1.0 - min(1.0, abs(first['fill'] - second['fill']))
    solidity = 1.0 - min(1.0, abs(first['solidity'] - second['solidity']))
    hu = 1.0 - min(1.0, float(np.mean(np.abs(np.array(first['hu']) - np.array(second['hu'])))) / 4.0)
    return float(np.clip(0.3 * aspect + 0.2 * fill + 0.2 * solidity + 0.3 * hu, 0.0, 1.0))


def feature_similarity(first, second):
    """Normalised count of ratio-test correspondences between two masked views."""
    points_a, _ = pose.match_features(first, second)
    return float(np.clip(len(points_a) / 80.0, 0.0, 1.0)), int(len(points_a))


def pairwise(items, embeddings):
    """Full matrix of pairwise evidence between the analysed images."""
    results = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            embedding = float(np.dot(embeddings[i], embeddings[j])) if embeddings is not None else None
            features, matches = feature_similarity(items[i]['keypoints'], items[j]['keypoints'])
            colour = histogram_intersection(items[i]['histogram'], items[j]['histogram'])
            shape = silhouette_similarity(items[i]['metrics'], items[j]['metrics'])
            signals = {'embedding': embedding, 'features': features,
                       'colour': colour, 'silhouette': shape}
            available = {k: v for k, v in signals.items() if v is not None}
            total = sum(IDENTITY_WEIGHTS[k] for k in available)
            score = sum(IDENTITY_WEIGHTS[k] * v for k, v in available.items()) / max(total, 1e-9)
            results.append({
                'first': items[i]['name'], 'second': items[j]['name'],
                'firstIndex': i, 'secondIndex': j,
                'embeddingSimilarity': None if embedding is None else round(embedding, 4),
                'featureSimilarity': round(features, 4), 'featureMatches': matches,
                'colourSimilarity': round(colour, 4), 'silhouetteSimilarity': round(shape, 4),
                'sameObjectConfidence': round(float(np.clip(score, 0.0, 1.0)), 4)})
    return results


def same_object(items, embeddings):
    """Aggregate verdict plus the images that disagree with the rest of the set."""
    if len(items) < 2:
        return {'sameObjectConfidence': 1.0, 'pairs': [], 'suspiciousImages': [],
                'weights': dict(IDENTITY_WEIGHTS), 'threshold': SUSPICIOUS_BELOW,
                'notes': ['A single image cannot be compared with another view.']}
    pairs = pairwise(items, embeddings)
    scores = [p['sameObjectConfidence'] for p in pairs]
    suspicious = []
    for index, item in enumerate(items):
        related = [p['sameObjectConfidence'] for p in pairs
                   if index in (p['firstIndex'], p['secondIndex'])]
        best = max(related) if related else 0.0
        if best < SUSPICIOUS_BELOW:
            suspicious.append({'image': item['name'], 'index': index,
                               'bestPairConfidence': round(best, 4),
                               'reason': 'No other supplied view supports the same object.'})
    notes = []
    if any(p['featureMatches'] < pose.MIN_MATCHES for p in pairs):
        notes.append('Some pairs share very few correspondences. Wide baselines such as front '
                     'against rear legitimately produce few matches, so a low feature score '
                     'alone does not prove a different object.')
    return {'sameObjectConfidence': round(float(np.mean(scores)), 4),
            'minimumPairConfidence': round(float(np.min(scores)), 4),
            'pairs': pairs, 'suspiciousImages': suspicious,
            'weights': dict(IDENTITY_WEIGHTS), 'threshold': SUSPICIOUS_BELOW, 'notes': notes}


def prepare(rgb, mask, *, name, crop=True):
    """Everything the identity and consistency checks need from one image."""
    gray = imaging.to_gray(rgb)
    cropped_rgb, cropped_mask = imaging.crop_to_object(rgb, mask) if crop else (rgb, mask)
    masked = cropped_rgb.copy()
    masked[cropped_mask <= 127] = 255
    return {'name': name, 'rgb': rgb, 'mask': mask, 'gray': gray,
            'cropped': imaging.resize(masked, (224, 224)),
            'metrics': pose.silhouette_metrics(mask),
            'histogram': colour_histogram(rgb, mask),
            'keypoints': pose.masked_keypoints(gray, mask),
            'sharpness': imaging.sharpness(gray, mask)}


def consistency(candidate, references, *, embeddings=None, mirror_reference=None):
    """Score one generated view against the real views of the same object."""
    scores = {}
    notes = []
    if embeddings is not None and len(references):
        similarities = [float(np.dot(embeddings[0], value)) for value in embeddings[1:]]
        scores['objectIdentity'] = float(np.clip(max(similarities), 0.0, 1.0))
        scores['objectIdentityMean'] = float(np.clip(np.mean(similarities), 0.0, 1.0))
    if references:
        colour = max(histogram_intersection(candidate['histogram'], r['histogram']) for r in references)
        scores['colourMaterial'] = float(np.clip(colour, 0.0, 1.0))
        shape = max(silhouette_similarity(candidate['metrics'], r['metrics']) for r in references)
        scores['majorProportions'] = shape
        features = max(feature_similarity(candidate['keypoints'], r['keypoints'])[0] for r in references)
        scores['featureConsistency'] = features
        areas = [r['metrics']['relativeArea'] for r in references]
        reference_area = float(np.median(areas)) if areas else 0.0
        area = candidate['metrics']['relativeArea']
        if reference_area > 0:
            ratio = min(area, reference_area) / max(area, reference_area)
            scores['silhouetteConsistency'] = float(np.clip(ratio, 0.0, 1.0))
            if ratio < 0.4:
                notes.append('The generated silhouette covers a very different image fraction '
                             'than the real views.')
    if mirror_reference is not None:
        mirrored = dict(mirror_reference['metrics'])
        scores['symmetryConsistency'] = silhouette_similarity(candidate['metrics'], mirrored)
    if candidate['metrics']['relativeArea'] < 0.005:
        notes.append('The generated view contains almost no object pixels.')
    weights = {'objectIdentity': 0.35, 'featureConsistency': 0.15, 'colourMaterial': 0.2,
               'majorProportions': 0.15, 'silhouetteConsistency': 0.1, 'symmetryConsistency': 0.05}
    available = {k: v for k, v in scores.items() if k in weights}
    total = sum(weights[k] for k in available)
    value = sum(weights[k] * v for k, v in available.items()) / max(total, 1e-9) if available else 0.0
    return {'signals': {k: round(float(v), 4) for k, v in scores.items()},
            'weights': weights, 'confidence': round(float(np.clip(value, 0.0, 1.0)), 4),
            'notes': notes}
