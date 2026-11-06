---
id: operation-list-models
title: list_models
description: Listez tous les modèles du catalogue avec leur famille, leur moteur, leur taille sur disque, leur licence et s'ils sont installés.
section: Référence
order: 200
parent: operations
sourceRevision: ab63be49a3869202
---

Listez tous les modèles du catalogue avec leur famille, leur moteur, leur taille sur disque, leur licence et s'ils sont installés.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `family` | `string` | Non | Restreint à une seule famille. `default=""` |
| `installed_only` | `boolean` | Non | Seulement les modèles présents sur disque. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `models` | `array` | Oui | Voir les paramètres de l’opération.  |
| `totalBytes` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `directory` | `string` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_models
```
