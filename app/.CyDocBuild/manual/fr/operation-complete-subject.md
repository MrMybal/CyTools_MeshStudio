---
id: operation-complete-subject
title: complete_subject
description: À partir d'une image, générer les vues droite, gauche et arrière avec Wonder3D autour de l'axe vertical de l'image, puis couper les quatre vues en une échelle commune : un ensemble de sujets pour le chemin de quatre vues de…
section: Référence
order: 200
parent: operations
sourceRevision: 3ee645f6e4a931eb
---

À partir d'une image, générer les vues droite, gauche et arrière avec Wonder3D autour de l'axe vertical de l'image, puis couper les quatre vues en une échelle commune : un ensemble de sujets pour le chemin de quatre vues de LocalMesh. Seulement pour une vue frontale de niveau : avec une vue trois-quarts ou supérieure, les vues générées sont inclinées et la fusion déforme l'objet. Les vues générées sont marquées comme telles, et LocalMesh mesure leurs angles lui-même.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `image` | `string` | Non | Image de référence du sujet (la face avant).  |
| `subject_set` | `string` | Non | Répertoire produit par prepare_subject ; son coupé frontal est utilisé. `default=""` |
| `seed` | `integer` | Non | Graine aléatoire Wonder3D. `default=42`, `minimum=0`, `maximum=2147483647` |
| `steps` | `integer` | Non | Étapes de diffusion de Wonder3D. `default=50`, `minimum=10`, `maximum=100` |
| `guidance` | `number` | Non | Échelle de guidance de Wonder3D. `default=3.0`, `minimum=1.0`, `maximum=10.0` |
| `gpu` | `integer` | Non | GPU index. `default=0`, `minimum=0`, `maximum=7` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `subject_set` | `string` | Oui | Les quatre cut-outs et subject.json.  |
| `subject_file` | `string` | Oui | subject.json  |
| `contact_sheet` | `string` | Non | Les quatre vues placées côte à côte.  |
| `views` | `array` | Oui | Voir les paramètres de l’opération.  |
| `viewCount` | `integer` | Non | Voir les paramètres de l’opération.  |
| `generated` | `array` | Non | Voir les paramètres de l’opération.  |
| `generator` | `string` | Non | Voir les paramètres de l’opération.  |
| `wonder3d_folder` | `string` | Non | Les six vues brutes de Wonder3D et leurs cartes normales.  |
| `notes` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `wonder3d`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation complete_subject
```
