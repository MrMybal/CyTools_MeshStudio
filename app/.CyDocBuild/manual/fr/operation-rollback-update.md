---
id: operation-rollback-update
title: rollback_update
description: Enregistrer l'échange inverse : le prochain démarrage restaure une sauvegarde conservée de la dossier de l'application. Annuler a lieu de cela annule la requête en attente. Vos données ne font jamais partie de ces mouvements.
section: Référence
order: 200
parent: operations
sourceRevision: c9f2c5461b025d9c
---

Enregistrer l'échange inverse : le prochain démarrage restaure une sauvegarde conservée de la dossier de l'application. Annuler a lieu de cela annule la requête en attente. Vos données ne font jamais partie de ces mouvements.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `backup` | `string` | Non | Dossier de sauvegarde pour restaurer ; le plus récent quand il est laissé vide. `default=""` |
| `cancel` | `boolean` | Non | Annuler la requête en attente au lieu de revenir en arrière. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `pending` | `string` | Non | Voir les paramètres de l’opération.  |
| `restartRequired` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `mode` | `string` | Non | Voir les paramètres de l’opération.  |
| `version` | `string` | Non | Voir les paramètres de l’opération.  |
| `fromVersion` | `string` | Non | Voir les paramètres de l’opération.  |
| `source` | `string` | Non | Voir les paramètres de l’opération.  |
| `cancelled` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `requestedAt` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation rollback_update
```
