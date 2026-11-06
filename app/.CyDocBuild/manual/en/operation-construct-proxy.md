---
id: operation-construct-proxy
title: construct_proxy
description: Build a simple, clean, mostly hard-surface proxy mesh (lofted cross-sections, extruded polygons, boxes, cylinders) from one or several pictures of the same object, and project the pictures on it. AI models only supply masks,…
section: Reference
order: 200
parent: operations
revision: 552320758c7e504e
---

Build a simple, clean, mostly hard-surface proxy mesh (lofted cross-sections, extruded polygons, boxes, cylinders) from one or several pictures of the same object, and project the pictures on it. AI models only supply masks, relative depth, camera poses and optional synthetic views.

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
| `main_axis` | `string` | No | Axis of the main loft. X = front/back, Y = up, Z = left/right. `default="Auto"`, `enum=["Auto", "X", "Y", "Z"]` |
| `max_sections` | `integer` | No | Override: maximum cross-sections of the main loft. `minimum=2`, `maximum=32` |
| `section_vertices` | `integer` | No | Override: vertices per rounded cross-section (box sections always use 4). `enum=[4, 6, 8, 12, 16]` |
| `max_primitives` | `integer` | No | Override: maximum fitted components besides the main body (a mirrored pair counts once). `minimum=0`, `maximum=40` |
| `max_polygon_vertices` | `integer` | No | Override: maximum outline vertices of an extruded polygon. `minimum=3`, `maximum=12` |
| `grid_resolution` | `integer` | No | Override: support volume resolution per axis (RAM grows with the cube). `minimum=48`, `maximum=192` |
| `min_part_volume` | `number` | No | Override: smallest component kept, as a fraction of the support volume. `minimum=0.0005`, `maximum=0.2` |
| `unobserved_extent_ratio` | `number` | No | When no picture limits the object along an axis (single front view, two opposite views), its extent on that axis is assumed to be this ratio times the largest observed dimension. The report lists every assumed axis. `default=1.0`, `minimum=0.1`, `maximum=4` |
| `body_window` | `number` | No | Appendages shorter than this fraction of the main axis are separated from the body. `default=0.35`, `minimum=0.1`, `maximum=0.8` |
| `min_gain` | `number` | No | Progressive optimisation: a section or component is kept only if FitScore improves by more than this. `default=0.004`, `minimum=0`, `maximum=0.2` |
| `split_below` | `number` | No | A component fitted below this volumetric IoU is split (plate peeling) and refitted. `default=0.5`, `minimum=0`, `maximum=1` |
| `snap_angle` | `number` | No | Hard-surface snapping: directions and outline edges closer than this to an axis become exactly parallel/perpendicular (degrees). 0 disables. `default=8`, `minimum=0`, `maximum=30` |
| `thin_as_planes` | `boolean` | No | Represent one-voxel-thin surfaces as zero-thickness double-sided Plane primitives. `default=false` |
| `min_thickness_ratio` | `number` | No | Thinnest allowed plate, relative to its largest outline span. `default=0.04`, `minimum=0.005`, `maximum=0.5` |
| `refine_passes` | `integer` | No | Coordinate-descent passes of the final silhouette refinement. `default=2`, `minimum=0`, `maximum=6` |
| `part_triangle_penalty` | `number` | No | Per-triangle penalty when choosing the primitive type of a component. `default=0.0015`, `minimum=0`, `maximum=0.02` |
| `fit_weights` | `object` | No | FitScore weights. Defaults: silhouette 1.0, depth 0.25, edge 0.35, multiview 0.4, symmetry 0.15, complexity_primitive 0.004, complexity_triangle 0.002 (per 100 triangles).  |
| `texture_resolution` | `integer` | No | BaseColor atlas size in pixels (square). `default=1024`, `enum=[256, 512, 1024, 2048, 4096]` |
| `texture_padding` | `integer` | No | xatlas chart padding in pixels. `default=4`, `minimum=1`, `maximum=16` |
| `texture_blend` | `string` | No | best = best camera per face. blend = weighted multi-view blend of the best cameras. `default="best"`, `enum=["best", "blend"]` |
| `blend_views` | `integer` | No | Cameras mixed per face when texture_blend = blend. `default=3`, `minimum=2`, `maximum=6` |
| `visibility_resolution` | `integer` | No | Depth-buffer size of the occlusion test. `default=384`, `enum=[256, 384, 512, 768]` |
| `min_facing` | `number` | No | A camera may texture a face only when cos(angle) exceeds this. `default=0.12`, `minimum=0`, `maximum=0.9` |
| `real_view_bonus` | `number` | No | TextureViewScore factor of real pictures. `default=1.0`, `minimum=0.1`, `maximum=1` |
| `mirrored_view_bonus` | `number` | No | TextureViewScore factor of mirrored real pictures. `default=0.55`, `minimum=0`, `maximum=1` |
| `generated_view_bonus` | `number` | No | TextureViewScore factor of synthetic views. `default=0.3`, `minimum=0`, `maximum=1` |
| `target_size` | `number` | No | Largest dimension of the exported mesh, in glTF units (metres). Relative proportions only: no absolute scale is recovered from pictures. `default=1.0`, `maximum=10000` |
| `weld_tolerance` | `number` | No | Vertex welding distance of proxy_geometry.obj, relative to target_size. `default=0.0001`, `minimum=0`, `maximum=0.01` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | Merged textured proxy (binary glTF, front +Z, up +Y). Internal faces removed. Input of any mesh Tool.  |
| `parts_file` | `string` | Yes | Separated parts: one named node per primitive, same atlas.  |
| `geometry_file` | `string` | Yes | Welded geometry only (OBJ, no UV).  |
| `texture_file` | `string` | Yes | BaseColor atlas (PNG).  |
| `triangles` | `integer` | Yes | See the operation parameters.  |
| `components` | `integer` | Yes | See the operation parameters.  |
| `fit_score` | `number` | No | See the operation parameters.  |
| `silhouette_agreement` | `number` | No | Weighted silhouette IoU over all views.  |
| `report_file` | `string` | Yes | JSON report: views, poses, coverage, scores, primitives, optimisation trace, texture sources.  |
| `preview_file` | `string` | Yes | PNG contact sheet: mask (green), support volume (yellow), proxy outline (red) for every view.  |
| `real_view_count` | `integer` | No | See the operation parameters.  |
| `generated_view_count` | `integer` | No | See the operation parameters.  |
| `real_coverage_score` | `number` | No | Real Coverage Score, 0..1 over the view sphere.  |
| `expected_reconstruction_confidence` | `number` | No | 0..1; capped at 0.5 for a single picture.  |
| `symmetry_axis` | `string` | No | See the operation parameters.  |
| `is_hypothesis` | `boolean` | No | True when only one real picture was available.  |
| `missing_views` | `array` | No | See the operation parameters.  |
| `understanding` | `object` | No | Models and device actually used, measured peak VRAM.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `proxyfit`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation construct_proxy
```
