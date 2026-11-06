---
id: operation-activate-update
title: activate_update
description: Vérifier une update préparée une fois de plus et enregistrer le remplacement pour le prochain démarrage. Les dossiers sont échangés par un processus distinct avant que l'application ne charge, de sorte que le code en cours de…
section: Référence
order: 200
parent: operations
sourceRevision: c03a7b49241f6205
---

Vérifier une update préparée une fois de plus et enregistrer le remplacement pour le prochain démarrage. Les dossiers sont échangés par un processus distinct avant que l'application ne charge, de sorte que le code en cours de fonctionnement n'est jamais remplacé sous lui-même, le dossier de l'application précédente est conservé en tant que sauvegarde, et data/ n'est pas touché.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `staged` | `string` | Non | Dossier préparé ; le plus récent quand il est laissé vide. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `pending` | `string` | Oui | La requête enregistrée.  |
| `restartRequired` | `boolean` | Oui | Voir les paramètres de l’opération.  |
| `mode` | `string` | Non | Voir les paramètres de l’opération.  |
| `version` | `string` | Non | Voir les paramètres de l’opération.  |
| `fromVersion` | `string` | Non | Voir les paramètres de l’opération.  |
| `source` | `string` | Non | Voir les paramètres de l’opération.  |
| `requestedAt` | `string` | Non | Voir les paramètres de l’opération.  |
| `verified` | `object` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation activate_update
```
