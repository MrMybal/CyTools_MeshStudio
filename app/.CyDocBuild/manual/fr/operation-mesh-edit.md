---
id: operation-mesh-edit
title: mesh_edit
description: Appliquez une chaîne d'éditions géométriques à une maille et écrivez le résultat : transformations, décimation, nettoyage, remplissage de trous, composants et enlèvement de matériaux. Chaque étape est déterministe et le…
section: Référence
order: 200
parent: operations
sourceRevision: cc326b7fcf45d08a
---

Appliquez une chaîne d'éditions géométriques à une maille et écrivez le résultat : transformations, décimation, nettoyage, remplissage de trous, composants et enlèvement de matériaux. Chaque étape est déterministe et le fichier d'entrée n'est jamais modifié.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Maille à éditer (GLB, glTF, OBJ, PLY, STL, OFF).  |
| `steps` | `array` | Oui | Éditions appliquées dans l'ordre.  |
| `output_format` | `string` | Non | Format de la maille écrite. `default="glb"`, `enum=["glb", "gltf", "obj", "ply", "stl"]` |
| `keep_materials` | `boolean` | Non | Transférer les matériaux et les textures vers le résultat lorsque le format le permet. `default=true` |
| `report` | `boolean` | Non | Écrire un rapport JSON avec l'état avant et après chaque étape. `default=true` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Maille éditée.  |
| `report_file` | `string` | Non | Rapport, lorsque demandé.  |
| `preview_file` | `string` | Non | Aperçu du résultat pour la vue 3D.  |
| `before` | `object` | Oui | Voir les paramètres de l’opération.  |
| `after` | `object` | Oui | Voir les paramètres de l’opération.  |
| `appliedSteps` | `array` | Oui | Voir les paramètres de l’opération.  |
| `warnings` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `meshedit`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation mesh_edit
```
