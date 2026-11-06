---
id: operation-refine-mesh
title: refine_mesh
description: Régénérer le détail géométrique d'une maille existante, en conservant sa forme globale : la maille est codée, sa présence devient la structure, et TRELLIS.2 redessine la forme à nouveau dessus à partir de l'image de référence,…
section: Référence
order: 200
parent: operations
sourceRevision: 544f4a27d69b8600
---

Régénérer le détail géométrique d'une maille existante, en conservant sa forme globale : la maille est codée, sa présence devient la structure, et TRELLIS.2 redessine la forme à nouveau dessus à partir de l'image de référence, jusqu'à la grille de 1536. La chaîne de nettoyage propre de LocalMesh ferme ensuite les trous, enlève les débris et la ramène au budget des faces, dans le cadre et à l'échelle de l'entrée. Seulement la géométrie : texturez le résultat avec "Texture a mesh for its own topology".

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Maille à affiner, Y-up et orientée comme la sortie de LocalMesh.  |
| `subject_set` | `string` | Non | Dossier produit par prepare_subject ou complete_subject : la référence de la découpe. `default=""` |
| `image` | `string` | Non | Image de référence, lorsque aucun jeu de sujets n'est disponible ; elle est ici coupée.  |
| `resolution` | `integer` | Non | Rééchantillonne la forme sur laquelle la forme est échantillonnée. 1536 nécessite une carte 24 GB et est abaissé par des étapes de 128 lorsque la forme a trop de tokens. `default=1536`, `enum=[1024, 1536]` |
| `target_faces` | `integer` | Non | Budjet des faces du résultat ; 0 utilise la recette de cette grille (250 000 sur 1024, 400 000 sur 1536). `default=0`, `minimum=0`, `maximum=1000000` |
| `use_all_views` | `boolean` | Non | Conditionne sur chaque vue du sujet, pas seulement la face avant. Expérimental. `default=false` |
| `steps` | `integer` | Non | Étapes d'échantillonnage du modèle de forme. `default=16`, `minimum=4`, `maximum=50` |
| `guidance` | `number` | Non | Conduite de forme ; 0 conserve la valeur propre des poids. `default=0.0`, `minimum=0.0`, `maximum=15.0` |
| `seed` | `integer` | Non | Semence (-1 tire un). `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `up_axis` | `string` | Non | Axe de montée de la maille d'entrée. `default="y"`, `enum=["y", "z"]` |
| `gpu` | `integer` | Non | GPU index. `default=0`, `minimum=0`, `maximum=7` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Oui | Maille raffinée (GLB, géométrie seulement).  |
| `report` | `string` | Non | rapport-réfined.json  |
| `seed` | `integer` | Non | Voir les paramètres de l’opération.  |
| `grid_resolution` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `token_cap` | `integer` | Non | Voir les paramètres de l’opération.  |
| `faces` | `integer` | Non | Voir les paramètres de l’opération.  |
| `vertices` | `integer` | Non | Voir les paramètres de l’opération.  |
| `peak_vram_gb` | `number` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `notes` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `trellis`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation refine_mesh
```
