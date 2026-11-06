---
id: operation-remesh-field
title: remesh_field
description: Quadranguler aléatoirement un maillage triangulaire avec le programme officiel QuadWild Bi-MDF. Plus lent que AutoRemesher et limité par un temps de résolution, mais suit le champ de courbure.
section: Référence
order: 200
parent: operations
sourceRevision: 508cebdb25c03fde
---

Quadranguler aléatoirement un maillage triangulaire avec le programme officiel QuadWild Bi-MDF. Plus lent que AutoRemesher et limité par un temps de résolution, mais suit le champ de courbure.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `input` | `string` | Oui | Voir les paramètres de l’opération.  |
| `preRemesh` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `featureAngle` | `number` | Non | Voir les paramètres de l’opération. `default=35`, `minimum=0`, `maximum=180` |
| `scale` | `number` | Non | Voir les paramètres de l’opération. `default=1`, `minimum=0.1`, `maximum=10` |
| `align` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `solverSeconds` | `integer` | Non | Voir les paramètres de l’opération. `default=200`, `minimum=1`, `maximum=3600` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `vertices` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `faces` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `quads` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `triangles` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `report` | `string` | Oui | Voir les paramètres de l’opération.  |
| `mimeType` | `string` | Oui | Voir les paramètres de l’opération.  |
| `warnings` | `array` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : `quadwild`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remesh_field
```
