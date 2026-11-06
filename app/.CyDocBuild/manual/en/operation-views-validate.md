---
id: operation-views-validate
title: views_validate
description: Score candidate views against the real photographs of the same object: identity, features, colour and materials.
section: Reference
order: 200
parent: operations
revision: 8fa8d8fd59e0b4d5
---

Score candidate views against the real photographs of the same object: identity, features, colour and materials.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `images` | `array` | Yes | One or more images of the same object. Image path: an absolute local path, or a path relative to data/inputs. The file is copied into the private job workspace automatically; no manual import is required. PNG, JPEG or WebP, at most 48 MiB and 60 megapixels. `default=[]` |
| `segmentation_backend` | `string` | No | sam2 uses the local SAM 2.1 weights. classical is a GrabCut fallback that needs no model. alpha uses the alpha channel of the supplied image. `default="sam2"`, `enum=["sam2", "classical", "alpha"]` |
| `device` | `string` | No | Auto selects CUDA when a device is present. CPU works for segmentation and analysis; generation on CPU is extremely slow and is not validated. `default="auto"`, `enum=["auto", "cuda", "cpu"]` |
| `force_same_object` | `boolean` | No | Same-object verification reports suspicious images and refuses to generate from them. Enable this to proceed anyway. `default=false` |
| `keep_input_copies` | `boolean` | No | Private input copies are deleted when the worker stops, including on failure and cancellation. Original files and generated results are never deleted. `default=false` |
| `candidates` | `array` | Yes | One or more images of the same object. Image path: an absolute local path, or a path relative to data/inputs. The file is copied into the private job workspace automatically; no manual import is required. PNG, JPEG or WebP, at most 48 MiB and 60 megapixels. `default=[]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `candidates` | `array` | Yes | See the operation parameters.  |
| `referenceCount` | `integer` | Yes | See the operation parameters.  |
| `device` | `string` | Yes | See the operation parameters.  |
| `deviceNote` | `string` | Yes | See the operation parameters.  |
| `directory` | `string` | Yes | See the operation parameters.  |
| `lowConfidenceViews` | `array` | Yes | See the operation parameters.  |
| `seconds` | `number` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `zero123plus`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation views_validate
```
