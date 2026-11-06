---
id: operation-check-update
title: check_update
description: Demandez au dépôt GitHub configuré sa dernière release et comparez-la avec la version installée. Les flux des moteurs et des poids répondent à partir de des fichiers locaux : ils sont mis à jour en réinstallant un moteur ou un…
section: Référence
order: 200
parent: operations
sourceRevision: 5d957013ef3bd2ef
---

Demandez au dépôt GitHub configuré sa dernière release et comparez-la avec la version installée. Les flux des moteurs et des poids répondent à partir de des fichiers locaux : ils sont mis à jour en réinstallant un moteur ou un modèle, pas par une release.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stream` | `string` | Non | Quel flux vérifier. `default="application"`, `enum=["application", "engines", "models"]` |
| `repository` | `string` | Non | Propriétaire du dépôt GitHub/nom du dépôt; enregistré dans data/settings/updates.json. `default=""` |
| `release_file` | `string` | Non | Une description de la release déjà enregistrée sur le disque, au lieu de demander à GitHub (utilisé par les tests). `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `stream` | `string` | Oui | Voir les paramètres de l’opération.  |
| `updateAvailable` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `message` | `string` | Non | Voir les paramètres de l’opération.  |
| `report` | `object` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation check_update
```
