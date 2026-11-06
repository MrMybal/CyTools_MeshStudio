---
id: operation-texture-mesh
title: texture_mesh
description: Give a remeshed model — QuadWild quads, a retopology, any mesh aligned with the reference — a texture made for that exact topology. "generate" asks TRELLIS.2 to generate it on this mesh from the reference picture, as LocalMesh…
section: Reference
order: 200
parent: operations
revision: b9e7cbae4b7c4c89
---

Give a remeshed model — QuadWild quads, a retopology, any mesh aligned with the reference — a texture made for that exact topology. "generate" asks TRELLIS.2 to generate it on this mesh from the reference picture, as LocalMesh does on its own mesh; "transfer" re-projects the texture of the detailed model instead, with no model. The detailed model, when given, is also baked into a normal map. Quads are kept in the OBJ; the GLB is triangulated, as glTF requires.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | Mesh to texture (OBJ keeps its quads; GLB, PLY, STL are read as triangles). Y-up, facing like the LocalMesh output.  |
| `subject_set` | `string` | No | Folder produced by prepare_subject or complete_subject: the reference cut-out, and the other views for multi-view texturing. `default=""` |
| `image` | `string` | No | Reference picture, when there is no subject set; it is cut out here.  |
| `detail_mesh` | `string` | No | Detailed model aligned with this mesh (the LocalMesh output): baked into the normal map, and the source of "transfer".  |
| `texture_source` | `string` | No | generate: TRELLIS.2 generates the texture on this mesh. transfer: the texture of the detailed model is re-projected. `default="generate"`, `enum=["generate", "transfer"]` |
| `texture_size` | `integer` | No | Side of the atlas in pixels. `default=4096`, `enum=[1024, 2048, 4096, 8192]` |
| `multiview_texture` | `boolean` | No | Guide the texture with every view of the subject set, not only the front. Experimental: never measured upstream. `default=false` |
| `resolution` | `integer` | No | Texture model grid: 512 uses the 512 model, 1024 the 1024 one. `default=1024`, `enum=[512, 1024]` |
| `steps` | `integer` | No | Sampling steps of the texture model. `default=16`, `minimum=4`, `maximum=50` |
| `guidance` | `number` | No | Guidance of the texture model. `default=5.0`, `minimum=1.0`, `maximum=12.0` |
| `seed` | `integer` | No | Seed (-1 draws one). `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `up_axis` | `string` | No | Up axis of the input mesh. `default="y"`, `enum=["y", "z"]` |
| `uv_padding` | `integer` | No | Padding between UV islands, in texels. `default=4`, `minimum=1`, `maximum=32` |
| `gpu` | `integer` | No | GPU index. `default=0`, `minimum=0`, `maximum=7` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | Yes | Textured GLB (triangulated, PBR with normal map).  |
| `obj_file` | `string` | Yes | Textured OBJ that keeps the quads, with its MTL.  |
| `base_color_file` | `string` | Yes | Base colour map.  |
| `normal_file` | `string` | No | Tangent-space normal map, when a detailed model was given.  |
| `roughness_file` | `string` | No | Roughness map.  |
| `report` | `string` | No | texture-report.json.  |
| `seed` | `integer` | No | See the operation parameters.  |
| `faces` | `integer` | No | See the operation parameters.  |
| `polygons` | `integer` | No | See the operation parameters.  |
| `polygons_kept` | `integer` | No | See the operation parameters.  |
| `polygons_split` | `integer` | No | See the operation parameters.  |
| `texture_size` | `integer` | No | See the operation parameters.  |
| `texels_per_triangle` | `number` | No | See the operation parameters.  |
| `peak_vram_gb` | `number` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `notes` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `trellis`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation texture_mesh
```
