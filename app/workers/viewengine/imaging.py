"""Image loading, masks, background composition and saving. No model is loaded here."""
import math
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = 80_000_000
NEUTRAL = (128, 128, 128)


def load_rgb(path):
    """Decode an image to uint8 RGB and report its native pixel size."""
    with Image.open(path) as image:
        image.load()
        native = (image.width, image.height)
        alpha = None
        if image.mode in ('RGBA', 'LA', 'PA') or 'transparency' in image.info:
            converted = image.convert('RGBA')
            alpha = np.array(converted)[:, :, 3]
        rgb = np.array(image.convert('RGB'))
    return rgb, alpha, native


def to_gray(rgb):
    return (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.uint8)


def binary_mask(values, threshold=127):
    return (np.asarray(values) > threshold).astype(np.uint8) * 255


def bounding_box(mask):
    """Tight ``[x, y, width, height]`` of the mask, or ``None`` when it is empty."""
    rows = np.any(mask > 127, axis=1)
    columns = np.any(mask > 127, axis=0)
    if not rows.any() or not columns.any():
        return None
    top, bottom = int(np.argmax(rows)), int(len(rows) - 1 - np.argmax(rows[::-1]))
    left, right = int(np.argmax(columns)), int(len(columns) - 1 - np.argmax(columns[::-1]))
    return [left, top, right - left + 1, bottom - top + 1]


def crop_to_object(rgb, mask, margin=0.08, square=True):
    """Centre the object with a relative margin; keeps the aspect when square."""
    box = bounding_box(mask)
    if box is None:
        return rgb, mask
    x, y, width, height = box
    pad = int(round(max(width, height) * float(margin)))
    if square:
        size = max(width, height) + 2 * pad
        centre = (x + width / 2.0, y + height / 2.0)
        left, top = int(round(centre[0] - size / 2.0)), int(round(centre[1] - size / 2.0))
        right, bottom = left + size, top + size
    else:
        left, top, right, bottom = x - pad, y - pad, x + width + pad, y + height + pad
    height_image, width_image = mask.shape[:2]
    pad_left, pad_top = max(0, -left), max(0, -top)
    pad_right, pad_bottom = max(0, right - width_image), max(0, bottom - height_image)
    rgb = np.pad(rgb, ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)), mode='edge')
    mask = np.pad(mask, ((pad_top, pad_bottom), (pad_left, pad_right)), mode='constant')
    left, top = left + pad_left, top + pad_top
    return rgb[top:top + (bottom - top), left:left + (right - left)], \
        mask[top:top + (bottom - top), left:left + (right - left)]


def resize(values, size, nearest=False):
    mode = Image.NEAREST if nearest else Image.LANCZOS
    if values.ndim == 2:
        return np.array(Image.fromarray(values).resize(size, mode))
    return np.array(Image.fromarray(values).resize(size, mode))


def compose_background(rgb, mask, mode):
    """Return ``(array, mime)`` for transparent, neutral or original backgrounds."""
    if mode == 'transparent':
        rgba = np.dstack([rgb, binary_mask(mask)])
        return rgba, 'image/png'
    if mode == 'neutral':
        alpha = (np.asarray(mask, dtype=np.float32) / 255.0)[:, :, None]
        flat = np.zeros_like(rgb, dtype=np.float32)
        flat[:, :] = NEUTRAL
        return np.clip(rgb.astype(np.float32) * alpha + flat * (1.0 - alpha), 0, 255).astype(np.uint8), 'image/png'
    return rgb, 'image/png'


def save(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(values).save(path)
    return path


def thumbnail(images, columns=4, cell=192):
    """Contact sheet of RGB or RGBA arrays, used for the interface preview."""
    if not images:
        return None
    columns = max(1, min(columns, len(images)))
    rows = int(math.ceil(len(images) / columns))
    sheet = np.zeros((rows * cell, columns * cell, 3), dtype=np.uint8)
    sheet[:, :] = (24, 24, 28)
    for index, value in enumerate(images):
        value = np.asarray(value)
        if value.ndim == 3 and value.shape[2] == 4:
            alpha = value[:, :, 3:4].astype(np.float32) / 255.0
            value = (value[:, :, :3].astype(np.float32) * alpha + 32 * (1.0 - alpha)).astype(np.uint8)
        height, width = value.shape[:2]
        scale = cell / float(max(height, width))
        target = (max(1, int(width * scale)), max(1, int(height * scale)))
        small = resize(value, target)
        row, column = divmod(index, columns)
        y = row * cell + (cell - small.shape[0]) // 2
        x = column * cell + (cell - small.shape[1]) // 2
        sheet[y:y + small.shape[0], x:x + small.shape[1]] = small
    return sheet


def sharpness(gray, mask=None):
    """Variance of the Laplacian inside the mask: used to rank reference images."""
    import cv2
    values = cv2.Laplacian(gray, cv2.CV_64F)
    if mask is not None and (mask > 127).any():
        values = values[mask > 127]
    return float(np.var(values))
