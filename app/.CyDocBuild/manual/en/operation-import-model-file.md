---
id: operation-import-model-file
title: import_model_file
description: Put in place a file the user downloaded themselves after accepting its licence, such as the SMPL body model. The application never asks for the credentials of those sites; it checks the file, copies it into data/models and…
section: Reference
order: 200
parent: operations
revision: 5209c77e425c4705
---

Put in place a file the user downloaded themselves after accepting its licence, such as the SMPL body model. The application never asks for the credentials of those sites; it checks the file, copies it into data/models and records its hash.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | Model identifier, as list_models reports it.  |
| `file` | `string` | Yes | The file downloaded from the official page (.pkl, or the .zip holding it).  |
| `target` | `string` | No | Which declared file this is, when the model expects several. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | See the operation parameters.  |
| `state` | `string` | Yes | See the operation parameters.  |
| `file` | `string` | Yes | The installed file.  |
| `sizeBytes` | `integer` | No | See the operation parameters.  |
| `missingFiles` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation import_model_file
```
