---
id: operation-prepare-subject
title: prepare_subject
description: Cut the subject out of every view once, at a common scale, and measure where each photograph was taken from. The result is a subject set that every reconstruction backend can consume, instead of each one carrying its own…
section: Reference
order: 200
parent: operations
revision: a1cd86e7aae760f9
---

Cut the subject out of every view once, at a common scale, and measure where each photograph was taken from. The result is a subject set that every reconstruction backend can consume, instead of each one carrying its own background remover and its own camera estimate.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `front` | `string` | No | Reference view of the subject. Optional when images are given.  |
| `right` | `string` | No | Right side view.  |
| `left` | `string` | No | Left side view.  |
| `back` | `string` | No | Back view.  |
| `images` | `array` | No | Views of the same subject. Without a front view, the role of each is read from its file name (front, right, left, back, or face, droite, gauche, dos); the first one without a role becomes the front.  |
| `common_framing` | `boolean` | No | Cut every view at one common scale. Required by a multi-view fusion: framing each view on its own scales an elongated object differently per view. `default=true` |
| `measure_camera` | `boolean` | No | Measure the azimuth of each view instead of assuming a regular turntable. `default=true` |
| `contact_sheet` | `boolean` | No | Write a contact sheet of the prepared views. `default=true` |
| `gpu` | `integer` | No | GPU index. `default=0`, `minimum=0`, `maximum=15` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `subject_set` | `string` | Yes | Folder holding the prepared views and their description.  |
| `subject_file` | `string` | Yes | The subject description (JSON).  |
| `views` | `array` | Yes | See the operation parameters.  |
| `contact_sheet` | `string` | No | Contact sheet of the prepared views.  |
| `camera` | `object` | No | See the operation parameters.  |
| `viewCount` | `integer` | Yes | See the operation parameters.  |
| `commonFraming` | `boolean` | No | See the operation parameters.  |
| `notes` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `birefnet`, `sam2`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation prepare_subject
```
