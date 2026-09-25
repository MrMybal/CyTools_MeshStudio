# CyTools_MeshStudio

Un seul outil pour les maillages : les opérations spécialisées (reconstruction, vues,
remaillage, UV, PBR, rig, mouvement, édition) et les workflows qui les enchaînent.
Il remplace onze Tools, dont les poids ont été **déplacés** ici (49,9 Gio) et le code
archivé dans `runtime/legacy-apps/`.

Maintenance : **Cyberalien**.

## Démarrer

Double-cliquer sur **CyTools_MeshStudio.exe**. L'interface Dear ImGui s'ouvre directement,
sans terminal et sans JSON à éditer. Elle démarre en anglais ; choisir
**Options → Langue → Français** pour la passer en français — toute l'interface est traduite,
infobulles des paramètres comprises.

Sous Linux, `CyTools_MeshStudio.sh` lance la même interface, mais rien n'a été exécuté sur
Linux ici : voir les limites en fin de fichier.

## Les onglets

- **Outils** : les 40 opérations, rangées par usage (Reconstruction, Vues, Topologie, UV,
  Texturation, Édition, Inspection, Rig, Mouvement, Workflow, Maintenance). Chaque opération a
  ses vrais contrôles, ses réglages avancés repliés, le choix du moteur quand il y en a
  plusieurs, la progression réelle, l'annulation et ses résultats.
- **Workflows** : enchaîner ces opérations, choisir ce que chaque étape reçoit de la
  précédente, enregistrer la chaîne et la rejouer sur un fichier ou sur un dossier entier.
- **Installation** : l'état de chaque moteur et de chaque modèle — installé ou non, taille,
  licence, accès restreint — avec les boutons pour installer ou réparer un moteur, **installer
  les poids d'un modèle absent**, et importer un fichier dont la licence s'accepte en personne
  (l'application ne demande jamais les identifiants de ces sites : elle importe le fichier que
  vous avez téléchargé).
- **Mises à jour** : les trois flux (application, moteurs, poids). Pour l'application :
  vérifier une version publiée sur GitHub (dépôt `MrMybal/CyTools_MeshStudio`, déclaré dans
  le manifeste et modifiable dans l'onglet), la préparer, l'activer au prochain démarrage et
  revenir en arrière. Rien n'est remplacé pendant que l'application tourne, et `data/` n'est
  jamais touché.
- **Vue 3D** : le résultat s'y ouvre automatiquement ; caméra orbitale ou libre, scènes et
  éclairages.
- **Journal de l'application**, **Opérations avancées** et **Options** (langue, thème,
  taille du texte, licences, sauvegarde et rechargement de la configuration).

## Ce qui a été réellement exécuté ici

Huit moteurs sont construits ; **dix-huit des vingt backends ont tourné pour de vrai** sur
cette machine (Windows 10, RTX 3090) :

- **géométrie** (CPU) : remaillage quad AutoRemesher et QuadWild Bi-MDF, dépliage et repacking
  UV xatlas, bake PBR, inspection, édition (transformer, recentrer, mettre à l'échelle,
  décimer, lisser, nettoyer), conversion et ajustement de maillage proxy ;
- **CUDA 12.4** : TripoSR (14 s), SPAR3D (47 s, avec son nuage de points) et UniRig
  (squelette + poids de skinning) ;
- **LocalMesh** (modèle TRELLIS.2) : *Image ou photos vers maillage texturé* — une image ou
  quatre photos, puis nettoyage, remaillage, décimation et texture PBR générée pour le
  maillage final. Quatre qualités : `draft`, `standard`, `high`, et `max` (grille 1536,
  400 000 faces, atlas 8K, carte de 24 Go). `draft` a tourné ici, et `high` en quatre vues ;
  `max` jamais. Le workflow
  *Image to high-quality mesh (LocalMesh)* enchaîne le détourage et la qualité `high` ;
  le détourage partagé `Préparer le sujet` prépare les vues une seule fois pour tous les
  backends ;
- **diffusion** : Zero123++, miroir, SAM 2.1, Depth Anything V2, PerspectiveFields ;
- **wonder3d** et **syncdreamer** : génération de vues manquantes ;
- **wham** : inspection vidéo (le moteur est construit et ses poids installés — voir ci-dessous) ;
- les **workflows**, la **CLI**, le **MCP** (62 outils), l'**annulation** et les **mises à jour**.

Preuves et mesures détaillées : **data/reports/VALIDATION.md**.

## LocalMesh+ : une image vers un modèle de production

Deux workflows vont plus loin que LocalMesh seul :

