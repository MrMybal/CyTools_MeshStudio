---
id: operation-run-workflow
title: run_workflow
description: Exécute une chaîne de traitement enregistrée sur un fichier d'entrée ou sur chaque fichier d'un dossier. Chaque étape est soumise comme une tâche réelle sur le même runtime que l'interface, les CLI et MCP.
section: Référence
order: 200
parent: operations
sourceRevision: 0de83acb79982a52
---

Exécute une chaîne de traitement enregistrée sur un fichier d'entrée ou sur chaque fichier d'un dossier. Chaque étape est soumise comme une tâche réelle sur le même runtime que l'interface, les CLI et MCP.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `workflow_name` | `string` | Non | Nom d'un workflow enregistré dans data/workflows. `default=""` |
| `workflow` | `object` | Non | Document de workflow intégré, au lieu d'un nom enregistré.  |
| `input_file` | `string` | Non | Entrée de la première étape.  |
| `input_folder` | `string` | Non | Dossier à traiter au lieu d'un seul fichier. `default=""` |
| `input_pattern` | `string` | Non | Glob appliqué à l'intérieur du dossier. `default="*"` |
| `input_mode` | `string` | Non | Surcharge le mode d'entrée du workflow : chacun (une exécution par fichier) ou ensemble (une exécution avec tous les fichiers). Vide : le workflow décide. `default=""`, `enum=["", "each", "together"]` |
| `keep_intermediate` | `boolean` | Non | Conservez la sortie de chaque étape, pas seulement la dernière. `default=true` |
| `stop_on_error` | `boolean` | Non | Arrêtez l'ensemble du workflow à la première étape échouée. `default=true` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `results` | `array` | Oui | Un enregistrement par entrée traitée.  |
| `outputs` | `array` | Oui | Fichiers finaux produits par le workflow.  |
| `report_file` | `string` | Non | Rapport de la mise en œuvre.  |
| `stepCount` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `inputCount` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `failedSteps` | `array` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation run_workflow
```
