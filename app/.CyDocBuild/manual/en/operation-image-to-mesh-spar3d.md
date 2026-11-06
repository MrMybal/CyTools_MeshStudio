---
id: operation-image-to-mesh-spar3d
title: image_to_mesh_spar3d
description: Reconstruct one object as a textured mesh with its point cloud. The backside is inferred by the model, not measured.
section: Reference
order: 200
parent: operations
revision: 723190db9b576e77
---

Reconstruct one object as a textured mesh with its point cloud. The backside is inferred by the model, not measured.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `image_file` | `string` | No | PNG/JPEG/WEBP inside CYTOOLS_SPAR3D_INPUT_ROOT (default: inputs). Optional when subject_set is given.  |
| `texture_resolution` | `integer` | No | See the operation parameters. `default=1024`, `enum=[512, 1024, 2048]` |
| `remesh` | `value` | No | GLB triangulates faces even after quad remeshing. `default="none"`, `enum=["none", "triangle", "quad"]` |
| `target_vertices` | `integer` | No | Approximate remeshing vertex target; -1 preserves upstream default. `default=-1`, `minimum=-1`, `maximum=100000` |
| `low_vram` | `boolean` | No | See the operation parameters. `default=false` |
| `gpu_index` | `integer` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=15` |
| `remove_background` | `boolean` | No | See the operation parameters. `default=true` |
| `foreground_ratio` | `number` | No | See the operation parameters. `default=1.3`, `minimum=1.1`, `maximum=2` |
| `seed` | `integer` | No | See the operation parameters. `default=42`, `minimum=0`, `maximum=2147483647` |
| `subject_set` | `string` | No | Folder produced by prepare_subject; its front cut-out replaces the image and switches the internal background removal off. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | See the operation parameters.  |
| `point_cloud_file` | `string` | Yes | See the operation parameters.  |
| `preprocessed_image` | `string` | Yes | See the operation parameters.  |
| `report_file` | `string` | Yes | See the operation parameters.  |
| `remesh` | `string` | Yes | See the operation parameters.  |
| `export_topology` | `string` | Yes | See the operation parameters.  |
| `model_id` | `string` | Yes | See the operation parameters.  |
| `model_revision` | `string` | Yes | See the operation parameters.  |
| `source_revision` | `string` | Yes | See the operation parameters.  |
| `vertices` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `faces` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `seed` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `gpu_index` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `peak_vram_bytes` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `load_seconds` | `number` | Yes | See the operation parameters. `minimum=0` |
| `total_seconds` | `number` | Yes | See the operation parameters. `minimum=0` |
| `warnings` | `array` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `spar3d`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation image_to_mesh_spar3d
```
