---
id: operation-views-auto-complete
title: views_auto_complete
description: Analysez les images fournies, décidez quelles perspectives importantes sont manquantes et générez uniquement celles-ci.
section: Référence
order: 200
parent: operations
sourceRevision: a843b427ef9ec820
---

Analysez les images fournies, décidez quelles perspectives importantes sont manquantes et générez uniquement celles-ci.

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
| `allow_mirror` | `boolean` | Non | Le miroir d'une vue existante est instantané et ne utilise aucun modèle, mais il suppose une symétrie bilatérale. `default=true` |
| `prefer_real` | `boolean` | Non | Lorsqu'une photographie réelle couvre déjà un point de vue demandé, elle est réutilisée au lieu de être générée. `default=true` |
| `reuse_tolerance` | `number` | Non | Distance angulaire en degrés au sein de laquelle une photographie réelle répond à un point de vue demandé. `default=15.0`, `minimum=0.0`, `maximum=90.0` |
| `seed` | `integer` | Non | -1 trace une semence. La semence résolue est rapportée dans les sorties et dans l'ensemble des vues afin que la même exécution puisse être répétée. `default=-1`, `minimum=-1`, `maximum=2147483647` |
| `steps` | `integer` | Non | Utilisé uniquement par les backends qui exposent un comptage de pas. `default=36`, `minimum=4`, `maximum=200` |
| `guidance` | `number` | Non | Guidance sans classifieur pour la back-end de génération. `default=4.0`, `minimum=0.5`, `maximum=20.0` |
| `variants` | `integer` | Non | Chaque variant est une génération complète avec sa propre semence, de sorte que la meilleure puisse être sélectionnée ultérieurement. `default=1`, `minimum=1`, `maximum=8` |
| `generate_normals` | `boolean` | Non | Utilise le Zero123++ normal ControlNet. Il produit également un canal alpha moulé qui est plus précis que le back-end de segmentation. `default=false` |
| `normal_guidance` | `number` | Non | Guidance utilisé uniquement pour le passage normal. `default=4.0`, `minimum=0.5`, `maximum=20.0` |
| `condition_ratio` | `number` | Non | Partie de l'image d'conditionnement au carré que l'objet occupe avant la génération. `default=0.95`, `minimum=0.5`, `maximum=1.0` |
| `include_polar` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `max_views` | `integer` | Non | Voir les paramètres de l’opération. `default=8`, `minimum=1`, `maximum=16` |
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
- Moteurs : `zero123plus`, `mirror`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation views_auto_complete
```
