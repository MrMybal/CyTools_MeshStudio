---
id: guide-lisez-moi
title: Guide d’utilisation
description: Utilisez l’application étape par étape.
section: Guide
order: 10
parent: overview
sourceRevision: 11ce39d4095d0a37
---

## CyTools_MeshStudio {#cytools-meshstudio}

MeshStudio réunit la reconstruction, la génération de vues, le remeshing, les UV, les textures PBR, le rigging, le mouvement, l’édition et l’inspection. Les workflows enchaînent ces opérations sur une entrée ou un dossier.

## Démarrer {#demarrer}

Double-cliquer sur **CyTools_MeshStudio.exe**. L'interface Dear ImGui s'ouvre directement, sans terminal et sans JSON à éditer. Elle démarre en anglais ; choisir **Options → Langue → Français** pour la passer en français — toute l'interface est traduite, infobulles des paramètres comprises.

Depuis la release GitHub : décompresser `CyTools_MeshStudio-<version>-windows-x64.zip` dans un dossier au chemin court (QuadWild échoue au-delà d'environ 240 caractères de chemin, et l'outil le dit au lieu de le lancer), puis double-cliquer sur l'exécutable. Rien n'est à installer : l'archive contient l'application, un Python 3.12 embarqué avec ses paquets, `uv` et les deux programmes natifs du moteur géométrie. Les moteurs et les poids, eux, se construisent et se téléchargent depuis l'onglet **Installation** (plusieurs dizaines de Go au total).

Sous Linux, `CyTools_MeshStudio.sh` lance la même interface, mais rien n'a été exécuté sur Linux ici : voir les limites en fin de fichier.

## Les pages {#les-pages}

Depuis la 0.1.2, les pages s'ouvrent depuis la barre latérale, en deux groupes : « Espace de travail » (Outils, Workflows, Vue 3D) et « Système » (Installation, Mises à jour, Journal, Opérations avancées, Options). La barre d'état, en bas, montre la tâche en cours ou la dernière erreur. Les listes d'outils, de workflows et de modèles ont un champ de recherche.

- **Outils** : les 40 opérations, rangées par usage (Reconstruction, Vues, Topologie, UV, Texturation, Édition, Inspection, Rig, Mouvement, Workflow, Maintenance). Chaque opération a ses vrais contrôles, ses réglages avancés repliés, le choix du moteur quand il y en a plusieurs, la progression réelle, l'annulation et ses résultats.
- **Workflows** : enchaîner ces opérations, choisir ce que chaque étape reçoit de la précédente, enregistrer la chaîne et la rejouer sur un fichier ou sur un dossier entier.
- **Installation** : l'état de chaque moteur et de chaque modèle — installé ou non, taille, licence, accès restreint — avec les boutons pour installer ou réparer un moteur, **installer les poids d'un modèle absent**, et importer un fichier dont la licence s'accepte en personne (l'application ne demande jamais les identifiants de ces sites : elle importe le fichier que vous avez téléchargé).
- **Mises à jour** : les trois flux (application, moteurs, poids). Pour l'application : vérifier une version publiée sur GitHub (dépôt `MrMybal/CyTools_MeshStudio`, déclaré dans le manifeste et modifiable dans l'onglet), la préparer, l'activer au prochain démarrage et revenir en arrière. Rien n'est remplacé pendant que l'application tourne, et `data/` n'est jamais touché.
- **Vue 3D** : le résultat s'y ouvre automatiquement ; caméra orbitale ou libre, scènes et éclairages.
- **Journal de l'application**, **Opérations avancées** et **Options** (langue, thème parmi les cinq de CyUI, densité compacte ou confortable, taille du texte, licences, sauvegarde et rechargement de la configuration).

## LocalMesh+ : une image vers un modèle de production {#localmesh-une-image-vers-un-modele-de-production}

Deux workflows vont plus loin que LocalMesh seul :

