---
id: operation-views-turntable
title: views_turntable
description: Produce N equally spaced views around the object, on one ring or on several rings at different elevations.
section: Reference
order: 200
parent: operations
revision: 420aaa561a842141
---

Produce N equally spaced views around the object, on one ring or on several rings at different elevations.

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
| `allow_mirror` | `boolean` | No | Mirroring an existing view is instant and uses no model, but it assumes bilateral symmetry. `default=true` |
| `prefer_real` | `boolean` | No | When a real photograph already covers a requested viewpoint it is reused instead of generated. `default=true` |
| `reuse_tolerance` | `number` | No | Angular distance in degrees within which a real photograph answers a requested viewpoint. `default=15.0`, `minimum=0.0`, `maximum=90.0` |
| `seed` | `integer` | No | -1 draws a seed. The resolved seed is reported in the outputs and in the View Set so a run can be repeated. `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `steps` | `integer` | No | Only used by backends that expose a step count. `default=36`, `minimum=4`, `maximum=200` |
| `guidance` | `number` | No | Classifier-free guidance of the generation backend. `default=4.0`, `minimum=0.5`, `maximum=20.0` |
| `variants` | `integer` | No | Each variant is a complete generation with its own seed, so the best one can be selected afterwards. `default=1`, `minimum=1`, `maximum=8` |
| `generate_normals` | `boolean` | No | Uses the Zero123++ normal ControlNet. It also produces a matted alpha channel that is more accurate than the segmentation backend. `default=false` |
| `normal_guidance` | `number` | No | Guidance used for the normal pass only. `default=4.0`, `minimum=0.5`, `maximum=20.0` |
| `condition_ratio` | `number` | No | Fraction of the square conditioning image the object occupies before generation. `default=0.95`, `minimum=0.5`, `maximum=1.0` |
| `count` | `integer` | No | Number of equally spaced azimuths on each ring. `default=8`, `minimum=2`, `maximum=36` |
| `elevation` | `number` | No | Used when no explicit list of ring elevations is given. `default=0.0`, `minimum=-90`, `maximum=90` |
| `start_azimuth` | `number` | No | See the operation parameters. `default=0.0`, `minimum=-180`, `maximum=180` |
| `ring_elevations` | `array` | No | One ring per elevation, for example [0, 30, -20]. Overrides the single ring elevation when present.  |
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
- Backends: `zero123plus`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation views_turntable
```
