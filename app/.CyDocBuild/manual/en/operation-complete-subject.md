---
id: operation-complete-subject
title: complete_subject
description: From one picture, generate the right, left and back views with Wonder3D around the vertical axis of the picture, then cut the four views out at one common scale: a subject set for the four-view path of LocalMesh. Only for a…
section: Reference
order: 200
parent: operations
revision: 3ee645f6e4a931eb
---

From one picture, generate the right, left and back views with Wonder3D around the vertical axis of the picture, then cut the four views out at one common scale: a subject set for the four-view path of LocalMesh. Only for a level front view: with a three-quarter or top view the generated views are tilted and the fusion deforms the object. The generated views are marked as such, and LocalMesh measures their angles itself.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `image` | `string` | No | Reference picture of the subject (the front).  |
| `subject_set` | `string` | No | Folder produced by prepare_subject; its front cut-out is used. `default=""` |
| `seed` | `integer` | No | Wonder3D random seed. `default=42`, `minimum=0`, `maximum=2147483647` |
| `steps` | `integer` | No | Diffusion steps of Wonder3D. `default=50`, `minimum=10`, `maximum=100` |
| `guidance` | `number` | No | Guidance scale of Wonder3D. `default=3.0`, `minimum=1.0`, `maximum=10.0` |
| `gpu` | `integer` | No | GPU index. `default=0`, `minimum=0`, `maximum=7` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `subject_set` | `string` | Yes | The four cut-outs and subject.json.  |
| `subject_file` | `string` | Yes | subject.json.  |
| `contact_sheet` | `string` | No | The four views side by side.  |
| `views` | `array` | Yes | See the operation parameters.  |
| `viewCount` | `integer` | No | See the operation parameters.  |
| `generated` | `array` | No | See the operation parameters.  |
| `generator` | `string` | No | See the operation parameters.  |
| `wonder3d_folder` | `string` | No | The six raw Wonder3D views and their normal maps.  |
| `notes` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `wonder3d`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation complete_subject
```
