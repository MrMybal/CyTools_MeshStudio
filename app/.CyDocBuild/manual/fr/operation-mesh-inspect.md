---
id: operation-mesh-inspect
title: mesh_inspect
description: Rapport de géométrie, UV, source de couleur, matériaux et transparence d'un maillage, ainsi que les paramètres recommandés avant la cuisson.
section: Référence
order: 200
parent: operations
sourceRevision: 19c0adbb85966446
---

Rapport de géométrie, UV, source de couleur, matériaux et transparence d'un maillage, ainsi que les paramètres recommandés avant la cuisson.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Chemin du maillage à l'intérieur du répertoire de maillage configuré: GLB, GLTF, OBJ, PLY, STL, OFF.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `vertices` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `faces` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `geometry_count` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=1` |
| `file_bytes` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `is_watertight` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `bounds` | `array` | Oui | Voir les paramètres de l’opération.  |
| `extents` | `array` | Oui | Voir les paramètres de l’opération.  |
| `has_uv` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `uv_in_unit_square` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `material_type` | `string` | Oui | Voir les paramètres de l’opération.  |
| `color_source` | `value` | Oui | Voir les paramètres de l’opération. `enum=["texture", "vertex_colors", "base_color_factor", "none"]` |
| `has_vertex_colors` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `has_base_color_texture` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `base_color_texture_size` | `array` | Oui | Voir les paramètres de l’opération.  |
| `has_metallic_roughness_texture` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `has_alpha` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `recommended` | `object` | Oui | Voir les paramètres de l’opération.  |
| `warnings` | `array` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `meshedit`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation mesh_inspect
```
