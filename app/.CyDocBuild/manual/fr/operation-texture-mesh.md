---
id: operation-texture-mesh
title: texture_mesh
description: Donnez un modèle remeshé — QuadWild quads, une retopologie, n’importe quel maillage aligné sur la référence — une texture faite pour cette topologie exacte. "generate" demande à TRELLIS.2 de générer la texture sur ce maillage…
section: Référence
order: 200
parent: operations
sourceRevision: b9e7cbae4b7c4c89
---

Donnez un modèle remeshé — QuadWild quads, une retopologie, n’importe quel maillage aligné sur la référence — une texture faite pour cette topologie exacte. "generate" demande à TRELLIS.2 de générer la texture sur ce maillage à partir de l'image de référence, comme LocalMesh le fait sur son propre maillage ; "transfer" ré-projecte la texture du modèle détaillé au lieu de cela, sans modèle. Le modèle détaillé, quand il est fourni, est également cuit dans une carte normale. Les quadrilatères sont conservés dans le OBJ ; le GLB est triangulé, comme glTF le requiert.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Maillage vers texture (OBJ conserve ses quadrilatères ; GLB, PLY, STL sont lus comme triangles). Y-up, orienté comme la sortie de LocalMesh.  |
| `subject_set` | `string` | Non | Dossier produit par prepare_subject ou complete_subject : la coupure de référence, et les autres vues pour la texturation multi-vues. `default=""` |
| `image` | `string` | Non | Image de référence, lorsque aucun jeu de sujets n'est disponible ; elle est ici coupée.  |
| `detail_mesh` | `string` | Non | Modèle détaillé aligné avec ce maillage (la sortie de LocalMesh) : cuit dans la carte normale, et la source de "transfer".  |
| `texture_source` | `string` | Non | generate : TRELLIS.2 génère la texture sur ce maillage. transfer : la texture du modèle détaillé est ré-projectée. `default="generate"`, `enum=["generate", "transfer"]` |
| `texture_size` | `integer` | Non | Côté de l’atlas en pixels. `default=4096`, `enum=[1024, 2048, 4096, 8192]` |
| `multiview_texture` | `boolean` | Non | Guidez la texture avec toutes les vues du sujet, pas seulement la face avant. Expérimental : jamais mesuré en amont. `default=false` |
| `resolution` | `integer` | Non | Modèle de grille de texture : 512 utilise le modèle 512, 1024 utilise le modèle 1024. `default=1024`, `enum=[512, 1024]` |
| `steps` | `integer` | Non | Étapes de prélèvement du modèle de texture. `default=16`, `minimum=4`, `maximum=50` |
| `guidance` | `number` | Non | Guidance du modèle de texture. `default=5.0`, `minimum=1.0`, `maximum=12.0` |
| `seed` | `integer` | Non | Semence (-1 tire un). `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `up_axis` | `string` | Non | Axe de montée de la maille d'entrée. `default="y"`, `enum=["y", "z"]` |
| `uv_padding` | `integer` | Non | Remplissage entre les îles UV, en texels. `default=4`, `minimum=1`, `maximum=32` |
| `gpu` | `integer` | Non | GPU index. `default=0`, `minimum=0`, `maximum=7` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Oui | GLB texturé (triangulé, PBR avec carte normale).  |
| `obj_file` | `string` | Oui | OBJ texturé qui conserve les quads, avec son MTL.  |
| `base_color_file` | `string` | Oui | Carte de couleur de base.  |
| `normal_file` | `string` | Non | Carte normale en espace tangente, lorsque un modèle détaillé a été fourni.  |
| `roughness_file` | `string` | Non | Carte de rugosité.  |
| `report` | `string` | Non | texture-report.json  |
| `seed` | `integer` | Non | Voir les paramètres de l’opération.  |
| `faces` | `integer` | Non | Voir les paramètres de l’opération.  |
| `polygons` | `integer` | Non | Voir les paramètres de l’opération.  |
| `polygons_kept` | `integer` | Non | Voir les paramètres de l’opération.  |
| `polygons_split` | `integer` | Non | Voir les paramètres de l’opération.  |
| `texture_size` | `integer` | Non | Voir les paramètres de l’opération.  |
| `texels_per_triangle` | `number` | Non | Voir les paramètres de l’opération.  |
| `peak_vram_gb` | `number` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `notes` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `trellis`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation texture_mesh
```
