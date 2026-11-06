---
id: operation-uv-unwrap
title: uv_unwrap
description: Générer des cartes UV et les packer dans un atlas unique avec xatlas.
section: Référence
order: 200
parent: operations
sourceRevision: ea45a023270c4a99
---

Générer des cartes UV et les packer dans un atlas unique avec xatlas.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `input` | `string` | Oui | Voir les paramètres de l’opération.  |
| `resolution` | `integer` | Non | Voir les paramètres de l’opération. `default=1024`, `minimum=64`, `maximum=4096` |
| `padding` | `integer` | Non | Voir les paramètres de l’opération. `default=4`, `minimum=0`, `maximum=32` |
| `iterations` | `integer` | Non | Voir les paramètres de l’opération. `default=1`, `minimum=1`, `maximum=10` |
| `maxCost` | `number` | Non | Voir les paramètres de l’opération. `default=2.0`, `minimum=0.1`, `maximum=10` |
| `bruteForce` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
| `rotateCharts` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `blockAlign` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
| `fixWinding` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh` | `string` | Oui | Voir les paramètres de l’opération.  |
| `preview` | `string` | Oui | Voir les paramètres de l’opération.  |
| `mapping` | `string` | Oui | Voir les paramètres de l’opération.  |
| `report` | `string` | Oui | Voir les paramètres de l’opération.  |
| `vertices` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `triangles` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `charts` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `width` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `height` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `utilization` | `number` | Oui | Voir les paramètres de l’opération. `minimum=0`, `maximum=1` |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : `xatlas`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation uv_unwrap
```
