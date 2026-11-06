---
id: operation-video-inspect
title: video_inspect
description: Decode every frame and report a JPEG preview and the metadata of the file.
section: Reference
order: 200
parent: operations
revision: ee8a5f20866ec173
---

Decode every frame and report a JPEG preview and the metadata of the file.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `video` | `string` | Yes | Relative path in data/inputs, imported from ImGui.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `frames` | `integer` | Yes | See the operation parameters. `minimum=1` |
| `fps` | `number` | Yes | See the operation parameters.  |
| `width` | `integer` | Yes | See the operation parameters. `minimum=1` |
| `height` | `integer` | Yes | See the operation parameters. `minimum=1` |
| `duration` | `number` | Yes | See the operation parameters.  |
| `preview` | `string` | Yes | See the operation parameters.  |
| `report` | `string` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `wham`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation video_inspect
```
