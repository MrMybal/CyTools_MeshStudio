---
id: operation-uv-unwrap
title: uv_unwrap
description: Generate UV charts and pack them into a single atlas with xatlas.
section: Reference
order: 200
parent: operations
revision: ea45a023270c4a99
---

Generate UV charts and pack them into a single atlas with xatlas.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `input` | `string` | Yes | See the operation parameters.  |
| `resolution` | `integer` | No | See the operation parameters. `default=1024`, `minimum=64`, `maximum=4096` |
| `padding` | `integer` | No | See the operation parameters. `default=4`, `minimum=0`, `maximum=32` |
| `iterations` | `integer` | No | See the operation parameters. `default=1`, `minimum=1`, `maximum=10` |
| `maxCost` | `number` | No | See the operation parameters. `default=2.0`, `minimum=0.1`, `maximum=10` |
| `bruteForce` | `boolean` | No | See the operation parameters. `default=false` |
| `rotateCharts` | `boolean` | No | See the operation parameters. `default=true` |
| `blockAlign` | `boolean` | No | See the operation parameters. `default=false` |
| `fixWinding` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh` | `string` | Yes | See the operation parameters.  |
| `preview` | `string` | Yes | See the operation parameters.  |
| `mapping` | `string` | Yes | See the operation parameters.  |
| `report` | `string` | Yes | See the operation parameters.  |
| `vertices` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `triangles` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `charts` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `width` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `height` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `utilization` | `number` | Yes | See the operation parameters. `minimum=0`, `maximum=1` |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: `xatlas`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation uv_unwrap
```
