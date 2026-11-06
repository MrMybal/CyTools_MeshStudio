---
id: operation-stage-update
title: stage_update
description: Télécharger ou copier une archive de la release, vérifier son SHA-256 lorsque celui-ci est fourni, décompresser l'archive sous runtime/updates et vérifier qu'elle contient cette Outils et pas de dossier de données. Rien n'est…
section: Référence
order: 200
parent: operations
sourceRevision: 2bbce71fd6859a2d
---

Télécharger ou copier une archive de la release, vérifier son SHA-256 lorsque celui-ci est fourni, décompresser l'archive sous runtime/updates et vérifier qu'elle contient cette Outils et pas de dossier de données. Rien n'est activé : l'application en cours de fonctionnement n'est pas modifiée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `source` | `string` | Oui | URL de l'actif de la release, ou un fichier .zip local.  |
| `sha256` | `string` | Non | SHA-256 attendu de l'archive ; refusé si celui-ci diffère. `default=""` |
| `version` | `string` | Non | Nom du dossier de préparation ; par défaut, il est le digest de l'archive. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `staged` | `string` | Oui | Où l'update a été décompressée.  |
| `version` | `string` | Oui | Voir les paramètres de l’opération.  |
| `sha256` | `string` | Non | Voir les paramètres de l’opération.  |
| `stream` | `string` | Non | Voir les paramètres de l’opération.  |
| `source` | `string` | Non | Voir les paramètres de l’opération.  |
| `files` | `integer` | Non | Voir les paramètres de l’opération.  |
| `archiveBytes` | `integer` | Non | Voir les paramètres de l’opération.  |
| `stagedAt` | `string` | Non | Voir les paramètres de l’opération.  |
| `verified` | `object` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation stage_update
```
