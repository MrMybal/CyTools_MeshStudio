---
id: operation-mesh-edit
title: mesh_edit
description: Apply a chain of geometric edits to a mesh and write the result: transforms, decimation, cleaning, hole filling, components and material stripping. Every step is deterministic and the input file is never modified.
section: Reference
order: 200
parent: operations
revision: cc326b7fcf45d08a
---

Apply a chain of geometric edits to a mesh and write the result: transforms, decimation, cleaning, hole filling, components and material stripping. Every step is deterministic and the input file is never modified.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | Mesh to edit (GLB, glTF, OBJ, PLY, STL, OFF).  |
| `steps` | `array` | Yes | Edits applied in order.  |
| `output_format` | `string` | No | Format of the written mesh. `default="glb"`, `enum=["glb", "gltf", "obj", "ply", "stl"]` |
| `keep_materials` | `boolean` | No | Carry materials and textures over to the result when the format allows it. `default=true` |
| `report` | `boolean` | No | Write a JSON report with the state before and after every step. `default=true` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | Edited mesh.  |
| `report_file` | `string` | No | Report, when requested.  |
| `preview_file` | `string` | No | Preview of the result for the 3D view.  |
| `before` | `object` | Yes | See the operation parameters.  |
| `after` | `object` | Yes | See the operation parameters.  |
| `appliedSteps` | `array` | Yes | See the operation parameters.  |
| `warnings` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `meshedit`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation mesh_edit
```
