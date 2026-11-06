---
id: operation-update-status
title: update_status
description: Where the three streams stand: the application version and its repository, what is staged, what is pending for the next start, the backups kept, the engines and their pinned revisions, and the model catalogue. Reads local…
section: Reference
order: 200
parent: operations
revision: fac391b434c5178b
---

Where the three streams stand: the application version and its repository, what is staged, what is pending for the next start, the backups kept, the engines and their pinned revisions, and the model catalogue. Reads local files only.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `application` | `object` | Yes | See the operation parameters.  |
| `pending` | `object/null` | No | See the operation parameters.  |
| `lastApplied` | `object/null` | No | See the operation parameters.  |
| `staged` | `array` | No | See the operation parameters.  |
| `backups` | `array` | No | See the operation parameters.  |
| `engines` | `array` | No | See the operation parameters.  |
| `models` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_status
```
