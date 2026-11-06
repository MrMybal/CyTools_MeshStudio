---
id: operation-run-workflow
title: run_workflow
description: Run a saved chain of operations on one input or on every file of a folder. Each step is submitted as a real job on the same runtime as the interface, the CLI and MCP.
section: Reference
order: 200
parent: operations
revision: 0de83acb79982a52
---

Run a saved chain of operations on one input or on every file of a folder. Each step is submitted as a real job on the same runtime as the interface, the CLI and MCP.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `workflow_name` | `string` | No | Name of a workflow saved in data/workflows. `default=""` |
| `workflow` | `object` | No | Inline workflow document, instead of a saved name.  |
| `input_file` | `string` | No | Input of the first step.  |
| `input_folder` | `string` | No | Folder to process instead of a single file. `default=""` |
| `input_pattern` | `string` | No | Glob applied inside the folder. `default="*"` |
| `input_mode` | `string` | No | Overrides the input mode of the workflow: each (one run per file) or together (one run with every file). Empty: the workflow decides. `default=""`, `enum=["", "each", "together"]` |
| `keep_intermediate` | `boolean` | No | Keep the output of every step, not only the last one. `default=true` |
| `stop_on_error` | `boolean` | No | Stop the whole workflow at the first failed step. `default=true` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `results` | `array` | Yes | One entry per input processed.  |
| `outputs` | `array` | Yes | Final files produced by the workflow.  |
| `report_file` | `string` | No | Report of the run.  |
| `stepCount` | `integer` | Yes | See the operation parameters.  |
| `inputCount` | `integer` | Yes | See the operation parameters.  |
| `failedSteps` | `array` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation run_workflow
```
