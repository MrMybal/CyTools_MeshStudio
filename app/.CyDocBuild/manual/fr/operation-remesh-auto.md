---
id: operation-remesh-auto
title: remesh_auto
description: Reconstruire la topologie en une maillage quadrangulaire dominant avec le programme officiel AutoRemesher. Seulement la géométrie: UV définit et les matériaux de l'entrée ne sont pas transférés, et le quadrillage cible est…
section: Référence
order: 200
parent: operations
sourceRevision: f11fe56c0875c8ee
---

Reconstruire la topologie en une maillage quadrangulaire dominant avec le programme officiel AutoRemesher. Seulement la géométrie: UV définit et les matériaux de l'entrée ne sont pas transférés, et le quadrillage cible est approximatif.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `input_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `target_quads` | `integer` | Non | Voir les paramètres de l’opération. `default=1000`, `minimum=16`, `maximum=100000` |
| `edge_scaling` | `number` | Non | Voir les paramètres de l’opération. `default=1`, `minimum=1`, `maximum=4` |
| `sharp_edge` | `number` | Non | Voir les paramètres de l’opération. `default=90`, `minimum=30`, `maximum=180` |
| `smooth_normal` | `number` | Non | Voir les paramètres de l’opération. `default=0`, `minimum=0`, `maximum=180` |
| `adaptivity` | `number` | Non | Voir les paramètres de l’opération. `default=1`, `minimum=0`, `maximum=1` |
| `anisotropy` | `number` | Non | Voir les paramètres de l’opération. `default=1`, `minimum=0`, `maximum=1` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `report` | `string` | Oui | Voir les paramètres de l’opération.  |
| `log` | `string` | Oui | Voir les paramètres de l’opération.  |
| `mimeType` | `string` | Oui | Voir les paramètres de l’opération.  |
| `vertices` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `faces` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `quads` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `nonQuads` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `quadRatio` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0`, `maximum=1` |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : `autoremesher`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remesh_auto
```
