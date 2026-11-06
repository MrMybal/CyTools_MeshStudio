---
id: operation-install-engine
title: install_engine
description: Create or repair one of the engine environments declared in app/engines.json, including the upstream sources it needs. Downloads happen here, never during an inference job.
section: Reference
order: 200
parent: operations
revision: f8bd0f911f239327
---

Create or repair one of the engine environments declared in app/engines.json, including the upstream sources it needs. Downloads happen here, never during an inference job.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `engine` | `string` | Yes | Engine to install. `enum=["geometry", "torch-cu124", "trellis", "diffusion", "wonder3d", "syncdreamer", "wham", "hi3dgen"]` |
| `device` | `string` | No | Build the CUDA variant or the CPU variant when the engine offers one. `default="auto"`, `enum=["auto", "cuda", "cpu"]` |
| `repair` | `boolean` | No | Reinstall even when the engine reports itself as installed. `default=false` |
| `sources_only` | `boolean` | No | Only fetch or update the upstream sources. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `engine` | `string` | Yes | See the operation parameters.  |
| `state` | `string` | Yes | See the operation parameters.  |
| `python` | `string` | No | See the operation parameters.  |
| `torch` | `string` | No | See the operation parameters.  |
| `cuda` | `boolean` | No | See the operation parameters.  |
| `log_file` | `string` | No | Full installation log.  |
| `sources` | `object` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `warnings` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_engine
```
