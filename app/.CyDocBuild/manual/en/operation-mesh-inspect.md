---
id: operation-mesh-inspect
title: mesh_inspect
description: Report geometry, UV, colour source, materials and transparency of a mesh, plus the settings recommended before baking.
section: Reference
order: 200
parent: operations
revision: 19c0adbb85966446
---

Report geometry, UV, colour source, materials and transparency of a mesh, plus the settings recommended before baking.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `mesh_file` | `string` | Yes | Mesh path inside the configured mesh root: GLB, GLTF, OBJ, PLY, STL, OFF.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `vertices` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `faces` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `geometry_count` | `integer` | Yes | See the operation parameters. `minimum=1` |
| `file_bytes` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `is_watertight` | `boolean` | Yes | See the operation parameters.  |
| `bounds` | `array` | Yes | See the operation parameters.  |
| `extents` | `array` | Yes | See the operation parameters.  |
| `has_uv` | `boolean` | Yes | See the operation parameters.  |
| `uv_in_unit_square` | `boolean` | Yes | See the operation parameters.  |
| `material_type` | `string` | Yes | See the operation parameters.  |
| `color_source` | `value` | Yes | See the operation parameters. `enum=["texture", "vertex_colors", "base_color_factor", "none"]` |
| `has_vertex_colors` | `boolean` | Yes | See the operation parameters.  |
| `has_base_color_texture` | `boolean` | Yes | See the operation parameters.  |
| `base_color_texture_size` | `array` | Yes | See the operation parameters.  |
| `has_metallic_roughness_texture` | `boolean` | Yes | See the operation parameters.  |
| `has_alpha` | `boolean` | Yes | See the operation parameters.  |
| `recommended` | `object` | Yes | See the operation parameters.  |
| `warnings` | `array` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: `meshedit`
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation mesh_inspect
```
