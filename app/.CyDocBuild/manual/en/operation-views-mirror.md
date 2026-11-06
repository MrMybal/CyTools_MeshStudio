---
id: operation-views-mirror
title: views_mirror
description: Produce the opposite view by mirroring one real image. A geometric flip, not a generation: it is only valid for a symmetric object.
section: Reference
order: 200
parent: operations
revision: 05c53ea15ea3c9cd
---

Produce the opposite view by mirroring one real image. A geometric flip, not a generation: it is only valid for a symmetric object.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `images` | `array` | Yes | One or more images of the same object. Image path: an absolute local path, or a path relative to data/inputs. The file is copied into the private job workspace automatically; no manual import is required. PNG, JPEG or WebP, at most 48 MiB and 60 megapixels. `default=[]` |
| `segmentation_backend` | `string` | No | sam2 uses the local SAM 2.1 weights. classical is a GrabCut fallback that needs no model. alpha uses the alpha channel of the supplied image. `default="sam2"`, `enum=["sam2", "classical", "alpha"]` |
| `device` | `string` | No | Auto selects CUDA when a device is present. CPU works for segmentation and analysis; generation on CPU is extremely slow and is not validated. `default="auto"`, `enum=["auto", "cuda", "cpu"]` |
| `force_same_object` | `boolean` | No | Same-object verification reports suspicious images and refuses to generate from them. Enable this to proceed anyway. `default=false` |
| `keep_input_copies` | `boolean` | No | Private input copies are deleted when the worker stops, including on failure and cancellation. Original files and generated results are never deleted. `default=false` |
| `background` | `string` | No | transparent writes RGBA using the object mask. neutral composites on a flat grey. original keeps the background the backend produced. `default="transparent"`, `enum=["transparent", "neutral", "original"]` |
| `resolution` | `integer` | No | 0 keeps the native resolution of the backend. A larger value only applies when resampling is enabled; resampling adds no detail. `default=0`, `enum=[0, 320, 512, 768, 1024]` |
| `upscale` | `boolean` | No | Lanczos resampling only. This Tool performs no super resolution. `default=false` |
| `symmetry` | `string` | No | auto mirrors an existing view only when the measured silhouette symmetry passes the threshold. force mirrors regardless and marks the result. off never mirrors. `default="auto"`, `enum=["auto", "off", "force"]` |
| `symmetry_threshold` | `number` | No | Minimum silhouette symmetry score accepted for an automatic mirror. `default=0.82`, `minimum=0.0`, `maximum=1.0` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `viewSet` | `string` | Yes | See the operation parameters.  |
| `directory` | `string` | Yes | See the operation parameters.  |
| `thumbnail` | `string` | Yes | See the operation parameters.  |
| `views` | `array` | Yes | See the operation parameters.  |
| `coverage` | `object` | Yes | See the operation parameters.  |
| `sameObjectConfidence` | `number` | Yes | See the operation parameters.  |
| `recommendations` | `array` | Yes | See the operation parameters.  |
| `requestedViews` | `array` | No | See the operation parameters.  |
| `generatedCount` | `integer` | Yes | See the operation parameters.  |
| `realCount` | `integer` | Yes | See the operation parameters.  |
| `lowConfidenceViews` | `array` | Yes | See the operation parameters.  |
| `seeds` | `array` | Yes | See the operation parameters.  |
| `symmetryScore` | `number` | No | See the operation parameters.  |
| `device` | `string` | Yes | See the operation parameters.  |
| `peakVramGiB` | `number` | Yes | See the operation parameters.  |
| `seconds` | `number` | Yes | See the operation parameters.  |
| `notes` | `array` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `mirror`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation views_mirror
```
