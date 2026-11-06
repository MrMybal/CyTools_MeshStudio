---
id: operation-save-workflow
title: save_workflow
description: Write a workflow document to data/workflows so that the interface, the CLI and MCP can run it by name.
section: Reference
order: 200
parent: operations
revision: 76ac7f7b5109508a
---

Write a workflow document to data/workflows so that the interface, the CLI and MCP can run it by name.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | Yes | Name of the workflow.  |
| `workflow` | `object` | Yes | The workflow document.  |
| `overwrite` | `boolean` | No | Replace an existing workflow with the same name. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | Yes | Saved document.  |
| `name` | `string` | Yes | See the operation parameters.  |
| `stepCount` | `integer` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation save_workflow
```