- **Image to production mesh (LocalMesh+)** : détourage → LocalMesh en qualité `high` (le modèle détaillé, gardé pour comparer) → allègement à 60 000 faces → quads alignés sur les formes par QuadWild → **texture 4K générée par TRELLIS.2 pour ce maillage quad précis**, avec une normal map cuite depuis le modèle détaillé. L'OBJ garde les quads ; le GLB est triangulé, comme glTF l'impose.
- **Option « refine »** (décochée par défaut, dans la liste des étapes) : TRELLIS.2 régénère le détail du modèle LocalMesh sur la grille 1536 en gardant sa forme, avant l'allègement et les quads ; la normal map est alors cuite depuis ce modèle raffiné. Elle existe aussi seule : *Raffiner un maillage avec TRELLIS.2 (LocalMesh)*, sur n'importe quel maillage aligné. Décochée, l'étape laisse passer le modèle LocalMesh tel quel.
- **Image to production mesh with generated views (experimental)** : la même chaîne, mais Wonder3D génère d'abord la droite, la gauche et le dos. **Uniquement pour une vue de face bien droite** : sur un avion vu de trois quarts par-dessus, les vues générées étaient inclinées et la forme fusionnée déformée (les quads et la texture, eux, l'ont suivie à 0,1 % près).

- **Image to production mesh with Hi3DGen** : la même chaîne, avec **Hi3DGen** (Stable-X) pour la forme : l'image devient une carte de normales nette (StableNormal YOSO), puis un maillage (TRELLIS v1 ré-entraîné sur des normales, grille 256). Cocher « refine » pour en régénérer le détail sur la grille 1536 avant les quads et la texture. Hi3DGen existe aussi seul : *Image vers maillage (Hi3DGen)*, onglet Outils, catégorie Reconstruction.


## Les autres workflows fournis {#les-autres-workflows-fournis}

| Workflow | Entrée | Pour quoi |
|---|---|---|
| *Image to quick preview (LocalMesh draft)* | une image | un premier aperçu en une minute environ, avant un long calcul |
| *Image to maximum-quality mesh (LocalMesh max)* | une image | grille 1536, 400 000 faces, atlas 8K ; fermer les autres programmes qui occupent le GPU |
| *Image to game asset (LocalMesh, AutoRemesher)* | une image | environ 4 000 quads, texture 2K et normal map, prêt pour Unity, Unreal ou Godot |
| *Image to rigged character (LocalMesh, UniRig)* | une image | le même asset avec environ 6 000 quads, puis squelette et skinning UniRig |
| *Image to 3D print (STL)* | une image | plus grande pièce, trous fermés, Z vers le haut, 100 mm de haut, STL |
| Comparer les moteurs de forme sur une image | une image | le même détourage donné à TripoSR, SPAR3D, Hi3DGen et LocalMesh ; un moteur en échec n'arrête pas les autres |
| *Four photos to production mesh (LocalMesh+)* | un dossier de quatre photos | la chaîne de production, à partir de vraies photos des quatre côtés |
| *Photos to textured mesh* | un dossier de quatre photos | LocalMesh `high` en quatre vues |
| *Mesh to game asset* | un maillage texturé | environ 4 000 quads, sa propre texture reportée dessus |
| *Retopologise a textured mesh (QuadWild, texture kept)* | un maillage texturé | quads QuadWild, sa propre texture reportée dessus, normal map depuis l'original |

**Quatre photos d'un même sujet** : les mettre seules dans un dossier, nommées d'après leur côté (`statue-front.jpg`, `statue-droite.jpg`, `statue-gauche.jpg`, `statue-dos.jpg` ; `face`, `right`, `left`, `back` marchent aussi), puis choisir ce dossier dans **Entrée › Dossier**. Ces workflows prennent les fichiers du dossier *ensemble* (réglage **Fichiers du dossier**, enregistré avec le workflow) ; les autres font une exécution par fichier.

Pour lancer : onglet **Workflows** → choisir le workflow → **Entrée › Fichier** : ton image → **Exécuter le workflow**. Compter plusieurs minutes de carte pleine (LocalMesh `high`, puis QuadWild sur le CPU, puis la texture). Les résultats sont dans le dossier du job, une étape par sous-dossier numéroté par sa place dans le workflow : `2-shape` (le résultat LocalMesh seul), `3-refine` (si l'option est cochée) et `6-texture` (`textured.glb`, `textured.obj`, les cartes et `texture-report.json`).
