---
id: operation-install-model
title: install_model
description: Download the weights of a model that is declared but absent, into data/models. Files whose licence is accepted in person are never downloaded here: the answer names them, and importmodelfile puts them in place once obtained.
section: Reference
order: 200
parent: operations
revision: b7e1630679b742ee
---

Download the weights of a model that is declared but absent, into data/models. Files whose licence is accepted in person are never downloaded here: the answer names them, and import_model_file puts them in place once obtained.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | Model identifier, as list_models reports it.  |
| `repair` | `boolean` | No | Download again even when the files are already present. `default=false` |
| `skip_optional` | `boolean` | No | Leave the optional files out (global motion for WHAM). `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | See the operation parameters.  |
| `state` | `string` | Yes | See the operation parameters.  |
| `directory` | `string` | No | Where the model was installed.  |
| `missingFiles` | `array` | No | See the operation parameters.  |
| `manualFiles` | `array` | No | See the operation parameters.  |
| `log_file` | `string` | No | Full download log.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `warnings` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_model
```
