---
id: operation-prepare-subject
title: prepare_subject
description: Couper le sujet dans chaque vue une seule fois, à une échelle commune, et mesurer depuis où a été prise chaque photographie. Le résultat est un ensemble de sujets que chaque backend de reconstruction peut consommer, au lieu de…
section: Référence
order: 200
parent: operations
sourceRevision: a1cd86e7aae760f9
---

Couper le sujet dans chaque vue une seule fois, à une échelle commune, et mesurer depuis où a été prise chaque photographie. Le résultat est un ensemble de sujets que chaque backend de reconstruction peut consommer, au lieu de chacun devoir son propre débarras de fond et son propre estimation de la caméra.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `front` | `string` | Non | Vue de référence du sujet. Optionnel lorsque les images sont fournies.  |
| `right` | `string` | Non | Vue latérale droite.  |
| `left` | `string` | Non | Vue latérale gauche.  |
| `back` | `string` | Non | Vue arrière.  |
| `images` | `array` | Non | Vues du même sujet. Sans vue avant, le rôle de chacune est lu de son nom de fichier (avant, droit, gauche, arrière, ou face, avant, droite, gauche, dos); la première sans rôle devient l'avant.  |
| `common_framing` | `boolean` | Non | Couper chaque vue à une échelle commune. Requis par une fusion multi-vues: encadrer chaque vue à ses propres échelles encadre différemment un objet allongé par vue. `default=true` |
| `measure_camera` | `boolean` | Non | Mesurer l'azimut de chaque vue au lieu de supposer une tourte régulière. `default=true` |
| `contact_sheet` | `boolean` | Non | Écrire un feuilleton de contact des vues préparées. `default=true` |
| `gpu` | `integer` | Non | GPU index. `default=0`, `minimum=0`, `maximum=15` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `subject_set` | `string` | Oui | Répertoire contenant les vues préparées et leur description.  |
| `subject_file` | `string` | Oui | La description du sujet (JSON).  |
| `views` | `array` | Oui | Voir les paramètres de l’opération.  |
| `contact_sheet` | `string` | Non | Feuille de contact des vues préparées.  |
| `camera` | `object` | Non | Voir les paramètres de l’opération.  |
| `viewCount` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `commonFraming` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `notes` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `birefnet`, `sam2`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation prepare_subject
```
