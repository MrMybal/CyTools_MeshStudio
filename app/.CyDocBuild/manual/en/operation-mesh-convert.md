---
id: operation-mesh-convert
title: mesh_convert
description: Convert a mesh between the supported formats, optionally triangulating it and embedding or extracting its textures.
section: Reference
order: 200
parent: operations
revision: f956b2b416a7b557
---

Convert a mesh between the supported formats, optionally triangulating it and embedding or extracting its textures.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | Mesh to convert.  |
| `output_format` | `string` | No | Target format. `default="glb"`, `enum=["glb", "gltf", "obj", "ply", "stl", "off"]` |
| `triangulate` | `boolean` | No | Triangulate faces during the conversion. `default=false` |
| `embed_textures` | `boolean` | No | Embed the textures in the file when the format allows it. `default=true` |
| `scale` | `number` | No | Uniform scale applied during the conversion. `default=1.0`, `minimum=1e-06` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | Converted mesh.  |
| `textures` | `array` | No | Textures written next to the mesh.  |
| `vertices` | `integer` | No | See the operation parameters.  |
| `faces` | `integer` | No | See the operation parameters.  |
| `warnings` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `meshedit`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation mesh_convert
```
