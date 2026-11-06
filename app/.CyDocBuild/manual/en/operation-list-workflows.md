---
id: operation-list-workflows
title: list_workflows
description: List the workflows saved in data/workflows with their steps and the operations they use.
section: Reference
order: 200
parent: operations
revision: a305fa77045d58f7
---

List the workflows saved in data/workflows with their steps and the operations they use.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `include_steps` | `boolean` | No | Include the full step list of every workflow. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `workflows` | `array` | Yes | See the operation parameters.  |
| `directory` | `string` | Yes | Where the workflows are stored.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_workflows
```
