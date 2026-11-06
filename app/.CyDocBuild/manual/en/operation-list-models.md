---
id: operation-list-models
title: list_models
description: List every model of the catalogue with its family, its engine, its size on disk, its licence and whether it is installed.
section: Reference
order: 200
parent: operations
revision: ab63be49a3869202
---

List every model of the catalogue with its family, its engine, its size on disk, its licence and whether it is installed.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `family` | `string` | No | Restrict to one family. `default=""` |
| `installed_only` | `boolean` | No | Only the models present on disk. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `models` | `array` | Yes | See the operation parameters.  |
| `totalBytes` | `integer` | Yes | See the operation parameters.  |
| `directory` | `string` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_models
```
