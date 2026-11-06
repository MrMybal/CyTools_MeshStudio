---
id: operation-photos-to-mesh
title: photos_to_mesh
description: LocalMesh: one image, or four photographs of the same subject, to a textured GLB. The TRELLIS.2 model generates the shape; the mesh is then cleaned, remeshed and decimated, and its PBR texture is generated for that final mesh,…
section: Reference
order: 200
parent: operations
revision: e34c947941ef3fd0
---

LocalMesh: one image, or four photographs of the same subject, to a textured GLB. The TRELLIS.2 model generates the shape; the mesh is then cleaned, remeshed and decimated, and its PBR texture is generated for that final mesh, with a baked normal map. Local CUDA inference.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `mode` | `string` | No | See the operation parameters. `default="single"`, `enum=["single", "four"]` |
| `front` | `string` | No | Image path: absolute local path or relative to data/inputs. Automatically copied into the private job workspace; no manual import required. PNG/JPEG/WebP, at most 32 MiB and 40 megapixels. Optional when subject_set is given. `default=""` |
| `right` | `string` | No | Image path: absolute local path or relative to data/inputs. Automatically copied into the private job workspace; no manual import required. PNG/JPEG/WebP, at most 32 MiB and 40 megapixels. `default=""` |
| `left` | `string` | No | Image path: absolute local path or relative to data/inputs. Automatically copied into the private job workspace; no manual import required. PNG/JPEG/WebP, at most 32 MiB and 40 megapixels. `default=""` |
| `back` | `string` | No | Image path: absolute local path or relative to data/inputs. Automatically copied into the private job workspace; no manual import required. PNG/JPEG/WebP, at most 32 MiB and 40 megapixels. `default=""` |
| `tier` | `string` | No | draft: 512 grid, 80 000 faces, 2K atlas, to judge the shape. standard: 1024 grid, 150 000 faces, 4K atlas. high: 1024 grid, 16 passes, 250 000 faces, 4K atlas. max: 1536 grid, 400 000 faces, 8K atlas; needs a 24 GB card, and with four photos it uses the older view mixer because the four-view models stop at 1024. `default="standard"`, `enum=["draft", "standard", "high", "max"]` |
| `seed` | `integer` | No | See the operation parameters. `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `gpu` | `integer` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=15` |
| `sampler` | `string` | No | See the operation parameters. `default="recipe"`, `enum=["recipe", "euler", "heun", "rk4", "rk5"]` |
| `transparency` | `string` | No | See the operation parameters. `default="auto"`, `enum=["auto", "opaque", "mask", "blend"]` |
| `up_axis` | `string` | No | See the operation parameters. `default="y"`, `enum=["y", "z"]` |
| `texture_size` | `integer` | No | See the operation parameters. `default=0`, `enum=[0, 1024, 2048, 4096]` |
| `target_faces` | `integer` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=400000` |
| `real_size_mm` | `number` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=100000` |
| `fidelity` | `number` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=20` |
| `tex_guidance` | `number` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=20` |
| `steps_structure` | `integer` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=100` |
| `steps_shape` | `integer` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=100` |
| `steps_texture` | `integer` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=100` |
| `bake_normal_map` | `boolean` | No | See the operation parameters. `default=true` |
| `origin_at_base` | `boolean` | No | See the operation parameters. `default=true` |
| `remove_floaters` | `boolean` | No | See the operation parameters. `default=true` |
| `fill_holes` | `boolean` | No | See the operation parameters. `default=true` |
| `keep_input_copies` | `boolean` | No | By default private input copies are deleted after the worker stops, including failure/cancellation. Enable only to retain them for debugging. Original files and generated outputs are never deleted. `default=false` |
| `subject_set` | `string` | No | Folder produced by prepare_subject. Its cut-outs are used as the views, so the subject is segmented once for the whole workflow instead of once per backend. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | Yes | See the operation parameters.  |
| `mimeType` | `string` | Yes | See the operation parameters.  |
| `report` | `string` | Yes | See the operation parameters.  |
| `thumbnail` | `string` | Yes | See the operation parameters.  |
| `seed` | `integer` | Yes | See the operation parameters.  |
| `faces` | `integer` | Yes | See the operation parameters.  |
| `vertices` | `integer` | Yes | See the operation parameters.  |
| `seconds` | `number` | Yes | See the operation parameters.  |
| `peak_vram_gb` | `number` | Yes | See the operation parameters.  |
| `notes` | `array` | Yes | See the operation parameters.  |
| `grid_resolution` | `integer` | No | Grid the shape was really sampled on. The 1536 cascade lowers it by steps of 128 when the object has more tokens than the card allows.  |
| `token_cap` | `integer` | No | Token ceiling applied, taken on the memory available at the start of the job.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `trellis`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation photos_to_mesh
```
