---
id: operation-views-mirror
title: views_mirror
description: Générez la vue opposée en mirroir une image réelle. Un miroir géométrique, pas une génération : cela est valable uniquement pour un objet symétrique.
section: Référence
order: 200
parent: operations
sourceRevision: 05c53ea15ea3c9cd
---

Générez la vue opposée en mirroir une image réelle. Un miroir géométrique, pas une génération : cela est valable uniquement pour un objet symétrique.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `images` | `array` | Oui | Un ou plusieurs images de l'objet même. Chemin d'image : un chemin local absolu, ou un chemin relatif à data/inputs. Le fichier est copié automatiquement dans l'espace de travail du job privé ; aucune importation manuelle n'est requise. PNG, JPEG ou WebP, pas plus de 48 MiB et 60 mégapixels. `default=[]` |
| `segmentation_backend` | `string` | Non | sam2 utilise les poids locaux SAM 2.1. classical est un échec de GrabCut qui n'a pas besoin de modèle. alpha utilise le canal alpha de l'image fournie. `default="sam2"`, `enum=["sam2", "classical", "alpha"]` |
| `device` | `string` | Non | Sélectionne automatiquement CUDA lorsque un appareil est présent. CPU fonctionne pour la segmentation et l'analyse ; la génération sur CPU est extrêmement lente et n'est pas validée. `default="auto"`, `enum=["auto", "cuda", "cpu"]` |
| `force_same_object` | `boolean` | Non | Les rapports de vérification d'objet identique signalent des images suspectes et refusent de les traiter. Activez cela pour continuer néanmoins. `default=false` |
| `keep_input_copies` | `boolean` | Non | Les copies d'entrée privées sont supprimées lorsque le worker s'arrête, y compris en cas d'échec et de annulation. Les fichiers originaux et les résultats générés ne sont jamais supprimés. `default=false` |
| `background` | `string` | Non | écrits transparents RGBA à l'aide du masque d'objet. compositage neutre sur un gris plat. l'original conserve le fond généré par le backend. `default="transparent"`, `enum=["transparent", "neutral", "original"]` |
| `resolution` | `integer` | Non | 0 conserve la résolution native du backend. Une valeur plus grande n'est prise en compte que lorsque le redimensionnement est activé ; le redimensionnement n'ajoute aucune détail. `default=0`, `enum=[0, 320, 512, 768, 1024]` |
| `upscale` | `boolean` | Non | Rechantillonnage de Lanczos uniquement. Cette Outil ne réalise aucune super résolution. `default=false` |
| `symmetry` | `string` | Non | auto ne reflète une vue existante que lorsque la symétrie de la silhouette mesurée dépasse le seuil. force reflète de toute façon et marque le résultat. off ne reflète jamais. `default="auto"`, `enum=["auto", "off", "force"]` |
| `symmetry_threshold` | `number` | Non | Score de symétrie minimum silhouettée accepté pour un miroir automatique. `default=0.82`, `minimum=0.0`, `maximum=1.0` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `viewSet` | `string` | Oui | Voir les paramètres de l’opération.  |
| `directory` | `string` | Oui | Voir les paramètres de l’opération.  |
| `thumbnail` | `string` | Oui | Voir les paramètres de l’opération.  |
| `views` | `array` | Oui | Voir les paramètres de l’opération.  |
| `coverage` | `object` | Oui | Voir les paramètres de l’opération.  |
| `sameObjectConfidence` | `number` | Oui | Voir les paramètres de l’opération.  |
| `recommendations` | `array` | Oui | Voir les paramètres de l’opération.  |
| `requestedViews` | `array` | Non | Voir les paramètres de l’opération.  |
| `generatedCount` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `realCount` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `lowConfidenceViews` | `array` | Oui | Voir les paramètres de l’opération.  |
| `seeds` | `array` | Oui | Voir les paramètres de l’opération.  |
| `symmetryScore` | `number` | Non | Voir les paramètres de l’opération.  |
| `device` | `string` | Oui | Voir les paramètres de l’opération.  |
| `peakVramGiB` | `number` | Oui | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Oui | Voir les paramètres de l’opération.  |
| `notes` | `array` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `mirror`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation views_mirror
```
