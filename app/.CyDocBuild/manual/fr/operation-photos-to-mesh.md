---
id: operation-photos-to-mesh
title: photos_to_mesh
description: LocalMesh : une image, ou quatre photographies du même sujet, pour un GLB texturé. Le modèle TRELLIS.2 génère la forme ; la maille est ensuite nettoyée, remeshée et réduite, et sa texture PBR est générée pour cette maille…
section: Référence
order: 200
parent: operations
sourceRevision: e34c947941ef3fd0
---

LocalMesh : une image, ou quatre photographies du même sujet, pour un GLB texturé. Le modèle TRELLIS.2 génère la forme ; la maille est ensuite nettoyée, remeshée et réduite, et sa texture PBR est générée pour cette maille finale, avec un map normal bake. Inférence locale CUDA.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mode` | `string` | Non | Voir les paramètres de l’opération. `default="single"`, `enum=["single", "four"]` |
| `front` | `string` | Non | Chemin de l'image : chemin local absolu ou relatif à data/inputs. Copié automatiquement dans l'espace de travail privé du job ; pas de import manuel nécessaire. PNG/JPEG/WebP, pas plus de 32 MiB et 40 mégapixels. Optionnel lorsque subject_set est donné. `default=""` |
| `right` | `string` | Non | Chemin de l'image : chemin local absolu ou relatif à data/inputs. Copié automatiquement dans l'espace de travail privé du job ; pas de import manuel nécessaire. PNG/JPEG/WebP, pas plus de 32 MiB et 40 mégapixels. `default=""` |
| `left` | `string` | Non | Chemin de l'image : chemin local absolu ou relatif à data/inputs. Copié automatiquement dans l'espace de travail privé du job ; pas de import manuel nécessaire. PNG/JPEG/WebP, pas plus de 32 MiB et 40 mégapixels. `default=""` |
| `back` | `string` | Non | Chemin de l'image : chemin local absolu ou relatif à data/inputs. Copié automatiquement dans l'espace de travail privé du job ; pas de import manuel nécessaire. PNG/JPEG/WebP, pas plus de 32 MiB et 40 mégapixels. `default=""` |
| `tier` | `string` | Non | draft : 512 grille, 80 000 faces, 2K atlas, pour juger de la forme. standard : 1024 grille, 150 000 faces, 4K atlas. high : 1024 grille, 16 passes, 250 000 faces, 4K atlas. max : 1536 grille, 400 000 faces, 8K atlas ; nécessite une carte 24 GB, et avec quatre photos elle utilise le vieux mixeur de vue car les modèles à quatre vues s'arrêtent à 1024. `default="standard"`, `enum=["draft", "standard", "high", "max"]` |
| `seed` | `integer` | Non | Voir les paramètres de l’opération. `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `gpu` | `integer` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=15` |
| `sampler` | `string` | Non | Voir les paramètres de l’opération. `default="recipe"`, `enum=["recipe", "euler", "heun", "rk4", "rk5"]` |
| `transparency` | `string` | Non | Voir les paramètres de l’opération. `default="auto"`, `enum=["auto", "opaque", "mask", "blend"]` |
| `up_axis` | `string` | Non | Voir les paramètres de l’opération. `default="y"`, `enum=["y", "z"]` |
| `texture_size` | `integer` | Non | Voir les paramètres de l’opération. `default=0`, `enum=[0, 1024, 2048, 4096]` |
| `target_faces` | `integer` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=400000` |
| `real_size_mm` | `number` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=100000` |
| `fidelity` | `number` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=20` |
| `tex_guidance` | `number` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=20` |
| `steps_structure` | `integer` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=100` |
| `steps_shape` | `integer` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=100` |
| `steps_texture` | `integer` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=100` |
| `bake_normal_map` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `origin_at_base` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `remove_floaters` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `fill_holes` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `keep_input_copies` | `boolean` | Non | Par défaut, les copies d'entrée privées sont supprimées après que le worker s'arrête, y compris en cas d'échec ou d'annulation. Activez uniquement pour les conserver à des fins de débogage. Les fichiers originaux et les sorties générées ne sont jamais supprimés. `default=false` |
| `subject_set` | `string` | Non | Dossier produit par prepare_subject. Ses coupures sont utilisées comme les vues, donc le sujet est segmenté une seule fois pour toute la workflow au lieu d'une fois par backend. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `mimeType` | `string` | Oui | Voir les paramètres de l’opération.  |
| `report` | `string` | Oui | Voir les paramètres de l’opération.  |
| `thumbnail` | `string` | Oui | Voir les paramètres de l’opération.  |
| `seed` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `faces` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `vertices` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Oui | Voir les paramètres de l’opération.  |
| `peak_vram_gb` | `number` | Oui | Voir les paramètres de l’opération.  |
| `notes` | `array` | Oui | Voir les paramètres de l’opération.  |
| `grid_resolution` | `integer` | Non | Grille sur laquelle la forme a été vraiment échantillonnée. La cascade 1536 diminue par étapes de 128 lorsque l'objet a plus de tokens que la carte ne le permet.  |
| `token_cap` | `integer` | Non | Plafond de tokens appliqué, pris sur la mémoire disponible au début du job.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `trellis`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation photos_to_mesh
```
