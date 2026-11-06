---
id: operation-video-to-motion
title: video_to_motion
description: Reconstruct SMPL poses, translations and time stamps of the people in a monocular video.
section: Reference
order: 200
parent: operations
revision: fc3ff5f0a7de4000
---

Reconstruct SMPL poses, translations and time stamps of the people in a monocular video.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `video` | `string` | Yes | Relative path in data/inputs, imported from ImGui.  |
| `global_motion` | `boolean` | No | See the operation parameters. `default=false` |
| `flip_eval` | `boolean` | No | See the operation parameters. `default=true` |
| `refine` | `boolean` | No | See the operation parameters. `default=false` |
| `gpu_index` | `integer` | No | See the operation parameters. `default=0`, `minimum=0`, `maximum=7` |
| `ram_budget_gib` | `integer` | No | See the operation parameters. `default=8`, `minimum=1`, `maximum=128` |
| `vram_budget_gib` | `integer` | No | See the operation parameters. `default=12`, `minimum=1`, `maximum=80` |
| `disk_budget_gib` | `integer` | No | See the operation parameters. `default=4`, `minimum=1`, `maximum=500` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `motion` | `string` | Yes | See the operation parameters.  |
| `report` | `string` | Yes | See the operation parameters.  |
| `people` | `integer` | Yes | See the operation parameters. `minimum=1` |
| `coordinates` | `string` | Yes | See the operation parameters. `enum=["world", "camera"]` |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `wham`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation video_to_motion
```
