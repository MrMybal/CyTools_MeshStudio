---
id: operation-install-engine
title: install_engine
description: Créez ou réparez l'un des environnements d'engine déclarés dans app/engines.json, y compris les sources upstream qu'il nécessite. Les téléchargements se produisent ici, jamais pendant une tâche d'inference.
section: Référence
order: 200
parent: operations
sourceRevision: f8bd0f911f239327
---

Créez ou réparez l'un des environnements d'engine déclarés dans app/engines.json, y compris les sources upstream qu'il nécessite. Les téléchargements se produisent ici, jamais pendant une tâche d'inference.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engine` | `string` | Oui | Engine à installer. `enum=["geometry", "torch-cu124", "trellis", "diffusion", "wonder3d", "syncdreamer", "wham", "hi3dgen"]` |
| `device` | `string` | Non | Construisez la variante CUDA ou la variante CPU lorsque l'engine en offre une. `default="auto"`, `enum=["auto", "cuda", "cpu"]` |
| `repair` | `boolean` | Non | Reinstaller même si l'engine indique qu'il est déjà installé. `default=false` |
| `sources_only` | `boolean` | Non | Seulement récupérer ou mettre à jour les sources upstream. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `engine` | `string` | Oui | Voir les paramètres de l’opération.  |
| `state` | `string` | Oui | Voir les paramètres de l’opération.  |
| `python` | `string` | Non | Voir les paramètres de l’opération.  |
| `torch` | `string` | Non | Voir les paramètres de l’opération.  |
| `cuda` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `log_file` | `string` | Non | Journal complet de l'installation.  |
| `sources` | `object` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `warnings` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_engine
```
