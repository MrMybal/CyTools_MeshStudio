---
id: operation-mesh-to-rig
title: mesh_to_rig
description: Prédisez un squelette et des poids de peau pour une maille avec UniRig Articulation-XL.
section: Référence
order: 200
parent: operations
sourceRevision: 29c6ef7e93f1c07d
---

Prédisez un squelette et des poids de peau pour une maille avec UniRig Articulation-XL.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh` | `string` | Oui | Voir les paramètres de l’opération.  |
| `seed` | `integer` | Non | Voir les paramètres de l’opération. `default=12345`, `minimum=0`, `maximum=2147483647` |
| `faces_target` | `integer` | Non | Voir les paramètres de l’opération. `default=50000`, `minimum=500`, `maximum=50000` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `rigged_mesh` | `string` | Oui | Voir les paramètres de l’opération.  |
| `skeleton` | `string` | Oui | Voir les paramètres de l’opération.  |
| `skin_weights` | `string` | Oui | Voir les paramètres de l’opération.  |
| `skeleton_fbx` | `string` | Oui | Voir les paramètres de l’opération.  |
| `skin_fbx` | `string` | Oui | Voir les paramètres de l’opération.  |
| `engine_revision` | `string` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `unirig`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation mesh_to_rig
```
