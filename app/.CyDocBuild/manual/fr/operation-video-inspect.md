---
id: operation-video-inspect
title: video_inspect
description: Décodez chaque cadre et rappelez une prévisualisation JPEG et les métadonnées du fichier.
section: Référence
order: 200
parent: operations
sourceRevision: ee8a5f20866ec173
---

Décodez chaque cadre et rappelez une prévisualisation JPEG et les métadonnées du fichier.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `video` | `string` | Oui | Chemin relatif dans data/inputs, importe depuis ImGui.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `frames` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=1` |
| `fps` | `number` | Oui | Voir les paramètres de l’opération.  |
| `width` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=1` |
| `height` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=1` |
| `duration` | `number` | Oui | Voir les paramètres de l’opération.  |
| `preview` | `string` | Oui | Voir les paramètres de l’opération.  |
| `report` | `string` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `wham`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation video_inspect
```
