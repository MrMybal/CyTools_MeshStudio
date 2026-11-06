---
id: operation-image-to-mesh-spar3d
title: image_to_mesh_spar3d
description: Reconstituez un objet sous forme d'un maillage texturé avec sa nuage de points. Le revers est inféré par le modèle, pas mesuré.
section: Référence
order: 200
parent: operations
sourceRevision: 723190db9b576e77
---

Reconstituez un objet sous forme d'un maillage texturé avec sa nuage de points. Le revers est inféré par le modèle, pas mesuré.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `image_file` | `string` | Non | PNG/JPEG/WEBP dans CYTOOLS_SPAR3D_INPUT_ROOT (par défaut : inputs). Optionnel lorsque subject_set est fourni.  |
| `texture_resolution` | `integer` | Non | Voir les paramètres de l’opération. `default=1024`, `enum=[512, 1024, 2048]` |
| `remesh` | `value` | Non | GLB triangule les faces même après le remeshing en quadrilatères. `default="none"`, `enum=["none", "triangle", "quad"]` |
| `target_vertices` | `integer` | Non | Cible de remeshing approximatif en sommets ; -1 conserve la valeur par défaut upstream. `default=-1`, `minimum=-1`, `maximum=100000` |
| `low_vram` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
| `gpu_index` | `integer` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=15` |
| `remove_background` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `foreground_ratio` | `number` | Non | Voir les paramètres de l’opération. `default=1.3`, `minimum=1.1`, `maximum=2` |
| `seed` | `integer` | Non | Voir les paramètres de l’opération. `default=42`, `minimum=0`, `maximum=2147483647` |
| `subject_set` | `string` | Non | Dossier produit par prepare_subject ; son découpage frontal remplace l'image et désactive la suppression du fond interne. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `point_cloud_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `preprocessed_image` | `string` | Oui | Voir les paramètres de l’opération.  |
| `report_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `remesh` | `string` | Oui | Voir les paramètres de l’opération.  |
| `export_topology` | `string` | Oui | Voir les paramètres de l’opération.  |
| `model_id` | `string` | Oui | Voir les paramètres de l’opération.  |
| `model_revision` | `string` | Oui | Voir les paramètres de l’opération.  |
| `source_revision` | `string` | Oui | Voir les paramètres de l’opération.  |
| `vertices` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `faces` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `seed` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `gpu_index` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `peak_vram_bytes` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `load_seconds` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `total_seconds` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `warnings` | `array` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `spar3d`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation image_to_mesh_spar3d
```
