---
id: operation-rollback-update
title: rollback_update
description: Record the reverse swap: the next start restores a kept backup of the app folder. Cancelling instead drops a pending request. Your data is never part of either move.
section: Reference
order: 200
parent: operations
revision: c9f2c5461b025d9c
---

Record the reverse swap: the next start restores a kept backup of the app folder. Cancelling instead drops a pending request. Your data is never part of either move.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `backup` | `string` | No | Backup folder to restore; the most recent one when left empty. `default=""` |
| `cancel` | `boolean` | No | Drop the pending request instead of rolling back. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `pending` | `string` | No | See the operation parameters.  |
| `restartRequired` | `boolean` | Yes | See the operation parameters.  |
| `mode` | `string` | No | See the operation parameters.  |
| `version` | `string` | No | See the operation parameters.  |
| `fromVersion` | `string` | No | See the operation parameters.  |
| `source` | `string` | No | See the operation parameters.  |
| `cancelled` | `boolean` | No | See the operation parameters.  |
| `requestedAt` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation rollback_update
```
