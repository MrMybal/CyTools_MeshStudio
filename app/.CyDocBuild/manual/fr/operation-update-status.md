---
id: operation-update-status
title: update_status
description: Où se trouvent les trois flux : la version de l'application et son dépôt, ce qui est en attente pour le prochain démarrage, les sauvegardes conservées, les moteurs et leurs révisions fixées, et le catalogue des modèles. Lit…
section: Référence
order: 200
parent: operations
sourceRevision: fac391b434c5178b
---

Où se trouvent les trois flux : la version de l'application et son dépôt, ce qui est en attente pour le prochain démarrage, les sauvegardes conservées, les moteurs et leurs révisions fixées, et le catalogue des modèles. Lit uniquement des fichiers locaux.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `application` | `object` | Oui | Voir les paramètres de l’opération.  |
| `pending` | `object/null` | Non | Voir les paramètres de l’opération.  |
| `lastApplied` | `object/null` | Non | Voir les paramètres de l’opération.  |
| `staged` | `array` | Non | Voir les paramètres de l’opération.  |
| `backups` | `array` | Non | Voir les paramètres de l’opération.  |
| `engines` | `array` | Non | Voir les paramètres de l’opération.  |
| `models` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update_status
```
