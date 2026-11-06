---
id: operation-save-workflow
title: save_workflow
description: Écrivez un document de workflow dans data/workflows afin que l'interface, le CLI et le MCP puissent l'exécuter par nom.
section: Référence
order: 200
parent: operations
sourceRevision: 76ac7f7b5109508a
---

Écrivez un document de workflow dans data/workflows afin que l'interface, le CLI et le MCP puissent l'exécuter par nom.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `name` | `string` | Oui | Nom du workflow.  |
| `workflow` | `object` | Oui | Le document de workflow.  |
| `overwrite` | `boolean` | Non | Remplacez un workflow existant par le même nom. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Oui | Document enregistré.  |
| `name` | `string` | Oui | Voir les paramètres de l’opération.  |
| `stepCount` | `integer` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation save_workflow
```
