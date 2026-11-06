---
id: operation-image-to-mesh-triposr
title: image_to_mesh_triposr
description: Reconstituez un objet à partir d'une seule image en secondes : NeRF feed-forward puis cubes de marche, couleurs de sommet ou un atlas de textures bakes. Prototypage rapide, pas une mesure de l'objet réel.
section: Référence
order: 200
parent: operations
sourceRevision: 8259358e5848deb3
---

Reconstituez un objet à partir d'une seule image en secondes : NeRF feed-forward puis cubes de marche, couleurs de sommet ou un atlas de textures bakes. Prototypage rapide, pas une mesure de l'objet réel.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `image_file` | `string` | Non | PNG/JPEG/WEBP dans CYTOOLS_TRIPOSR_INPUT_ROOT (par défaut : inputs). Optionnel lorsque subject_set est fourni.  |
| `mc_resolution` | `integer` | Non | Résolution de la grille de cubes de marche. Moins est rapide et plus coarsier. `default=256`, `enum=[128, 192, 256, 320, 384]` |
| `density_threshold` | `number` | Non | Voir les paramètres de l’opération. `default=25`, `minimum=1`, `maximum=100` |
| `chunk_size` | `integer` | Non | Voir les paramètres de l’opération. `default=8192`, `minimum=0`, `maximum=131072` |
| `output_format` | `value` | Non | GLB transporte des couleurs de sommet. La bake d'un atlas de textures nécessite obj. `default="glb"`, `enum=["glb", "obj"]` |
| `bake_texture` | `boolean` | Non | Bake un atlas de textures avec xatlas et moderngl au lieu de couleurs de sommet. Nécessite un contexte OpenGL fonctionnel et output_format obj. `default=false` |
| `texture_resolution` | `integer` | Non | Voir les paramètres de l’opération. `default=1024`, `enum=[512, 1024, 2048]` |
| `remove_background` | `boolean` | Non | Exécutez rembg sur l'entrée. Désactivez uniquement pour une image qui a déjà un fond propre et centré. `default=true` |
| `foreground_ratio` | `number` | Non | Partie de la frame occupée par l'objet après le crop. `default=0.85`, `minimum=0.5`, `maximum=1` |
| `device` | `value` | Non | CPU est supporté par le code source upstream mais est bien plus lent ; ce n'est pas un chemin validé ici. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `gpu_index` | `integer` | Non | Indice du périphérique NVIDIA, ignoré lorsque device vaut cpu. `default=0`, `minimum=0`, `maximum=15` |
| `preview_views` | `integer` | Non | Nombre de prévisualisations tournante PNG rendues par NeRF. 0 saute la rendu. `default=0`, `minimum=0`, `maximum=8` |
| `preview_size` | `integer` | Non | Voir les paramètres de l’opération. `default=256`, `enum=[128, 256, 512]` |
| `subject_set` | `string` | Non | Dossier produit par prepare_subject ; son découpage frontal remplace l'image et désactive la suppression du fond interne. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `texture_file` | `string` | Oui | Chaîne vide lorsque les couleurs des sommets sont utilisées.  |
| `preprocessed_image` | `string` | Oui | Voir les paramètres de l’opération.  |
| `preview_files` | `array` | Oui | Voir les paramètres de l’opération.  |
| `report_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `output_format` | `string` | Oui | Voir les paramètres de l’opération.  |
| `bake_texture` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `has_vertex_colors` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `vertices` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `faces` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `mc_resolution` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `density_threshold` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `model_id` | `string` | Oui | Voir les paramètres de l’opération.  |
| `model_revision` | `string` | Oui | Voir les paramètres de l’opération.  |
| `source_revision` | `string` | Oui | Voir les paramètres de l’opération.  |
| `device` | `string` | Oui | Voir les paramètres de l’opération.  |
| `gpu_index` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `cuda_marching_cubes` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `peak_vram_bytes` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `load_seconds` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `inference_seconds` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `mesh_seconds` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `total_seconds` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `warnings` | `array` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `triposr`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation image_to_mesh_triposr
```
