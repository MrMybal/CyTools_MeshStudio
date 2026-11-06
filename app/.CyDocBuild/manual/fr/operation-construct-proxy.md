---
id: operation-construct-proxy
title: construct_proxy
description: Créez un simple et propre maillage proxy en surface (loft de sections transversales, extrusion de polygones, boîtes, cylindres) à partir d'une ou plusieurs images de l'objet, et projetez les images dessus. Les modèles AI ne…
section: Référence
order: 200
parent: operations
sourceRevision: 552320758c7e504e
---

Créez un simple et propre maillage proxy en surface (loft de sections transversales, extrusion de polygones, boîtes, cylindres) à partir d'une ou plusieurs images de l'objet, et projetez les images dessus. Les modèles AI ne fournissent que des masques, une profondeur relative, des poses de caméra et des vues synthétiques optionnelles.

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
| `main_axis` | `string` | Non | Axe du principal loft. X = avant/arrière, Y = haut, Z = gauche/droite. `default="Auto"`, `enum=["Auto", "X", "Y", "Z"]` |
| `max_sections` | `integer` | Non | Surcharge : maximum de sections transversales principales. `minimum=2`, `maximum=32` |
| `section_vertices` | `integer` | Non | Surcharge : sommets par section ronde (les sections de boîte utilisent toujours 4). `enum=[4, 6, 8, 12, 16]` |
| `max_primitives` | `integer` | Non | Surcharge : maximum de composants ajustés en plus du corps principal (un couple miroir compte une seule fois). `minimum=0`, `maximum=40` |
| `max_polygon_vertices` | `integer` | Non | Surcharge : nombre maximum de sommets de l'outline d'un polygone extrudé. `minimum=3`, `maximum=12` |
| `grid_resolution` | `integer` | Non | Surcharge : résolution de volume support par axe (RAM augmente avec le cube). `minimum=48`, `maximum=192` |
| `min_part_volume` | `number` | Non | Surcharge : plus petit composant conservé, sous forme de fraction du volume support. `minimum=0.0005`, `maximum=0.2` |
| `unobserved_extent_ratio` | `number` | Non | Lorsqu'aucune image ne limite l'objet le long d'un axe (vue frontale unique, deux vues opposées), sa portée sur cet axe est supposée être cette fraction multipliée par la plus grande dimension observée. Le rapport liste chaque axe supposé. `default=1.0`, `minimum=0.1`, `maximum=4` |
| `body_window` | `number` | Non | Appendices plus courts que cette fraction de l'axe principal sont séparés du corps. `default=0.35`, `minimum=0.1`, `maximum=0.8` |
| `min_gain` | `number` | Non | Optimisation progressive : un section ou composant est conservé seulement si le FitScore améliore de plus de cette quantité. `default=0.004`, `minimum=0`, `maximum=0.2` |
| `split_below` | `number` | Non | Soudure à surface dure : directions et bords de l'outline plus proches que cette valeur d'un axe deviennent exactement parallèles/perpendiculaires (en degrés). 0 désactive. `default=0.5`, `minimum=0`, `maximum=1` |
| `snap_angle` | `number` | Non | Soudure à surface dure : directions et bords de l'outline plus proches que cette valeur d'un axe deviennent exactement parallèles/perpendiculaires (en degrés). 0 désactive. `default=8`, `minimum=0`, `maximum=30` |
| `thin_as_planes` | `boolean` | Non | Représenter des surfaces d'une épaisseur d'un voxel comme des primitives de plan double faces de zéro épaisseur. `default=false` |
| `min_thickness_ratio` | `number` | Non | Plaque la plus mince autorisée, par rapport à son plus grand contour. `default=0.04`, `minimum=0.005`, `maximum=0.5` |
| `refine_passes` | `integer` | Non | PASSES de descente en coordonnées finales de l'affinement de la silhouette. `default=2`, `minimum=0`, `maximum=6` |
| `part_triangle_penalty` | `number` | Non | Pénalité par triangle lors du choix du type de primitive d'un composant. `default=0.0015`, `minimum=0`, `maximum=0.02` |
| `fit_weights` | `object` | Non | Poids du FitScore. Par défaut : silhouette 1.0, profondeur 0.25, bord 0.35, multi-vue 0.4, symétrie 0.15, complexité_primitive 0.004, complexité_triangle 0.002 (par 100 triangles).  |
| `texture_resolution` | `integer` | Non | Taille de l'atlas BaseColor en pixels (carré). `default=1024`, `enum=[256, 512, 1024, 2048, 4096]` |
| `texture_padding` | `integer` | Non | Remplissage de l'atlas xatlas en pixels. `default=4`, `minimum=1`, `maximum=16` |
| `texture_blend` | `string` | Non | best = meilleure caméra par face. blend = mélange multi-vue pondéré des meilleures caméras. `default="best"`, `enum=["best", "blend"]` |
| `blend_views` | `integer` | Non | Les caméras sont mélangées par visage lorsque texture_blend = blend. `default=3`, `minimum=2`, `maximum=6` |
| `visibility_resolution` | `integer` | Non | Taille du buffer profondeur de l'essai d'occlusion. `default=384`, `enum=[256, 384, 512, 768]` |
| `min_facing` | `number` | Non | Une caméra peut texturener un visage uniquement lorsque cos(angle) dépasse cette valeur. `default=0.12`, `minimum=0`, `maximum=0.9` |
| `real_view_bonus` | `number` | Non | Facteur TextureViewScore des images réelles. `default=1.0`, `minimum=0.1`, `maximum=1` |
| `mirrored_view_bonus` | `number` | Non | Facteur TextureViewScore des images réelles miroirées. `default=0.55`, `minimum=0`, `maximum=1` |
| `generated_view_bonus` | `number` | Non | Facteur TextureViewScore des vues synthétiques. `default=0.3`, `minimum=0`, `maximum=1` |
| `target_size` | `number` | Non | Dimension la plus grande de la maille exportée, en unités glTF (mètres). Seules les proportions relatives : aucaille échelle absolue n'est récupérée à partir des images. `default=1.0`, `maximum=10000` |
| `weld_tolerance` | `number` | Non | Distance de collage des sommets de proxy_geometry.obj, relative à target_size. `default=0.0001`, `minimum=0`, `maximum=0.01` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Méta-données texturées fusionnées (binary glTF, face avant +Z, axe vertical +Y). Faces internes supprimées. Entrée pour tout outil de maillage.  |
| `parts_file` | `string` | Oui | Parties séparées : un nœud par primitive, même atlas.  |
| `geometry_file` | `string` | Oui | Géométrie fusionnée uniquement (OBJ, pas de UV).  |
| `texture_file` | `string` | Oui | Atlas de BaseColor (PNG).  |
| `triangles` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `components` | `integer` | Oui | Voir les paramètres de l’opération.  |
| `fit_score` | `number` | Non | Voir les paramètres de l’opération.  |
| `silhouette_agreement` | `number` | Non | Score d'intersection de silhouette pondéré sur toutes les vues.  |
| `report_file` | `string` | Oui | Rapport JSON : vues, poses, couverture, scores, primitives, trace d'optimisation, sources de textures.  |
| `preview_file` | `string` | Oui | Feuille de contact PNG : masque (vert), volume de support (jaune), contour du proxy (rouge) pour chaque vue.  |
| `real_view_count` | `integer` | Non | Voir les paramètres de l’opération.  |
| `generated_view_count` | `integer` | Non | Voir les paramètres de l’opération.  |
| `real_coverage_score` | `number` | Non | Score de couverture réelle, 0..1 sur la sphère de vues.  |
| `expected_reconstruction_confidence` | `number` | Non | 0..1; plafonné à 0,5 pour une seule image.  |
| `symmetry_axis` | `string` | Non | Voir les paramètres de l’opération.  |
| `is_hypothesis` | `boolean` | Non | Vrai lorsque seule une vraie image était disponible.  |
| `missing_views` | `array` | Non | Voir les paramètres de l’opération.  |
| `understanding` | `object` | Non | Modèles et appareil réellement utilisés, mesuré pic de VRAM.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `proxyfit`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation construct_proxy
```
