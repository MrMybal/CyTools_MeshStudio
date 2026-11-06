---
id: guide-app-docs-workflow
title: Flux de travail
description: Flux de travail
section: Guide
order: 40
parent: guide-lisez-moi
sourceRevision: 244f573d6f90188b
---

## Flux de travail {#workflows}

Un workflow est une chaîne d'opérations de cette Outil, stockée sous le nom JSON dans `data/workflows` et exécutée de la même manière depuis l'interface, le CLI et le MCP. C'est des données, pas du code : `run_workflow` lit le document et appelle les mêmes gestionnaires un par un, comme le ferait un client.

Cette page enregistre également ce que l'LocalMesh chaîne de traitement nous a appris, car la première chaîne de traitement réelle de cette Outil est cette chaîne de traitement, qui a été ouverte.

## L'interface frontale partagée {#the-shared-front-end}

Quatre des outils absorbés portaient leur propre débarraseur de fond (BiRefNet, u2net, transparent-background, SAM 2.1) et trois estimaient la caméra différemment (Depth Anything 3, DINOv2 + SAM 2.1, PerspectiveFields). `prepare_subject` le fait une seule fois et écrit un ensemble de sujets :

```
outputs/subject/
  front.png right.png left.png back.png   cut-outs, one common scale
  contact.png                             contact sheet
  subject.json                            what was measured
```

`subject.json` transporte, par vue, sa source, sa taille, la géométrie de la composition et son azimut mesuré lorsque la mesure a été acceptée ; et, pour l'ensemble, le rapport de la caméra avec `refusedBecause` lorsque ce n'était pas le cas. Un pas de reconstruction consomme le dossier jusqu'à `subject_set`, de sorte que le sujet est segmenté une seule fois pour toute la workflow.

La refusée est exposée plutôt que silencieusement avalée : "la vue arrière mesure 32,7 degrés d'inclinaison, au-delà du seuil des 30 degrés" informe l'artiste de refaire la prise de vue au niveau de l'œil, où seules les "angles ronds utilisés" ne suffiraient pas.

## Alimentation d'un pas provenant d'un autre {#feeding-a-step-from-another}

Étape où l'on indique ses entrées :

* `input_from` — le pas dont il lit la sortie (vide : le pas précédent, ou l'entrée du workflow pour le premier pas).
* `input_field` — quel champ de sortie de cette étape prendre (vide : la sortie principale de la maille).
* `input_to` — quel paramètre de cette étape le reçoit-il (vide : le champ que l'opération lit normalement pour son entrée). C'est ce qui permet à une étape de consommer un dossier préparé au lieu d'un fichier maillage.

```json
{"id": "mesh", "operation": "photos_to_mesh",
 "input_from": "subject", "input_field": "subject_set", "input_to": "subject_set"}
```

Une étape qui a besoin de plus d'une chose liste les autres dans `extra_inputs` (`{"from": "shape", "field": "file", "to": "detail_mesh"}`) ; `"from": "@input"` nomme le fichier sur lequel le workflow a été lancé, qui est comment une retopologie récupère sa texture originale.

Les paramètres de chaque étape sont validés contre le schéma de l'opération, et complétés avec ses valeurs par défaut, avant que l'étape ne s'exécute — exactement comme un travail soumis à lui-même. Un paramètre mal orthographié échoue à l'étape qui le transporte, en nommant celui-ci, au lieu de se produire à l'intérieur d'un worker après les étapes précédentes ont été payées.

## Ce qu'un dossier signifie : `input_mode` {#what-a-folder-means-input-mode}

`each` (par défaut) exécute toute la chaîne une fois par fichier du dossier : un lot de maillages. Pour quatre photographies d'une statue, c'est faux — chacune deviendrait son propre sujet, et le mode à quatre vues ne verrait jamais quatre vues. `together` exécute la chaîne une fois, et la première étape reçoit chaque fichier comme une liste. `prepare_subject` donne ensuite à chaque photographie son rôle de son nom de fichier (`front`, `right`, `left`, `back`, ou `face`, `droite`, `gauche`, `dos` ; les accents sont ignorés) ; une photographie sans rôle devient la face avant si aucune n'est présente. Le mode est enregistré dans le document et affiché sous l'entrée dans l'éditeur ; `run_workflow` peut l'override.

## Quand une étape échoue : `continue_on_error` {#when-a-step-fails-continue-on-error}

Sans lui, une étape échouée arrête le workflow. Avec lui, l'échec est listé dans le rapport et enregistré comme un avertissement, et l'étape transmet ce qu'elle a reçu — exactement comme elle le fait quand elle est désactivée — de sorte que la chaîne continue. La comparaison des moteurs en dépend (un moteur échouant laisse les autres), et c'est aussi le cas pour Maillage vers actif de jeu : un entrée sans texture UV pour transférer obtient toujours sa maillage quadrilatère.

## Les workflows fournis dans `data/workflows` {#the-workflows-shipped-in-data-workflows}

| Workflow | Entrée | Chaîne |
|---|---|---|
| Image pour aperçu rapide (brouillon LocalMesh) | image | coupé, brouillon LocalMesh |
| Image pour maillage de haute qualité (LocalMesh) | image | coupé, LocalMesh de haute qualité |
| Image en maillage de qualité maximale (LocalMesh max) | image | coupé, LocalMesh max (1536 mailles, 24 GB carte) |
| Image en maillage de production (LocalMesh+) | image | coupé, LocalMesh haute, [affiner], 60 000 faces, QuadWild, texture 4K + carte normale |
| Image en maillage de production avec Hi3DGen | image | la même chose avec Hi3DGen pour la forme |
| Image en maillage de production avec vues générées (expérimental) | niveau vue avant | Vue Wonder3D, LocalMesh quatre vues, puis les mêmes |
| Quatre photos vers la mesh de production (LocalMesh+) | dossier, ensemble | Quatre photos, LocalMesh quatre vues, [refine], QuadWild, texture à partir des quatre photos |
| Photos vers mesh texturée | dossier, ensemble | Quatre photos, LocalMesh quatre vues |
| Image vers actif de jeu (LocalMesh, AutoRemesher) | image | LocalMesh haute, 20 000 faces, ~4 000 quads, 2K texture + map normale |
| Image vers personnage riggé (LocalMesh, UniRig) | image | l'actif du jeu avec environ 6 000 quadrilatères, puis UniRig |
| Image pour impression 3D (STL) | image | LocalMesh haut, partie la plus grande, trous, normales, Z-up, 100 mm, STL |
| Comparer les moteurs de forme sur une image | image | une découpe vers TripoSR, SPAR3D, Hi3DGen et LocalMesh |
| Maillage vers actif du jeu | maillage texturé | 20 000-face OBJ, ~4 000 quads, sa texture transférée en arrière |
| Retopologisez un maillage texturé (QuadWild, sa texture conservée) | maillage texturé | 60 000 faces, QuadWild, sa texture transférée en arrière |

## Ressources {#resources}

Les étapes d'un workflow s'exécutent à l'intérieur du job qui les a lancés, une après l'autre, donc le job réserve le maximum de ses étapes plutôt que leur somme (`runner.estimate`). Une étape qui nécessite plus de ce que le job a réservé est signalée par le programmeur avant que rien ne commence.
