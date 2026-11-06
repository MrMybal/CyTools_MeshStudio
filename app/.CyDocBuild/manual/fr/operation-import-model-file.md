---
id: operation-import-model-file
title: import_model_file
description: Placez un fichier que l'utilisateur a téléchargé lui-même après avoir accepté ses conditions d'utilisation, tel que le modèle de corps SMPL. L'application ne demande jamais les identifiants de ces sites ; elle vérifie le…
section: Référence
order: 200
parent: operations
sourceRevision: 5209c77e425c4705
---

Placez un fichier que l'utilisateur a téléchargé lui-même après avoir accepté ses conditions d'utilisation, tel que le modèle de corps SMPL. L'application ne demande jamais les identifiants de ces sites ; elle vérifie le fichier, le copie dans data/models et enregistre son hachage.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Oui | Télécharger les poids du modèle qui est déclaré mais absent, dans data/models. Les fichiers dont la licence est acceptée en personne ne sont jamais téléchargés ici : le nom des fichiers les nomme, et import_model_file les met en place une fois obtenus.  |
| `file` | `string` | Oui | Le fichier téléchargé depuis la page officielle (.pkl, ou le .zip qui le contient).  |
| `target` | `string` | Non | Quel est le fichier déclaré, lorsque le modèle attend plusieurs fichiers. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Oui | Voir les paramètres de l’opération.  |
| `state` | `string` | Oui | Voir les paramètres de l’opération.  |
| `file` | `string` | Oui | Le fichier installé.  |
| `sizeBytes` | `integer` | Non | Voir les paramètres de l’opération.  |
| `missingFiles` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation import_model_file
```