- **Image to production mesh (LocalMesh+)** : détourage → LocalMesh en qualité `high` (le
  modèle détaillé, gardé pour comparer) → allègement à 60 000 faces → quads alignés sur les
  formes par QuadWild → **texture 4K générée par TRELLIS.2 pour ce maillage quad précis**, avec
  une normal map cuite depuis le modèle détaillé. L'OBJ garde les quads ; le GLB est triangulé,
  comme glTF l'impose.
- **Option « refine »** (décochée par défaut, dans la liste des étapes) : TRELLIS.2 régénère
  le détail du modèle LocalMesh sur la grille 1536 en gardant sa forme, avant l'allègement et
  les quads ; la normal map est alors cuite depuis ce modèle raffiné. Elle existe aussi seule :
  *Raffiner un maillage avec TRELLIS.2 (LocalMesh)*, sur n'importe quel maillage aligné.
  Décochée, l'étape laisse passer le modèle LocalMesh tel quel.
- **Image to production mesh with generated views (experimental)** : la même chaîne, mais
  Wonder3D génère d'abord la droite, la gauche et le dos. **Uniquement pour une vue de face bien
  droite** : sur un avion vu de trois quarts par-dessus, les vues générées étaient inclinées et
  la forme fusionnée déformée (les quads et la texture, eux, l'ont suivie à 0,1 % près).

- **Image to production mesh with Hi3DGen** : la même chaîne, avec **Hi3DGen** (Stable-X)
  pour la forme : l'image devient une carte de normales nette (StableNormal YOSO), puis un
  maillage (TRELLIS v1 ré-entraîné sur des normales, grille 256). Cocher « refine » pour en
  régénérer le détail sur la grille 1536 avant les quads et la texture. Hi3DGen existe aussi
  seul : *Image vers maillage (Hi3DGen)*, onglet Outils, catégorie Reconstruction.

Le workflow expérimental a tourné de bout en bout (507 s : Wonder3D, LocalMesh `high` en
quatre vues, QuadWild, texture 4K avec normal map). Les autres n'ont pas encore tourné sur le GPU.

## Les autres workflows fournis

| Workflow | Entrée | Pour quoi |
|---|---|---|
| *Image to quick preview (LocalMesh draft)* | une image | un premier aperçu en une minute environ, avant un long calcul |
| *Image to maximum-quality mesh (LocalMesh max)* | une image | grille 1536, 400 000 faces, atlas 8K ; fermer les autres programmes qui occupent le GPU |
| *Image to game asset (LocalMesh, AutoRemesher)* | une image | environ 4 000 quads, texture 2K et normal map, prêt pour Unity, Unreal ou Godot |
| *Image to rigged character (LocalMesh, UniRig)* | une image | le même asset avec environ 6 000 quads, puis squelette et skinning UniRig |
| *Image to 3D print (STL)* | une image | plus grande pièce, trous fermés, Z vers le haut, 100 mm de haut, STL |
| *Compare the shape engines on one image* | une image | le même détourage donné à TripoSR, SPAR3D, Hi3DGen et LocalMesh ; un moteur en échec n'arrête pas les autres |
| *Four photos to production mesh (LocalMesh+)* | un dossier de quatre photos | la chaîne de production, à partir de vraies photos des quatre côtés |
| *Photos to textured mesh* | un dossier de quatre photos | LocalMesh `high` en quatre vues |
| *Mesh to game asset* | un maillage texturé | environ 4 000 quads, sa propre texture reportée dessus |
| *Retopologise a textured mesh (QuadWild, texture kept)* | un maillage texturé | quads QuadWild, sa propre texture reportée dessus, normal map depuis l'original |

**Quatre photos d'un même sujet** : les mettre seules dans un dossier, nommées d'après leur côté
(`statue-front.jpg`, `statue-droite.jpg`, `statue-gauche.jpg`, `statue-dos.jpg` ; `face`,
`right`, `left`, `back` marchent aussi), puis choisir ce dossier dans **Entrée › Dossier**. Ces
workflows prennent les fichiers du dossier *ensemble* (réglage **Fichiers du dossier**, enregistré
avec le workflow) ; les autres font une exécution par fichier.

Pour lancer : onglet **Workflows** → choisir le workflow → **Entrée › Fichier** : ton image →
**Exécuter le workflow**. Compter plusieurs minutes de carte pleine (LocalMesh `high`, puis
QuadWild sur le CPU, puis la texture). Les résultats sont dans le dossier du job, une étape par
sous-dossier numéroté par sa place dans le workflow : `2-shape` (le résultat LocalMesh
seul), `3-refine` (si l'option est cochée) et `6-texture` (`textured.glb`, `textured.obj`, les
cartes et `texture-report.json`).

## Ce qui manque encore, et pourquoi

- **WHAM n'a jamais produit de mouvement ici.** Ses cinq checkpoints (6,07 Gio) sont
  téléchargés et vérifiés, mais le modèle corporel `SMPL_NEUTRAL.pkl` demande une inscription
  personnelle sur <https://smplify.is.tue.mpg.de>. L'onglet Installation affiche la page à
  visiter et un bouton *Importer le fichier...* ; tant qu'il manque, `video_to_motion` refuse
  en nommant le fichier au lieu d'échouer au milieu du chargement.
- **Aucune version publiée sur GitHub n'existe encore.** Le dépôt
  `github.com/MrMybal/CyTools_MeshStudio` est déclaré dans le manifeste et l'onglet Mises à
  jour l'interroge pour de vrai : il répond aujourd'hui qu'aucune release n'est publiée — le
  dépôt est encore privé, ce qu'une requête anonyme ne distingue pas d'un dépôt sans release,
  et tant qu'il le reste l'application ne pourra pas y lire ses mises à jour. Le mécanisme
  lui-même est implémenté et testé (28 vérifications sur un arbre jetable, puis préparation,
  activation, échange au démarrage et retour en arrière sur cette installation même).
- **Linux et macOS** : rien n'a été exécuté.
- La génération de forme de LocalMesh reste d'un seul tenant (le code amont tient son état
  GPU d'un bout à l'autre) ; la **texture**, elle, se refait désormais à part, sur n'importe
  quel maillage aligné, avec *Texturer un maillage pour sa propre topologie*.

