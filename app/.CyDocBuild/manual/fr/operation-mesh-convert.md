---
id: operation-mesh-convert
title: mesh_convert
description: Convertir une maille entre les formats supportés, optionnellement la trianguler et insérer ou extraire ses textures.
section: Référence
order: 200
parent: operations
sourceRevision: f956b2b416a7b557
---

Convertir une maille entre les formats supportés, optionnellement la trianguler et insérer ou extraire ses textures.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Maille à convertir.  |
| `output_format` | `string` | Non | Format cible. `default="glb"`, `enum=["glb", "gltf", "obj", "ply", "stl", "off"]` |
| `triangulate` | `boolean` | Non | Trianguler les visages pendant la conversion. `default=false` |
| `embed_textures` | `boolean` | Non | Insérer les textures dans le fichier lorsque le format le permet. `default=true` |
| `scale` | `number` | Non | Échelle uniforme appliquée pendant la conversion. `default=1.0`, `minimum=1e-06` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Maillage converti.  |
| `textures` | `array` | Non | Textures écrites à côté du maillage.  |
| `vertices` | `integer` | Non | Voir les paramètres de l’opération.  |
| `faces` | `integer` | Non | Voir les paramètres de l’opération.  |
| `warnings` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `meshedit`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation mesh_convert
```
