---
id: operation-image-to-mesh-hi3dgen
title: image_to_mesh_hi3dgen
description: Hi3DGen (Stable-X): l'image devient une carte normale tranchée (StableNormal YOSO), et un TRELLIS v1 reconditionné sur les cartes normales transforme cette carte normale en une maillage. Seulement la géométrie, sur une grille…
section: Référence
order: 200
parent: operations
sourceRevision: 528260027de9798d
---

Hi3DGen (Stable-X): l'image devient une carte normale tranchée (StableNormal YOSO), et un TRELLIS v1 reconditionné sur les cartes normales transforme cette carte normale en une maillage. Seulement la géométrie, sur une grille de 256, dans le même cadre que la sortie LocalMesh : texturez-la avec "Texture a mesh for its own topology", ou régénérez d'abord son détail sur une grille de 1536 avec "Refine a mesh". Une image sans transparence est coupée en premier avec l'interface frontale partagée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `image` | `string` | Non | Image du personnage. Avec un canal alpha, elle est utilisée telle quelle ; sinon, elle est coupée avec BiRefNet en premier.  |
| `subject_set` | `string` | Non | Dossier produit par prepare_subject ou complete_subject : son cut-out frontal est utilisé. `default=""` |
| `seed` | `integer` | Non | Semence (-1 tire un). `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `normal_resolution` | `integer` | Non | Résolution de l'estimation de la carte normale. `default=768`, `enum=[512, 768, 1024]` |
| `ss_steps` | `integer` | Non | Étapes de prélèvement de la structure sparsitaire. `default=50`, `minimum=10`, `maximum=100` |
| `ss_guidance` | `number` | Non | Guidage de la structure sparsitaire. `default=3.0`, `minimum=0.0`, `maximum=10.0` |
| `slat_steps` | `integer` | Non | Étapes de prélèvement du latent structuré. `default=6`, `minimum=2`, `maximum=50` |
| `slat_guidance` | `number` | Non | Guidage du latent structuré. `default=3.0`, `minimum=0.0`, `maximum=10.0` |
| `origin_at_base` | `boolean` | Non | Placez la base de l'objet sur le plan du sol. `default=true` |
| `gpu` | `integer` | Non | GPU index. `default=0`, `minimum=0`, `maximum=7` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Oui | La maille (GLB, géométrie seulement).  |
| `normal_file` | `string` | Oui | La carte normale générée à partir de la géométrie utilisée.  |
| `prepared_file` | `string` | Non | La découpe, coupée et padding comme le modèle l'a vu.  |
| `subject_set` | `string` | Non | Le jeu de sujets utilisé, lorsque l'un a été préparé.  |
| `report` | `string` | Non | hi3dgen-report.json  |
| `seed` | `integer` | Non | Voir les paramètres de l’opération.  |
| `faces` | `integer` | Non | Voir les paramètres de l’opération.  |
| `vertices` | `integer` | Non | Voir les paramètres de l’opération.  |
| `peak_vram_gb` | `number` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `notes` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `hi3dgen`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation image_to_mesh_hi3dgen
```
