#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""One-shot Wonder3D multi-view runner (single image -> 6 colour views + 6 normal maps).

Contract
--------
stdin : ONE JSON object
    {"parameters": {"image": <abs path RGB/RGBA>, "mask": <optional abs path, white = object>,
                    "output": <abs output dir>, "engine": <abs path of the Wonder3D clone>,
                    "model": <abs path of the weights folder>, "steps": 50, "seed": 42,
                    "guidance": 3.0, "device": "cuda", "cropSize": 192, "xformers": true}}
    ("cropSize" and "xformers" are optional extras; unknown keys such as "elevation" are ignored.)
    or {"parameters": {"task": "diagnose"}}
stdout: EXACTLY ONE JSON object (result, diagnose report or {"error": {...}}).
stderr: every diagnostic, library warning and progress bar.
<output>/progress.json : {"percent": 0-100, "step": "text"} rewritten atomically during the run.

Exit code: 0 on success, 1 when an {"error": ...} object is printed.

The upstream source tree is NOT modified. Everything that had to be adapted is done here at
import time (see `_harden_torch_load`, the offline switches and the working-directory change that
upstream's relative `./mvdiffusion/data/fixed_poses/nine_views` path needs).

Camera convention reported in "generated" (upstream source + measured on a real run, the
evidence is recorded in wonder3d.cameras.json):
    * the six views lie in the ZERO-elevation plane of the INPUT view camera frame (the camera
      turns around the vertical axis of the input PICTURE, not around the world vertical), and
      they are orthographic ("fov": 0) - the input picture is assumed orthographic as well;
    * "generatorAzimuth" is the upstream angle: front 0, front_right +45, right +90, back 180,
      left -90, front_left -45.  Positive = the camera moves towards the right edge of the input
      picture (+X of the input camera, counter-clockwise seen from above), i.e. towards the LEFT
      side of an object facing the camera.  The Tool convention ("+" = the camera moves towards
      the object's RIGHT side) is therefore  toolAzimuth = -generatorAzimuth  (sign -1.0);
    * normal maps are expressed in the input-view camera frame for every view:
      R = +X (picture right), G = +Y (picture up), B = +Z (towards the input camera).
"""
from __future__ import annotations

import json
import os
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _protocol import isolate_native_output, serve  # noqa: E402
from _legacy import legacy_handler  # noqa: E402

isolate_native_output()
import time
import traceback

MODEL_ID = "wonder3d-v1.0"

# Order produced by the pipeline (upstream gradio_app_mv.py / single_image_dataset.py).
# azimuth: degrees published by upstream (README: 0, 45, 90, 180, -90, -45); positive means
# the camera centre moves along +X of the input camera (towards the right edge of the input picture).
VIEW_TABLE = [
    ("front", 0.0),
    ("front_right", 45.0),
    ("right", 90.0),
    ("back", 180.0),
    ("left", -90.0),
    ("front_left", -45.0),
]

# "generatorAzimuth" is the upstream (native) angle.  The Tool maps it with its own `sign` (-1.0,
# checked on aircraft_front_right.png, see wonder3d.cameras.json).
TOOL_AZIMUTH_SIGN = -1.0
AZIMUTH_CONVENTION = ("generatorAzimuth = upstream azimuth in the input-view frame; + = camera towards the right edge "
                      "of the input picture = towards the object's LEFT side; Tool azimuth = -generatorAzimuth")


class RunnerError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _log(*args) -> None:
    print("[wonder3d]", *args, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------------
# stdout protection: libraries (tqdm, diffusers, upstream print calls) must never reach stdout.
# --------------------------------------------------------------------------------------------
_REAL_STDOUT_FD = None


def _protect_stdout() -> None:
    global _REAL_STDOUT_FD
    sys.stdout.flush()
    _REAL_STDOUT_FD = os.dup(1)
    os.dup2(2, 1)  # fd 1 now points to stderr for every C / Python writer
    sys.stdout = sys.stderr


def _emit(obj: dict) -> None:
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    fd = _REAL_STDOUT_FD if _REAL_STDOUT_FD is not None else 1
    try:
        sys.stderr.flush()
    except Exception:
        pass
    os.write(fd, data)


class Progress:
    def __init__(self, output_dir: str | None):
        self.path = os.path.join(output_dir, "progress.json") if output_dir else None

    def __call__(self, percent: float, step: str) -> None:
        if not self.path:
            return
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"percent": max(0, min(100, int(round(percent)))), "step": step}, fh)
            os.replace(tmp, self.path)
        except Exception as exc:  # best effort only
            _log("progress write failed:", exc)


# --------------------------------------------------------------------------------------------
# diagnose
# --------------------------------------------------------------------------------------------
def _version(module_name: str):
    try:
        module = __import__(module_name)
        return getattr(module, "__version__", "unknown")
    except Exception as exc:
        return "unavailable: %s: %s" % (type(exc).__name__, exc)


def diagnose() -> dict:
    report = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": sys.platform,
        "torch": _version("torch"),
        "torchvision": _version("torchvision"),
        "diffusers": _version("diffusers"),
        "transformers": _version("transformers"),
        "xformers": _version("xformers"),
        "huggingface_hub": _version("huggingface_hub"),
        "numpy": _version("numpy"),
        "cudaAvailable": False,
        "cudaVersion": None,
        "devices": [],
    }
    try:
        import torch

        report["cudaAvailable"] = bool(torch.cuda.is_available())
        report["cudaVersion"] = torch.version.cuda
        if report["cudaAvailable"]:
            for index in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(index)
                report["devices"].append(
                    {"index": index, "name": props.name, "totalMemoryBytes": int(props.total_memory),
                     "capability": "%d.%d" % (props.major, props.minor)}
                )
    except Exception as exc:
        report["torchError"] = "%s: %s" % (type(exc).__name__, exc)
    return {"diagnose": report}


# --------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------
def _harden_torch_load(torch) -> None:
    """The official weights are pickle '.bin' files.  diffusers 0.19.3 / transformers 4.35.2 call
    torch.load() without weights_only, which would execute arbitrary pickled code.  Force
    weights_only=True unless a caller explicitly chose a value."""
    original = torch.load

    def safe_load(*args, **kwargs):
        kwargs.setdefault("weights_only", True)
        return original(*args, **kwargs)

    safe_load.__wrapped__ = original
    torch.load = safe_load


def _enable_attention(pipeline, torch, use_xformers: bool) -> str:
    """Upstream only works with its XFormers*AttnProcessor classes: at the pinned revision the plain
    MVAttnProcessor raises "unexpected keyword argument 'sparse_mv_attention'".  When xformers cannot
    be used, the same upstream processors are kept and the single function they call
    (xformers.ops.memory_efficient_attention) is served by torch scaled_dot_product_attention."""
    if use_xformers:
        try:
            import xformers.ops  # noqa: F401

            pipeline.unet.enable_xformers_memory_efficient_attention()
            return "xformers"
        except Exception as exc:
            _log("xformers attention unavailable, falling back to torch SDPA:", exc)

    import types

    import mvdiffusion.models.transformer_mv2d as transformer_mv2d

    def memory_efficient_attention(query, key, value, attn_bias=None, **_ignored):
        return torch.nn.functional.scaled_dot_product_attention(query, key, value, attn_mask=attn_bias)

    transformer_mv2d.xformers = types.SimpleNamespace(
        ops=types.SimpleNamespace(memory_efficient_attention=memory_efficient_attention))
    custom = (transformer_mv2d.CustomAttention, transformer_mv2d.CustomJointAttention)
    for module in pipeline.unet.modules():
        if isinstance(module, custom):
            module.set_use_memory_efficient_attention_xformers(True)
    return "torch-sdpa"


def _build_rgba(image_path: str, mask_path: str | None):
    """Return (RGBA PIL image, mask source string).  Alpha = object."""
    import numpy as np
    from PIL import Image

    image = Image.open(image_path)
    image.load()
    source = None
    alpha = None
    if mask_path:
        mask = Image.open(mask_path).convert("L")
        if mask.size != image.size:
            mask = mask.resize(image.size, Image.BILINEAR)
        alpha = np.asarray(mask).copy()
        source = "mask"
    elif image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        candidate = np.asarray(rgba)[:, :, 3]
        if candidate.min() < 250:  # a real alpha channel, not an all-opaque one
            alpha = candidate.copy()
            source = "alpha"
    rgb = np.asarray(image.convert("RGB")).copy()
    if alpha is None:
        alpha = _alpha_from_uniform_background(rgb)
        source = "border-background"
    coverage = float((alpha > 127).mean())
    if coverage < 0.002 or coverage > 0.97:
        raise RunnerError(
            "GenerationFailed",
            "Cannot isolate the object (mask source '%s' covers %.1f%% of the picture). "
            "Provide a 'mask' picture (white = object)." % (source, coverage * 100.0),
        )
    rgba = np.dstack([rgb, alpha]).astype("uint8")
    return Image.fromarray(rgba, "RGBA"), source, coverage


def _alpha_from_uniform_background(rgb):
    """Fallback used when neither an alpha channel nor a mask is supplied: the background is the
    set of pixels connected to the picture border whose colour is close to the border colour.
    (Upstream uses rembg + SAM here; they are deliberately not part of this environment.)"""
    import cv2
    import numpy as np

    h, w = rgb.shape[:2]
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]], axis=0).astype(np.int16)
    reference = np.median(border, axis=0)
    spread = float(np.abs(border - reference).max(axis=1).mean())
    tolerance = max(14.0, 3.0 * spread)
    distance = np.abs(rgb.astype(np.int16) - reference).max(axis=2)
    candidate = (distance <= tolerance).astype(np.uint8)
    _count, labels = cv2.connectedComponents(candidate, connectivity=4)
    edge_labels = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, edge_labels) & (candidate == 1)  # label 0 = non-candidate pixels
    alpha = np.where(background, 0, 255).astype(np.uint8)
    # drop isolated specks (noise, JPEG blocks) without eroding thin parts of the object
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(alpha, connectivity=8)
    minimum = max(16, int(0.0002 * h * w))
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] < minimum:
            alpha[labels == label] = 0
    _log("background estimated from the border: colour=%s tolerance=%.1f" % (reference.tolist(), tolerance))
    return alpha


def _expand_to_square(rgba):
    """Same as upstream gradio_app_mv.expand2square(img, (127, 127, 127, 0))."""
    from PIL import Image

    width, height = rgba.size
    if width == height:
        return rgba
    side = max(width, height)
    result = Image.new("RGBA", (side, side), (127, 127, 127, 0))
    result.paste(rgba, ((side - width) // 2, (side - height) // 2))
    return result


def _save_tensor_png(tensor, path: str) -> None:
    """Same conversion as upstream save_image_to_disk()."""
    import torch
    from PIL import Image

    array = tensor.detach().float().mul(255).add_(0.5).clamp_(0, 255).permute(1, 2, 0).to("cpu", torch.uint8).numpy()
    Image.fromarray(array).save(path)


# --------------------------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------------------------
def generate(parameters: dict) -> dict:
    for key in ("image", "output", "engine", "model"):
        if not parameters.get(key):
            raise RunnerError("GenerationFailed", "Missing parameter '%s'." % key)
    image_path = os.path.abspath(parameters["image"])
    mask_path = os.path.abspath(parameters["mask"]) if parameters.get("mask") else None
    output_dir = os.path.abspath(parameters["output"])
    engine_dir = os.path.abspath(parameters["engine"])
    model_dir = os.path.abspath(parameters["model"])
    steps = int(parameters.get("steps", 50) or 50)
    seed = int(parameters.get("seed", 42) if parameters.get("seed") is not None else 42)
    guidance = float(parameters.get("guidance", 3.0) if parameters.get("guidance") is not None else 3.0)
    crop_size = int(parameters.get("cropSize", 192) or 192)
    device_name = str(parameters.get("device", "cuda") or "cuda")

    if not os.path.isfile(image_path):
        raise RunnerError("GenerationFailed", "Input picture not found: %s" % image_path)
    if mask_path and not os.path.isfile(mask_path):
        raise RunnerError("GenerationFailed", "Mask picture not found: %s" % mask_path)
    if not os.path.isfile(os.path.join(engine_dir, "mvdiffusion", "pipelines", "pipeline_mvdiffusion_image.py")):
        raise RunnerError("MissingDependency", "Wonder3D source not found in: %s" % engine_dir)
    if not os.path.isfile(os.path.join(model_dir, "model_index.json")):
        raise RunnerError("MissingDependency", "Wonder3D weights not found in: %s" % model_dir)
    if not 1 <= steps <= 1000:
        raise RunnerError("GenerationFailed", "'steps' must be between 1 and 1000.")
    if not 16 <= crop_size <= 256:
        raise RunnerError("GenerationFailed", "'cropSize' must be between 16 and 256.")

    os.makedirs(output_dir, exist_ok=True)
    progress = Progress(output_dir)
    progress(0, "starting")

    # Never reach the network: everything is local.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DISABLE_TELEMETRY"] = "1"

    try:
        import numpy  # noqa: F401
        import torch
    except Exception as exc:
        raise RunnerError("MissingDependency", "torch is not importable: %s: %s" % (type(exc).__name__, exc))

    if device_name.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RunnerError("DeviceUnavailable", "CUDA was requested but torch.cuda.is_available() is False.")
        try:
            device = torch.device(device_name if ":" in device_name else "cuda:0")
        except Exception as exc:
            raise RunnerError("DeviceUnavailable", "Invalid device '%s': %s" % (device_name, exc))
        if device.index is not None and device.index >= torch.cuda.device_count():
            raise RunnerError("DeviceUnavailable", "CUDA device %d does not exist (%d device(s) visible)."
                              % (device.index, torch.cuda.device_count()))
        dtype = torch.float16
    elif device_name == "cpu":
        device = torch.device("cpu")
        dtype = torch.float32
    else:
        raise RunnerError("DeviceUnavailable", "Unsupported device '%s'." % device_name)

    _harden_torch_load(torch)

    progress(2, "preparing the conditioning picture")
    rgba, mask_source, coverage = _build_rgba(image_path, mask_path)
    rgba.thumbnail([1024, 1024])  # upstream preprocess(): RES = 1024
    rgba = _expand_to_square(rgba)

    # Upstream modules.  single_image_dataset.py reads "./mvdiffusion/data/fixed_poses/nine_views"
    # relative to the working directory, hence the chdir (every path above is already absolute).
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    os.chdir(engine_dir)
    try:
        from einops import rearrange
        from mvdiffusion.data.single_image_dataset import SingleImageDataset
        from mvdiffusion.pipelines.pipeline_mvdiffusion_image import MVDiffusionImagePipeline
    except ImportError as exc:
        raise RunnerError("MissingDependency", "%s: %s" % (type(exc).__name__, exc))

    dataset = SingleImageDataset(root_dir="", num_views=6, img_wh=[256, 256], bg_color="white",
                                 crop_size=crop_size, single_image=rgba)
    batch = dataset[0]
    conditioning_path = os.path.join(output_dir, "conditioning.png")
    _save_tensor_png(batch["imgs_in"][0], conditioning_path)

    progress(5, "loading the model")
    load_start = time.time()
    pipeline = MVDiffusionImagePipeline.from_pretrained(model_dir, torch_dtype=dtype, local_files_only=True)
    attention = _enable_attention(pipeline, torch, use_xformers=bool(parameters.get("xformers", True)) and device.type == "cuda")
    pipeline.to(device)
    pipeline.set_progress_bar_config(disable=True)
    torch.set_grad_enabled(False)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)
    load_seconds = time.time() - load_start
    _log("model loaded in %.1fs (attention=%s)" % (load_seconds, attention))
    progress(30, "model loaded")

    # Same batch layout as upstream run_pipeline(): normal domain first, colour domain second.
    imgs_in = torch.cat([batch["imgs_in"]] * 2, dim=0).to(dtype)
    imgs_in = rearrange(imgs_in, "Nv C H W -> (Nv) C H W")
    generator = torch.Generator(device=device).manual_seed(seed)

    def on_step(index, _timestep, _latents):
        progress(30 + 65.0 * (index + 1) / steps, "diffusion step %d/%d" % (index + 1, steps))

    generation_start = time.time()
    out = pipeline(
        imgs_in,
        generator=generator,
        guidance_scale=guidance,
        num_inference_steps=steps,
        output_type="pt",
        num_images_per_prompt=1,
        callback=on_step,
        callback_steps=1,
        eta=1.0,  # configs/mvdiffusion-joint-ortho-6views.yaml: pipe_validation_kwargs.eta
    ).images
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    generation_seconds = time.time() - generation_start

    count = out.shape[0] // 2
    if count != len(VIEW_TABLE):
        raise RunnerError("GenerationFailed", "The pipeline returned %d pictures, expected 12." % out.shape[0])
    normals = out[:count]
    colours = out[count:]

    progress(96, "writing the pictures")
    generated = []
    for index, (view_name, upstream_azimuth) in enumerate(VIEW_TABLE):
        colour_path = os.path.join(output_dir, "rgb_000_%s.png" % view_name)
        normal_path = os.path.join(output_dir, "normals_000_%s.png" % view_name)
        _save_tensor_png(colours[index], colour_path)
        _save_tensor_png(normals[index], normal_path)
        generated.append({
            "image": colour_path,
            "normal": normal_path,
            "generatorAzimuth": upstream_azimuth,
            "elevation": 0.0,
            "fov": 0.0,
            "viewName": view_name,
            "toolAzimuth": 180.0 if upstream_azimuth == 180.0 else TOOL_AZIMUTH_SIGN * upstream_azimuth + 0.0,
            "projection": "orthographic",
            "width": int(colours[index].shape[-1]),
            "height": int(colours[index].shape[-2]),
        })

    peak = int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else 0
    result = {
        "generated": generated,
        "stats": {
            "model": MODEL_ID,
            "device": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
            "steps": steps,
            "seed": seed,
            "guidance": guidance,
            "cropSize": crop_size,
            "loadSeconds": round(load_seconds, 3),
            "generationSeconds": round(generation_seconds, 3),
            "peakVramBytes": peak,
            "attention": attention,
            "dtype": str(dtype).replace("torch.", ""),
            "maskSource": mask_source,
            "maskCoverage": round(coverage, 5),
            "conditioningImage": conditioning_path,
            "azimuthConvention": AZIMUTH_CONVENTION,
            "normalFrame": "input-view camera for every view (upstream normal_system='front'): R=+X right, G=+Y up, B=+Z towards the input camera",
            "background": "white",
        },
    }
    progress(100, "done")
    return result


def _execute(parameters):
    """The upstream runner, reached through one entry point like the other ported workers."""
    if parameters.get('task') == 'diagnose':
        return diagnose()
    return generate(parameters)


if __name__ == '__main__':
    handler = legacy_handler(_execute)
    raise SystemExit(serve({'generate_views': handler, 'diagnose': handler}))
