# CyTools MeshStudio — notes de version

[English](VERSION.md) · [README](README.fr.md)

## Application publiée

**0.1.4 · EXPÉRIMENTAL · Windows x64**

Il s’agit de la version de l’application, pas de son SDK ni de sa bibliothèque d’interface. Cette release expérimentale est destinée à l’évaluation.

- [Release publiée et sommes de contrôle](https://github.com/MrMybal/CyTools_MeshStudio/releases/tag/v0.1.4)
- [Téléchargement Windows portable](https://github.com/MrMybal/CyTools_MeshStudio/releases/download/v0.1.4/CyTools_MeshStudio-0.1.4-windows-x64.zip)

## Changements de cette release binaire

- Manuel CyDoc complet en anglais et français : navigation, recherche, aide contextuelle et médias pertinents.
- Lecteur hors ligne et contrats natifs existants conservés.
- ABI Python et prérequis des moteurs/modèles inchangés depuis la release applicative précédente.

La vitrine, la présentation du README et la navigation du dépôt ont été ajoutées après cette release binaire. Elles n’annoncent pas un nouvel exécutable et n’impliquent pas que des changements sources ultérieurs sont dans le ZIP.

## Versions des composants

| Composant | Version | Rôle |
| --- | --- | --- |
| CyTools MeshStudio | 0.1.4 | Application |
| CyToolsCore | 0.10.1 | SDK / runtime |
| CyUI | 1.2.0 | Modules d’interface sélectionnés |
| CyDoc | 0.1.0 | Lecteur inclus |

## Limites documentées

Expérimental, testé sous Windows avec du matériel NVIDIA. Linux n’est pas validé. Tous les moteurs installés n’ont pas été exécutés de bout en bout : l’inférence GPU Hi3DGen, certains parcours LocalMesh+ et le raffinement haute résolution restent à valider. WHAM nécessite les fichiers SMPL sous licence distincte. Les licences et accès varient selon le modèle.

Moteurs et poids s’installent séparément. Une opération déclarée ou un modèle téléchargeable ne prouve pas la validation de toutes les combinaisons de paramètres, matériels ou modèles. Conservez les licences de la release installée.

## Signalements et mises à jour

Les notes actuelles ne publient pas de liste de tickets bug par bug. Consultez le suivi des problèmes pour les signalements confirmés ; les limites ci-dessus concernent les plateformes et composants facultatifs.

- [Suivi des problèmes](https://github.com/MrMybal/CyTools_MeshStudio/issues)
- [Toutes les releases](https://github.com/MrMybal/CyTools_MeshStudio/releases)

Pour une installation compatible, utilisez son flux de mise à jour et préservez données/modèles. Un changement d’ABI nécessite la distribution complète correspondante ; ne forcez pas une mise à jour applicative incompatible.
