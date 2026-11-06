---
id: operation-remesh-field
title: remesh_field
description: Field aligned quadrangulation of a triangulated mesh with the official QuadWild Bi-MDF binaries. Slower than AutoRemesher and bounded by a solver time limit, but follows the curvature field.
section: Reference
order: 200
parent: operations
revision: 508cebdb25c03fde
---

Field aligned quadrangulation of a triangulated mesh with the official QuadWild Bi-MDF binaries. Slower than AutoRemesher and bounded by a solver time limit, but follows the curvature field.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `input` | `string` | Yes | See the operation parameters.  |
| `preRemesh` | `boolean` | No | See the operation parameters. `default=true` |
| `featureAngle` | `number` | No | See the operation parameters. `default=35`, `minimum=0`, `maximum=180` |
| `scale` | `number` | No | See the operation parameters. `default=1`, `minimum=0.1`, `maximum=10` |
| `align` | `boolean` | No | See the operation parameters. `default=true` |
| `solverSeconds` | `integer` | No | See the operation parameters. `default=200`, `minimum=1`, `maximum=3600` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `vertices` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `faces` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `quads` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `triangles` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `file` | `string` | Yes | See the operation parameters.  |
| `report` | `string` | Yes | See the operation parameters.  |
| `mimeType` | `string` | Yes | See the operation parameters.  |
| `warnings` | `array` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: `quadwild`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remesh_field
```
