---
id: operation-stage-update
title: stage_update
description: Download or copy a release archive, check its SHA-256 when one is given, unpack it under runtime/updates and verify it holds this Tool and no data folder. Nothing is activated: the running application is untouched.
section: Reference
order: 200
parent: operations
revision: 2bbce71fd6859a2d
---

Download or copy a release archive, check its SHA-256 when one is given, unpack it under runtime/updates and verify it holds this Tool and no data folder. Nothing is activated: the running application is untouched.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `source` | `string` | Yes | URL of the release asset, or a local .zip.  |
| `sha256` | `string` | No | Expected SHA-256 of the archive; refused when it differs. `default=""` |
| `version` | `string` | No | Name of the staging folder; defaults to the archive digest. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `staged` | `string` | Yes | Where the update was unpacked.  |
| `version` | `string` | Yes | See the operation parameters.  |
| `sha256` | `string` | No | See the operation parameters.  |
| `stream` | `string` | No | See the operation parameters.  |
| `source` | `string` | No | See the operation parameters.  |
| `files` | `integer` | No | See the operation parameters.  |
| `archiveBytes` | `integer` | No | See the operation parameters.  |
| `stagedAt` | `string` | No | See the operation parameters.  |
| `verified` | `object` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation stage_update
```
