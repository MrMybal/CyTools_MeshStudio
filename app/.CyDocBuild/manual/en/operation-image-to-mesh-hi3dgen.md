---
id: operation-image-to-mesh-hi3dgen
title: image_to_mesh_hi3dgen
description: Hi3DGen (Stable-X): the picture becomes a sharp normal map (StableNormal YOSO), and a TRELLIS v1 retrained on normal maps turns that normal map into a mesh. Geometry only, on a 256 grid, in the same frame as the LocalMesh…
section: Reference
order: 200
parent: operations
revision: 528260027de9798d
---

Hi3DGen (Stable-X): the picture becomes a sharp normal map (StableNormal YOSO), and a TRELLIS v1 retrained on normal maps turns that normal map into a mesh. Geometry only, on a 256 grid, in the same frame as the LocalMesh output: texture it with "Texture a mesh for its own topology", or regenerate its detail on the 1536 grid first with "Refine a mesh". A picture without transparency is cut out first with the shared front end.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `image` | `string` | No | Picture of the subject. With an alpha channel it is used as it is; otherwise it is cut out with BiRefNet first.  |
| `subject_set` | `string` | No | Folder produced by prepare_subject or complete_subject: its front cut-out is used. `default=""` |
| `seed` | `integer` | No | Seed (-1 draws one). `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `normal_resolution` | `integer` | No | Resolution of the normal map estimation. `default=768`, `enum=[512, 768, 1024]` |
| `ss_steps` | `integer` | No | Sampling steps of the sparse structure. `default=50`, `minimum=10`, `maximum=100` |
| `ss_guidance` | `number` | No | Guidance of the sparse structure. `default=3.0`, `minimum=0.0`, `maximum=10.0` |
| `slat_steps` | `integer` | No | Sampling steps of the structured latent. `default=6`, `minimum=2`, `maximum=50` |
| `slat_guidance` | `number` | No | Guidance of the structured latent. `default=3.0`, `minimum=0.0`, `maximum=10.0` |
| `origin_at_base` | `boolean` | No | Put the base of the object on the ground plane. `default=true` |
| `gpu` | `integer` | No | GPU index. `default=0`, `minimum=0`, `maximum=7` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | Yes | The mesh (GLB, geometry only).  |
| `normal_file` | `string` | Yes | The normal map the geometry was generated from.  |
| `prepared_file` | `string` | No | The cut-out, cropped and padded as the model saw it.  |
| `subject_set` | `string` | No | The subject set used, when one was prepared.  |
| `report` | `string` | No | hi3dgen-report.json.  |
| `seed` | `integer` | No | See the operation parameters.  |
| `faces` | `integer` | No | See the operation parameters.  |
| `vertices` | `integer` | No | See the operation parameters.  |
| `peak_vram_gb` | `number` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `notes` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `hi3dgen`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation image_to_mesh_hi3dgen
```
