---
id: operation-install-model
title: install_model
description: Identifiant du modèle, tel que rapporté par listmodels.
section: Référence
order: 200
parent: operations
sourceRevision: b7e1630679b742ee
---

Identifiant du modèle, tel que rapporté par list_models.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Oui | Télécharger les poids du modèle qui est déclaré mais absent, dans data/models. Les fichiers dont la licence est acceptée en personne ne sont jamais téléchargés ici : le nom des fichiers les nomme, et import_model_file les met en place une fois obtenus.  |
| `repair` | `boolean` | Non | Télécharger à nouveau même si les fichiers sont déjà présents. `default=false` |
| `skip_optional` | `boolean` | Non | Omettre les fichiers optionnels (mouvement global pour WHAM). `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Oui | Voir les paramètres de l’opération.  |
| `state` | `string` | Oui | Voir les paramètres de l’opération.  |
| `directory` | `string` | Non | Où le modèle a été installé.  |
| `missingFiles` | `array` | Non | Voir les paramètres de l’opération.  |
| `manualFiles` | `array` | Non | Voir les paramètres de l’opération.  |
| `log_file` | `string` | Non | Journal complet de téléchargement.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `warnings` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_model
```
