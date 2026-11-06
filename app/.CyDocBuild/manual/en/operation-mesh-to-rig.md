---
id: operation-mesh-to-rig
title: mesh_to_rig
description: Predict a skeleton and skinning weights for a mesh with UniRig Articulation-XL.
section: Reference
order: 200
parent: operations
revision: 29c6ef7e93f1c07d
---

Predict a skeleton and skinning weights for a mesh with UniRig Articulation-XL.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh` | `string` | Yes | See the operation parameters.  |
| `seed` | `integer` | No | See the operation parameters. `default=12345`, `minimum=0`, `maximum=2147483647` |
| `faces_target` | `integer` | No | See the operation parameters. `default=50000`, `minimum=500`, `maximum=50000` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `rigged_mesh` | `string` | Yes | See the operation parameters.  |
| `skeleton` | `string` | Yes | See the operation parameters.  |
| `skin_weights` | `string` | Yes | See the operation parameters.  |
| `skeleton_fbx` | `string` | Yes | See the operation parameters.  |
| `skin_fbx` | `string` | Yes | See the operation parameters.  |
| `engine_revision` | `string` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `unirig`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation mesh_to_rig
```
