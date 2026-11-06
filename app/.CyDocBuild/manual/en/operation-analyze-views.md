---
id: operation-analyze-views
title: analyze_views
description: Pre-flight for a reconstruction: segmentation, view poses, same-object check, coverage map and the list of viewpoints that are missing.
section: Reference
order: 200
parent: operations
revision: 0c17276b0806c9c6
---

Pre-flight for a reconstruction: segmentation, view poses, same-object check, coverage map and the list of viewpoints that are missing.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `images` | `array` | Yes | One to twelve real pictures of the SAME object. Real pictures always win over synthetic data.  |
| `generated_views` | `array` | No | Optional synthetic views with their requested poses. They only vote with a reduced weight and can never carve away what a real picture shows. `default=[]` |
| `segmentation_model` | `string` | No | SAM 2.1 checkpoint for the object mask. auto = preferred installed model, else classical segmentation (alpha / plain background / GrabCut). none = classical only. `default="auto"`, `enum=["auto", "none", "sam2.1-hiera-tiny", "sam2.1-hiera-small", "sam2.1-hiera-base-plus", "sam2.1-hiera-large"]` |
| `depth_model` | `string` | No | Depth Anything V2 checkpoint (relative depth, low-confidence cue). Base and Large are CC-BY-NC-4.0 and require a personal licence acceptance. `default="auto"`, `enum=["auto", "none", "depth-anything-v2-small", "depth-anything-v2-base", "depth-anything-v2-large"]` |
| `camera_model` | `string` | No | Perspective Fields (Paramnet-360Cities-edina-centered): roll, pitch (elevation = -pitch) and field of view of each real picture. Applied only to values the user did not give and only when the picture shows a scene; on a cut-out object the cue is reported but not used. Adobe Research License, non-commercial: personal acceptance required. `default="auto"`, `enum=["auto", "none", "perspective-fields-paramnet-360cities"]` |
| `device` | `string` | No | Device of the AI understanding stage. auto = CUDA when PyTorch sees it, else CPU. The fitting engine always runs on the CPU. `default="auto"`, `enum=["auto", "cuda", "cpu"]` |
| `view_synthesis` | `string` | No | Missing-view generation with Zero123++ v1.2 (six views at known poses from one real picture, CUDA only). auto = only when the Real Coverage Score is below synthesis_coverage_threshold and the model is installed; always = generate or fail; off = never. Generated views vote with generated_view_weight and never override a real picture. `default="auto"`, `enum=["off", "auto", "always"]` |
| `view_synthesis_model` | `string` | No | Missing-view generator. auto = first installed of Zero123++ v1.2 (6 views, absolute elevations +20/-10, FOV 30), Wonder3D v1.0 (6 orthographic views in the frame of the input picture, colour + normals) and SyncDreamer (16 views at a fixed elevation of 30 degrees). Wonder3D and SyncDreamer run in their own environment and pinned source checkout (Installation tab). All need a CUDA GPU. `default="auto"`, `enum=["auto", "zero123plus-v1.2", "wonder3d-v1.0", "syncdreamer"]` |
| `synthesis_source` | `integer` | No | Index in `images` of the picture given to Zero123++. -1 = first picture that is not a top/bottom view. `default=-1`, `minimum=-1`, `maximum=11` |
| `synthesis_steps` | `integer` | No | Diffusion steps of the generator. Omitted = its own default (Zero123++ 36, Wonder3D 50, SyncDreamer 50). `minimum=5`, `maximum=200` |
| `synthesis_seed` | `integer` | No | Zero123++ random seed. The same seed, weights and runtime give the same views; bit-exact reproduction across GPUs is not promised. `default=0`, `minimum=0`, `maximum=2147483647` |
| `synthesis_guidance` | `number` | No | Classifier-free guidance scale. Omitted = the generator default (Zero123++ 4.0, Wonder3D 3.0, SyncDreamer 2.0). `minimum=1`, `maximum=10` |
| `synthesis_coverage_threshold` | `number` | No | view_synthesis = auto generates views when the Real Coverage Score is below this value. `default=0.6`, `minimum=0`, `maximum=1` |
| `symmetry` | `string` | No | Mirror plane normal. Auto measures bilateral symmetry (normal = Z, left/right) from several views, or assumes it for a single picture. Force X = front/back, Force Y = top/bottom, Force Z = left/right. `default="Auto"`, `enum=["Off", "Auto", "Force X", "Force Y", "Force Z"]` |
| `use_depth` | `boolean` | No | Use the depth maps for pose estimation and concavity carving. `default=true` |
| `register_views` | `boolean` | No | Classical registration of real views (OpenCV SIFT + essential matrix) for pictures without a pose. `default=true` |
| `refine_poses` | `boolean` | No | Refine unposed views by silhouette coherence. `default=true` |
| `default_azimuth` | `number` | No | Azimuth assumed when nothing else is known (degrees). `default=35`, `minimum=-360`, `maximum=360` |
| `default_elevation` | `number` | No | Elevation assumed when nothing else is known (degrees). `default=12`, `minimum=-90`, `maximum=90` |
| `default_fov` | `number` | No | Field of view assumed for pictures without one (degrees, 0 = orthographic). `default=35`, `minimum=0`, `maximum=120` |
| `real_view_weight` | `number` | No | Weight of real pictures. `default=1.0`, `minimum=0.1`, `maximum=1` |
| `generated_view_weight` | `number` | No | Weight of synthetic views (recommended 0.3 to 0.6). `default=0.45`, `minimum=0.05`, `maximum=0.9` |
| `mirrored_view_weight` | `number` | No | Weight of mirrored real views, multiplied by the symmetry confidence. `default=0.8`, `minimum=0.05`, `maximum=1` |
| `single_view_symmetry_confidence` | `number` | No | Confidence of the assumed symmetry when it cannot be measured. `default=0.5`, `minimum=0`, `maximum=1` |
| `symmetry_threshold` | `number` | No | Auto symmetry: minimal ratio of silhouette coherence with/without mirrored views. `default=0.93`, `minimum=0.5`, `maximum=1` |
| `depth_margin` | `number` | No | Depth carving safety margin, fraction of the object size. `default=0.12`, `minimum=0.02`, `maximum=0.5` |
| `complexity` | `string` | No | Budget preset. UltraSimple: 2-4 sections, about 20-100 triangles. Simple: 4-8 sections, 100-500. Medium: 8-16 sections, 500-2000. Targets, not hard limits. `default="Simple"`, `enum=["UltraSimple", "Simple", "Medium"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `report_file` | `string` | Yes | JSON report: views, poses, coverage, scores, primitives, optimisation trace, texture sources.  |
| `preview_file` | `string` | Yes | PNG contact sheet: mask (green), support volume (yellow), proxy outline (red) for every view.  |
| `real_view_count` | `integer` | No | See the operation parameters.  |
| `generated_view_count` | `integer` | No | See the operation parameters.  |
| `real_coverage_score` | `number` | Yes | Real Coverage Score, 0..1 over the view sphere.  |
| `expected_reconstruction_confidence` | `number` | Yes | 0..1; capped at 0.5 for a single picture.  |
| `symmetry_axis` | `string` | No | See the operation parameters.  |
| `is_hypothesis` | `boolean` | No | True when only one real picture was available.  |
| `missing_views` | `array` | No | See the operation parameters.  |
| `understanding` | `object` | No | Models and device actually used, measured peak VRAM.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `proxyfit`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation analyze_views
```