## Ligne de commande et MCP

```bash
runtime/python/Scripts/python.exe app/tool.py create-client --name "Moi" --permission filesystemExternal --permission network
```

Mettre le jeton dans `CYTOOLS_TOKEN`, puis par exemple :

```bash
runtime/python/Scripts/python.exe app/tool.py invoke diagnose --params "{}"
```

Installer un moteur, puis les poids d'un modèle :

```bash
runtime/python/Scripts/python.exe app/setup_engine.py wham
```

```bash
runtime/python/Scripts/python.exe app/tool.py invoke install_model --params "{\"model\":\"wham\"}" --timeout 7200
```

## Organisation

- `app/` : code, manifeste, interface, workers, scripts, tests, documentation développeur.
- `data/` : entrées, modèles, jobs, réglages, journaux, workflows, rapports.
- `runtime/` : Python privé, moteurs, sources amont, binaires natifs, mises à jour préparées,
  sauvegardes, archives.

Les modèles occupent 60,7 Gio dans `data/models`. Aucune mise à jour ne remplace `data/`.
Plusieurs poids sont sous licence non commerciale (Zero123++, Wonder3D, SyncDreamer,
PerspectiveFields, WHAM) et DINOv3 comme SMPL demandent une acceptation personnelle sur leur
page officielle ; l'onglet Installation le signale pour chaque modèle.

## Tests

```bash
runtime/python/Scripts/python.exe app/test_tool.py
```

```bash
runtime/python/Scripts/python.exe app/tests/test_updates.py
```

```bash
runtime/python/Scripts/python.exe app/tests/validate_forms.py
```

`app/desktop.py --ui-test-interactions` rejoue le parcours à la souris (45 vérifications, en
anglais et en français) ; `app/tests/test_workflow_inputs.py` exécute chaque workflow enregistré
avec des substituts à la place des modèles, étapes validées contre le manifeste (80
vérifications), et `runtime/engines/trellis/Scripts/python.exe app/tests/test_quadtex.py`
le dépliage qui garde les quads ; `app/tests/validate_mcp.py` et `app/tests/validate_cancel.py`
couvrent le MCP et l'annulation. Ne pas lancer deux d'entre eux en même temps : un seul
runtime possède le dossier `data/`.

Guide technique : `app/README.md`, `app/Docs/Architecture.md` et `app/Docs/Workflow.md`.

## Licence

Copyright (C) 2026 Cyberalien.

CyTools_MeshStudio est distribué sous la **GNU General Public License, version 3 uniquement**
(`GPL-3.0-only`). Voir le texte complet dans [LICENSE](LICENSE). Il repose sur le SDK
[CyToolsCore](https://github.com/MrMybal/CyToolsCore), sous la même licence.

Vous pouvez redistribuer et modifier ce programme selon les termes de cette licence. Il est
fourni sans aucune garantie, notamment sans garantie de qualité marchande ou d'adéquation à
un usage particulier. Les moteurs, programmes natifs, dépendances et poids de modèles
installés par l'application conservent leurs licences respectives, dont plusieurs sont non
commerciales : la liste est dans `app/Docs/ThirdPartyNotices.md` et dans l'onglet Options.
