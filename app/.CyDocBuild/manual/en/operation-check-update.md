---
id: operation-check-update
title: check_update
description: Ask the configured GitHub repository for its latest release and compare it with the installed version. The engines and the weights streams answer from local files: they are updated by reinstalling an engine or a model, not by…
section: Reference
order: 200
parent: operations
revision: 5d957013ef3bd2ef
---

Ask the configured GitHub repository for its latest release and compare it with the installed version. The engines and the weights streams answer from local files: they are updated by reinstalling an engine or a model, not by a release.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `stream` | `string` | No | Which stream to check. `default="application"`, `enum=["application", "engines", "models"]` |
| `repository` | `string` | No | GitHub repository owner/name; saved in data/settings/updates.json. `default=""` |
| `release_file` | `string` | No | A release description already on disk, instead of asking GitHub (used by the tests). `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `stream` | `string` | Yes | See the operation parameters.  |
| `updateAvailable` | `boolean` | No | See the operation parameters.  |
| `message` | `string` | No | See the operation parameters.  |
| `report` | `object` | Yes | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation check_update
```
