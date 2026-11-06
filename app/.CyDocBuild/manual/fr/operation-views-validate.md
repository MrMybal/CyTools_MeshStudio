---
id: operation-views-validate
title: views_validate
description: Évaluez les vues des candidats contre les vraies photographies de l'objet même : identité, caractéristiques, couleur et matériaux.
section: Référence
order: 200
parent: operations
sourceRevision: 8fa8d8fd59e0b4d5
---

Évaluez les vues des candidats contre les vraies photographies de l'objet même : identité, caractéristiques, couleur et matériaux.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `images` | `array` | Oui | Un ou plusieurs images de l'objet même. Chemin d'image : un chemin local absolu, ou un chemin relatif à data/inputs. Le fichier est copié automatiquement dans l'espace de travail du job privé ; aucune importation manuelle n'est requise. PNG, JPEG ou WebP, pas plus de 48 MiB et 60 mégapixels. `default=[]` |
| `segmentation_backend` | `string` | Non | sam2 utilise les poids locaux SAM 2.1. classical est un échec de GrabCut qui n'a pas besoin de modèle. alpha utilise le canal alpha de l'image fournie. `default="sam2"`, `enum=["sam2", "classical", "alpha"]` |
| `device` | `string` | Non | Sélectionne automatiquement CUDA lorsque un appareil est présent. CPU fonctionne pour la segmentation et l'analyse ; la génération sur CPU est extrêmement lente et n'est pas validée. `default="auto"`, `enum=["auto", "cuda", "cpu"]` |
| `force_same_object` | `boolean` | Non | Les rapports de vérification d'objet identique signalent des images suspectes et refusent de les traiter. Activez cela pour continuer néanmoins. `default=false` |
| `keep_input_copies` | `boolean` | Non | Les copies d'entrée privées sont supprimées lorsque le worker s'arrête, y compris en cas d'échec et de annulation. Les fichiers originaux et les résultats générés ne sont jamais supprimés. `default=false` |
| `candidates` | `array` | Oui | Un ou plusieurs images de l'objet même. Chemin d'image : un chemin local absolu, ou un chemin relatif à data/inputs. Le fichier est copié automatiquement dans l'espace de travail du job privé ; aucune importation manuelle n'est requise. PNG, JPEG ou WebP, pas plus de 48 MiB et 60 mégapixels. `default=[]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `candidates` | `array` | Oui | Voir les paramètres de l’opération.  |
| `referenceCount` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `device` | `string` | Oui | Voir les paramètres de l’opération.  |
| `deviceNote` | `string` | Oui | Voir les paramètres de l’opération.  |
| `directory` | `string` | Oui | Voir les paramètres de l’opération.  |
| `lowConfidenceViews` | `array` | Oui | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `zero123plus`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation views_validate
```
