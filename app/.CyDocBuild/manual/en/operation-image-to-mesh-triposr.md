---
id: operation-image-to-mesh-triposr
title: image_to_mesh_triposr
description: Reconstruct one object from a single image in seconds: feed-forward NeRF then marching cubes, vertex colours or a baked texture atlas. Fast prototyping, not a measurement of the real object.
section: Reference
order: 200
parent: operations
revision: 8259358e5848deb3
---

Reconstruct one object from a single image in seconds: feed-forward NeRF then marching cubes, vertex colours or a baked texture atlas. Fast prototyping, not a measurement of the real object.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `image_file` | `string` | No | PNG/JPEG/WEBP inside CYTOOLS_TRIPOSR_INPUT_ROOT (default: inputs). Optional when subject_set is given.  |
| `mc_resolution` | `integer` | No | Marching cubes grid resolution. Lower is faster and coarser. `default=256`, `enum=[128, 192, 256, 320, 384]` |
| `density_threshold` | `number` | No | See the operation parameters. `default=25`, `minimum=1`, `maximum=100` |
| `chunk_size` | `integer` | No | See the operation parameters. `default=8192`, `minimum=0`, `maximum=131072` |
| `output_format` | `value` | No | GLB carries vertex colours. Baking a texture atlas requires obj. `default="glb"`, `enum=["glb", "obj"]` |
| `bake_texture` | `boolean` | No | Bake a texture atlas with xatlas and moderngl instead of vertex colours. Needs a working OpenGL context and output_format obj. `default=false` |
| `texture_resolution` | `integer` | No | See the operation parameters. `default=1024`, `enum=[512, 1024, 2048]` |
| `remove_background` | `boolean` | No | Run rembg on the input. Disable only for an image that already has a clean, centred foreground. `default=true` |
| `foreground_ratio` | `number` | No | Fraction of the frame occupied by the object after cropping. `default=0.85`, `minimum=0.5`, `maximum=1` |
| `device` | `value` | No | CPU is supported by the upstream code but is far slower; it is not a validated path here. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `gpu_index` | `integer` | No | NVIDIA device index, ignored when device is cpu. `default=0`, `minimum=0`, `maximum=15` |
| `preview_views` | `integer` | No | Number of NeRF-rendered turntable PNG previews. 0 skips rendering. `default=0`, `minimum=0`, `maximum=8` |
| `preview_size` | `integer` | No | See the operation parameters. `default=256`, `enum=[128, 256, 512]` |
| `subject_set` | `string` | No | Folder produced by prepare_subject; its front cut-out replaces the image and switches the internal background removal off. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | See the operation parameters.  |
| `texture_file` | `string` | Yes | Empty string when vertex colours are used.  |
| `preprocessed_image` | `string` | Yes | See the operation parameters.  |
| `preview_files` | `array` | Yes | See the operation parameters.  |
| `report_file` | `string` | Yes | See the operation parameters.  |
| `output_format` | `string` | Yes | See the operation parameters.  |
| `bake_texture` | `boolean` | Yes | See the operation parameters.  |
| `has_vertex_colors` | `boolean` | Yes | See the operation parameters.  |
| `vertices` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `faces` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `mc_resolution` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `density_threshold` | `number` | Yes | See the operation parameters. `minimum=0` |
| `model_id` | `string` | Yes | See the operation parameters.  |
| `model_revision` | `string` | Yes | See the operation parameters.  |
| `source_revision` | `string` | Yes | See the operation parameters.  |
| `device` | `string` | Yes | See the operation parameters.  |
| `gpu_index` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `cuda_marching_cubes` | `boolean` | Yes | See the operation parameters.  |
| `peak_vram_bytes` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `load_seconds` | `number` | Yes | See the operation parameters. `minimum=0` |
| `inference_seconds` | `number` | Yes | See the operation parameters. `minimum=0` |
| `mesh_seconds` | `number` | Yes | See the operation parameters. `minimum=0` |
| `total_seconds` | `number` | Yes | See the operation parameters. `minimum=0` |
| `warnings` | `array` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `triposr`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation image_to_mesh_triposr
```
