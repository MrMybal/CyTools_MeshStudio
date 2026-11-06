---
id: operation-analyze-views
title: analyze_views
description: Pré-vue pour une reconstruction : segmentation, poses de vue, vérification d'objet, carte de couverture et la liste des points de vue manquants.
section: Référence
order: 200
parent: operations
sourceRevision: 0c17276b0806c9c6
---

Pré-vue pour une reconstruction : segmentation, poses de vue, vérification d'objet, carte de couverture et la liste des points de vue manquants.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `images` | `array` | Oui | Une à douze images réelles de l'objet SAME. Les images réelles prennent toujours le dessus sur les données synthétiques.  |
| `generated_views` | `array` | Non | Vues synthétiques optionnelles avec leurs poses demandées. Elles votent seulement avec un poids réduit et ne peuvent jamais supprimer ce que montre une image réelle. `default=[]` |
| `segmentation_model` | `string` | Non | SAM 2.1 pour le masque de l'objet. auto = modèle préféré installé, sinon segmentation classique (alpha / arrière-plan simple / GrabCut). none = segmentation classique seulement. `default="auto"`, `enum=["auto", "none", "sam2.1-hiera-tiny", "sam2.1-hiera-small", "sam2.1-hiera-base-plus", "sam2.1-hiera-large"]` |
| `depth_model` | `string` | Non | Profondeur Anything V2 (profondeur relative, indice de confiance faible). Base et Large sont CC-BY-NC-4.0 et nécessitent l'acceptation d'une licence personnelle. `default="auto"`, `enum=["auto", "none", "depth-anything-v2-small", "depth-anything-v2-base", "depth-anything-v2-large"]` |
| `camera_model` | `string` | Non | Champs de perspective (Paramnet-360Cities-edina-centered): roll, pitch (élevation = -pitch) et champ de vision de chaque image réelle. Appliqués seulement aux valeurs que l'utilisateur n'a pas données et seulement lorsque l'image montre un paysage ; sur un objet coupé, le signal est rapporté mais ne sert pas. Licence de recherche Adobe, non commerciale : acceptation personnelle requise. `default="auto"`, `enum=["auto", "none", "perspective-fields-paramnet-360cities"]` |
| `device` | `string` | Non | Dispositif de la phase de compréhension AI. auto = CUDA si PyTorch le voit, sinon CPU. Le moteur d'ajustement s'exécute toujours sur le CPU. `default="auto"`, `enum=["auto", "cuda", "cpu"]` |
| `view_synthesis` | `string` | Non | Génération de vues manquantes avec Zero123++ v1.2 (six vues à des poses connues à partir d'une seule image réelle, CUDA seulement). auto = seulement lorsque le score de couverture réelle est en dessous de synthesis_coverage_threshold et que le modèle est installé ; always = générer ou échouer ; off = jamais. Les vues générées votent avec generated_view_weight et ne jamais remplacer une image réelle. `default="auto"`, `enum=["off", "auto", "always"]` |
| `view_synthesis_model` | `string` | Non | Générateur de vues manquantes. auto = première version installée de Zero123++ v1.2 (6 vues, altitudes absolues +20/-10, FOV 30), Wonder3D v1.0 (6 vues orthographiques dans le cadre de l'image d'entrée, couleurs + normales) et SyncDreamer (16 vues à une altitude fixe de 30 degrés). Wonder3D et SyncDreamer s'exécutent dans leur propre environnement et un dépot source fixé (onglet Installation). Tous ont besoin d'un CUDA GPU. `default="auto"`, `enum=["auto", "zero123plus-v1.2", "wonder3d-v1.0", "syncdreamer"]` |
| `synthesis_source` | `integer` | Non | Index dans `images` de l'image donnée à Zero123++. -1 = première image qui n'est pas une vue de haut/bas. `default=-1`, `minimum=-1`, `maximum=11` |
| `synthesis_steps` | `integer` | Non | Étapes de diffusion du générateur. Ommis = sa propre valeur par défaut (Zero123++ 36, Wonder3D 50, SyncDreamer 50). `minimum=5`, `maximum=200` |
| `synthesis_seed` | `integer` | Non | Grain de sable aléatoire de Zero123++. Le même grain de sable, poids et durée donnent les mêmes vues ; une reproduction bit-exacte sur différents GPU n'est pas garantie. `default=0`, `minimum=0`, `maximum=2147483647` |
| `synthesis_guidance` | `number` | Non | Échelle de guidance sans classifieur. Ommis = la valeur par défaut du générateur (Zero123++ 4.0, Wonder3D 3.0, SyncDreamer 2.0). `minimum=1`, `maximum=10` |
| `synthesis_coverage_threshold` | `number` | Non | view_synthesis = auto génère des vues lorsque le Score de Couverture Réelle est en dessous de cette valeur. `default=0.6`, `minimum=0`, `maximum=1` |
| `symmetry` | `string` | Non | Utiliser les cartes de profondeur pour l'estimation de la pose et la taille de la concavité. `default="Auto"`, `enum=["Off", "Auto", "Force X", "Force Y", "Force Z"]` |
| `use_depth` | `boolean` | Non | Utiliser les cartes de profondeur pour l'estimation de la pose et la taille de la concavité. `default=true` |
| `register_views` | `boolean` | Non | Inscription classique de vues réelles (OpenCV SIFT + matrice essentielle) pour des images sans pose. `default=true` |
| `refine_poses` | `boolean` | Non | Affinement des vues sans pose par cohérence des silhouettes. `default=true` |
| `default_azimuth` | `number` | Non | Azimut supposé lorsque rien d'autre ne est connu (degrés). `default=35`, `minimum=-360`, `maximum=360` |
| `default_elevation` | `number` | Non | Élevation supposée lorsque rien d'autre ne est connu (degrés). `default=12`, `minimum=-90`, `maximum=90` |
| `default_fov` | `number` | Non | champ de vision supposé pour des images sans un (degrés, 0 = orthographique). `default=35`, `minimum=0`, `maximum=120` |
| `real_view_weight` | `number` | Non | Poids des images réelles. `default=1.0`, `minimum=0.1`, `maximum=1` |
| `generated_view_weight` | `number` | Non | Poids des vues synthétiques (recommandé 0,3 à 0,6). `default=0.45`, `minimum=0.05`, `maximum=0.9` |
| `mirrored_view_weight` | `number` | Non | Poids des vues réelles miroir, multiplié par la confiance de la symétrie. `default=0.8`, `minimum=0.05`, `maximum=1` |
| `single_view_symmetry_confidence` | `number` | Non | Confiance de la symétrie supposée lorsque celle-ci ne peut pas être mesurée. `default=0.5`, `minimum=0`, `maximum=1` |
| `symmetry_threshold` | `number` | Non | Symétrie automatique : rapport minimal de cohérence de silhouette avec/sans vues miroir. `default=0.93`, `minimum=0.5`, `maximum=1` |
| `depth_margin` | `number` | Non | Marge de sécurité de l'excavation en profondeur, fraction de la taille de l'objet. `default=0.12`, `minimum=0.02`, `maximum=0.5` |
| `complexity` | `string` | Non | Budget prédéfini. UltraSimple : 2-4 sections, environ 20-100 triangles. Simple : 4-8 sections, 100-500. Moyen : 8-16 sections, 500-2000. Cibles, pas de limites dures. `default="Simple"`, `enum=["UltraSimple", "Simple", "Medium"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `report_file` | `string` | Oui | Rapport JSON : vues, poses, couverture, scores, primitives, trace d'optimisation, sources de textures.  |
| `preview_file` | `string` | Oui | Feuille de contact PNG : masque (vert), volume de support (jaune), contour du proxy (rouge) pour chaque vue.  |
| `real_view_count` | `integer` | Non | Voir les paramètres de l’opération.  |
| `generated_view_count` | `integer` | Non | Voir les paramètres de l’opération.  |
| `real_coverage_score` | `number` | Oui | Score de couverture réelle, 0..1 sur la sphère de vues.  |
| `expected_reconstruction_confidence` | `number` | Oui | 0..1; plafonné à 0,5 pour une seule image.  |
| `symmetry_axis` | `string` | Non | Voir les paramètres de l’opération.  |
| `is_hypothesis` | `boolean` | Non | Vrai lorsque seule une vraie image était disponible.  |
| `missing_views` | `array` | Non | Voir les paramètres de l’opération.  |
| `understanding` | `object` | Non | Modèles et appareil réellement utilisés, mesuré pic de VRAM.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `proxyfit`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation analyze_views
```
