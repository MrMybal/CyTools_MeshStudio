---
id: operation-video-to-motion
title: video_to_motion
description: Reconstituez les poses, les translations et les marques temporelles des personnes dans une vidéo monoscopique : SMPL.
section: Référence
order: 200
parent: operations
sourceRevision: fc3ff5f0a7de4000
---

Reconstituez les poses, les translations et les marques temporelles des personnes dans une vidéo monoscopique : SMPL.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `video` | `string` | Oui | Chemin relatif dans data/inputs, importe depuis ImGui.  |
| `global_motion` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
| `flip_eval` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `refine` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
| `gpu_index` | `integer` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=7` |
| `ram_budget_gib` | `integer` | Non | Voir les paramètres de l’opération. `default=8`, `minimum=1`, `maximum=128` |
| `vram_budget_gib` | `integer` | Non | Voir les paramètres de l’opération. `default=12`, `minimum=1`, `maximum=80` |
| `disk_budget_gib` | `integer` | Non | Voir les paramètres de l’opération. `default=4`, `minimum=1`, `maximum=500` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `motion` | `string` | Oui | Voir les paramètres de l’opération.  |
| `report` | `string` | Oui | Voir les paramètres de l’opération.  |
| `people` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=1` |
| `coordinates` | `string` | Oui | Voir les paramètres de l’opération. `enum=["world", "camera"]` |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `wham`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation video_to_motion
```
