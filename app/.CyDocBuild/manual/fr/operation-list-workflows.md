---
id: operation-list-workflows
title: list_workflows
description: Listez les workflows enregistrés dans data/workflows avec leurs étapes et les opérations qu'ils utilisent.
section: Référence
order: 200
parent: operations
sourceRevision: a305fa77045d58f7
---

Listez les workflows enregistrés dans data/workflows avec leurs étapes et les opérations qu'ils utilisent.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `include_steps` | `boolean` | Non | Incluez la liste complète d'étapes de chaque workflow. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `workflows` | `array` | Oui | Voir les paramètres de l’opération.  |
| `directory` | `string` | Oui | Où sont stockés les workflows.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_workflows
```
