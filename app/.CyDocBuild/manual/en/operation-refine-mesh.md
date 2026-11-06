---
id: operation-refine-mesh
title: refine_mesh
description: Regenerate the geometric detail of an existing mesh, keeping its overall shape: the mesh is encoded, its occupancy becomes the structure, and TRELLIS.2 samples the shape again on it from the reference picture, up to the 1536…
section: Reference
order: 200
parent: operations
revision: 544f4a27d69b8600
---

Regenerate the geometric detail of an existing mesh, keeping its overall shape: the mesh is encoded, its occupancy becomes the structure, and TRELLIS.2 samples the shape again on it from the reference picture, up to the 1536 grid. LocalMesh's own cleaning chain then closes the holes, removes the debris and brings it to the face budget, in the frame and at the scale of the input. Geometry only: texture the result with "Texture a mesh for its own topology".

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | Mesh to refine, Y-up and facing like the LocalMesh output.  |
| `subject_set` | `string` | No | Folder produced by prepare_subject or complete_subject: the reference cut-out. `default=""` |
| `image` | `string` | No | Reference picture, when there is no subject set; it is cut out here.  |
| `resolution` | `integer` | No | Grid the shape is sampled on again. 1536 needs a 24 GB card and is lowered by steps of 128 when the shape has too many tokens. `default=1536`, `enum=[1024, 1536]` |
| `target_faces` | `integer` | No | Face budget of the result; 0 takes the recipe of that grid (250 000 on 1024, 400 000 on 1536). `default=0`, `minimum=0`, `maximum=1000000` |
| `use_all_views` | `boolean` | No | Condition on every view of the subject set, not only the front. Experimental. `default=false` |
| `steps` | `integer` | No | Sampling steps of the shape model. `default=16`, `minimum=4`, `maximum=50` |
| `guidance` | `number` | No | Shape guidance; 0 keeps the weights' own value. `default=0.0`, `minimum=0.0`, `maximum=15.0` |
| `seed` | `integer` | No | Seed (-1 draws one). `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `up_axis` | `string` | No | Up axis of the input mesh. `default="y"`, `enum=["y", "z"]` |
| `gpu` | `integer` | No | GPU index. `default=0`, `minimum=0`, `maximum=7` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | Yes | The refined mesh (GLB, geometry only).  |
| `report` | `string` | No | refine-report.json.  |
| `seed` | `integer` | No | See the operation parameters.  |
| `grid_resolution` | `integer` | Yes | See the operation parameters.  |
| `token_cap` | `integer` | No | See the operation parameters.  |
| `faces` | `integer` | No | See the operation parameters.  |
| `vertices` | `integer` | No | See the operation parameters.  |
| `peak_vram_gb` | `number` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `notes` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `trellis`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation refine_mesh
```
