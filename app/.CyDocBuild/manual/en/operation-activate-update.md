---
id: operation-activate-update
title: activate_update
description: Verify a staged update once more and record the swap for the next start. The folders are exchanged by a separate process before the application loads, so the running code is never replaced underneath itself, the previous app…
section: Reference
order: 200
parent: operations
revision: c03a7b49241f6205
---

Verify a staged update once more and record the swap for the next start. The folders are exchanged by a separate process before the application loads, so the running code is never replaced underneath itself, the previous app folder is kept as a backup, and data/ is not touched.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `staged` | `string` | No | Staged folder; the most recent one when left empty. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `pending` | `string` | Yes | The recorded request.  |
| `restartRequired` | `boolean` | Yes | See the operation parameters.  |
| `mode` | `string` | No | See the operation parameters.  |
| `version` | `string` | No | See the operation parameters.  |
| `fromVersion` | `string` | No | See the operation parameters.  |
| `source` | `string` | No | See the operation parameters.  |
| `requestedAt` | `string` | No | See the operation parameters.  |
| `verified` | `object` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation activate_update
```
