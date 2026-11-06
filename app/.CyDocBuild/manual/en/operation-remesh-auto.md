---
id: operation-remesh-auto
title: remesh_auto
description: Rebuild the topology as a quad dominant mesh with the official AutoRemesher program. Geometry only: UV sets and materials of the input are not carried over, and the quad target is approximate.
section: Reference
order: 200
parent: operations
revision: f11fe56c0875c8ee
---

Rebuild the topology as a quad dominant mesh with the official AutoRemesher program. Geometry only: UV sets and materials of the input are not carried over, and the quad target is approximate.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `input_file` | `string` | Yes | See the operation parameters.  |
| `target_quads` | `integer` | No | See the operation parameters. `default=1000`, `minimum=16`, `maximum=100000` |
| `edge_scaling` | `number` | No | See the operation parameters. `default=1`, `minimum=1`, `maximum=4` |
| `sharp_edge` | `number` | No | See the operation parameters. `default=90`, `minimum=30`, `maximum=180` |
| `smooth_normal` | `number` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=180` |
| `adaptivity` | `number` | No | See the operation parameters. `default=1`, `minimum=0`, `maximum=1` |
| `anisotropy` | `number` | No | See the operation parameters. `default=1`, `minimum=0`, `maximum=1` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | Yes | See the operation parameters.  |
| `report` | `string` | Yes | See the operation parameters.  |
| `log` | `string` | Yes | See the operation parameters.  |
| `mimeType` | `string` | Yes | See the operation parameters.  |
| `vertices` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `faces` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `quads` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `nonQuads` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `quadRatio` | `number` | Yes | See the operation parameters. `minimum=0`, `maximum=1` |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: `autoremesher`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remesh_auto
```
