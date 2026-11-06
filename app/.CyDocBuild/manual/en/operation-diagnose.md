---
id: operation-diagnose
title: diagnose
description: Report the state of every engine, backend, native program and model: what is installed, what is missing, and which device each backend would really use.
section: Reference
order: 200
parent: operations
revision: 9d713b37b9059d38
---

Report the state of every engine, backend, native program and model: what is installed, what is missing, and which device each backend would really use.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `engine` | `string` | No | Restrict the report to one engine. `default=""` |
| `deep` | `boolean` | No | Also start each installed engine to report its real torch and device. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `engines` | `object` | Yes | See the operation parameters.  |
| `backends` | `array` | Yes | See the operation parameters.  |
| `models` | `array` | Yes | See the operation parameters.  |
| `natives` | `object` | No | See the operation parameters.  |
| `platform` | `object` | No | See the operation parameters.  |
| `warnings` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation diagnose
```
