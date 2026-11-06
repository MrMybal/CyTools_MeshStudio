---
id: operation-diagnose
title: diagnose
description: Rapporter l'état de chaque moteur, backend, programme natif et modèle : ce qui est installé, ce qui manque, et quel périphérique chaque backend utiliserait réellement.
section: Référence
order: 200
parent: operations
sourceRevision: 9d713b37b9059d38
---

Rapporter l'état de chaque moteur, backend, programme natif et modèle : ce qui est installé, ce qui manque, et quel périphérique chaque backend utiliserait réellement.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engine` | `string` | Non | Limiter le rapport à un seul moteur. `default=""` |
| `deep` | `boolean` | Non | Démarrer également chaque moteur installé pour rapporter son vrai torch et périphérique. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engines` | `object` | Oui | Voir les paramètres de l’opération.  |
| `backends` | `array` | Oui | Voir les paramètres de l’opération.  |
| `models` | `array` | Oui | Voir les paramètres de l’opération.  |
| `natives` | `object` | Non | Voir les paramètres de l’opération.  |
| `platform` | `object` | Non | Voir les paramètres de l’opération.  |
| `warnings` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation diagnose
```
