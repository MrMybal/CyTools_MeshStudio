"""Merge the French translations of this Tool into app/locales/ui.json, and report the gaps.

    python app/scripts/update_locales.py            # merge and report
    python app/scripts/update_locales.py --check    # only report what is missing

``ui_common`` reads one catalogue, ``locales/ui.json``, which the scaffold ships already
filled for the façade. The strings of this Tool live here so they can be regenerated and
audited: the script collects every string the interface can show — the tabs and panel labels
written below, the operation names and descriptions of the manifest, and the field labels the
parameter editor derives from the schema — then reports which ones have no French yet.
"""
import argparse
import json
from pathlib import Path
import re
import sys

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

APP = Path(__file__).resolve().parents[1]
CATALOG = APP / 'locales' / 'ui.json'
MANIFEST = APP / 'CyTool.json'

# ----------------------------------------------------------------- panel and tab strings
INTERFACE = {
    'Tools': 'Outils',
    'Workflows': 'Workflows',
    'Installation': 'Installation',
    'Updates': 'Mises à jour',
    # categories
    'Reconstruction': 'Reconstruction',
    'Views': 'Vues',
    'Topology': 'Topologie',
    'UV': 'UV',
    'Texturing': 'Texturation',
    'Editing': 'Édition',
    'Inspection': 'Inspection',
    'Rigging': 'Rig',
    'Motion': 'Mouvement',
    'Maintenance': 'Maintenance',
    'Other': 'Autre',
    # tools panel
    'No operation available.': 'Aucune opération disponible.',
    'Ported from': 'Repris de',
    'Backend': 'Moteur',
    'Run': 'Exécuter',
    'Reset': 'Réinitialiser',
    'Cancel': 'Annuler',
    'Result': 'Résultat',
    'Output': 'Sortie',
    'Value': 'Valeur',
    'Open in the 3D view': 'Ouvrir dans la vue 3D',
    'Open the folder': 'Ouvrir le dossier',
    'Advanced settings': 'Paramètres avancés',
    'Browse': 'Parcourir',
    'Clear': 'Vider',
    'Add': 'Ajouter',
    'Add files': 'Ajouter des fichiers',
    'Add empty': 'Ajouter une entrée vide',
    'Entry': 'Entrée',
    'Choose': 'Choisir',
    'Choose files': 'Choisir des fichiers',
    'This backend is not available in this build yet': "Ce moteur n'est pas encore disponible dans cette version",
    'The engine': 'Le moteur',
    'is not installed. Open the Installation tab.': "n'est pas installé. Ouvrir l'onglet Installation.",
    # workflow panel
    'Saved workflows': 'Workflows enregistrés',
    'Refresh': 'Actualiser',
    'New': 'Nouveau',
    'Name': 'Nom',
    'Description': 'Description',
    'Steps': 'Étapes',
    'Add step': 'Ajouter une étape',
    'Remove': 'Retirer',
    'Enabled': 'Activée',
    'Random': 'Aléatoire',
    'Input': 'Entrée',
    'File': 'Fichier',
    'Folder': 'Dossier',
    'Pattern': 'Motif',
    'Run the workflow': 'Exécuter le workflow',
    'Files of the folder': 'Fichiers du dossier',
    'One run per file': 'Une exécution par fichier',
    'All files together, as the views of one subject':
        "Tous les fichiers ensemble, comme les vues d'un même sujet",
    'Save': 'Enregistrer',
    'Saved to': 'Enregistré dans',
    'Workflow finished': 'Workflow terminé',
    'output(s)': 'sortie(s)',
    'Input from': 'Entrée depuis',
    'Previous step': 'Étape précédente',
    'Output field': 'Champ de sortie',
    'Main output': 'Sortie principale',
    'Receives it in': 'Reçue dans',
    'Default input': 'Entrée par défaut',
    'Choose the input': "Choisir l'entrée",
    'Choose a folder': 'Choisir un dossier',
    # installation panel
    'State comes from diagnose, the same report the CLI prints.':
        "L'état vient de diagnose, le même rapport que celui de la CLI.",
    'Engines': 'Moteurs',
    'Backends': 'Moteurs de calcul',
    'Models': 'Modèles',
    'Engine': 'Moteur',
    'State': 'État',
    'Runtime': 'Exécution',
    'Size': 'Taille',
    'Device': 'Périphérique',
    'Reinstall even if installed': 'Réinstaller même si déjà installé',
    'Install': 'Installer',
    'Repair': 'Réparer',
    'installing': 'installation en cours',
    'Cancel the installation': "Annuler l'installation",
    'Ready': 'Prêt',
    'Missing': 'Manquant',
    'yes': 'oui',
    'no': 'non',
    'worker not ported': 'worker non porté',
    'engine': 'moteur',
    'Family': 'Famille',
    'Model': 'Modèle',
    'Licence': 'Licence',
    'Revision': 'Révision',
    'unknown': 'inconnue',
    'non-commercial': 'non commercial',
    'gated': 'accès restreint',
    'Resume': 'Reprendre',
    'downloading': 'téléchargement en cours',
    'manual': 'manuel',
    'Cancel the download': 'Annuler le téléchargement',
    'This model came with the absorbed Tools; its download is not described here.':
        "Ce modèle provient des outils absorbés ; son téléchargement n'est pas décrit ici.",
    'Files to accept and download yourself':
        'Fichiers à accepter et télécharger vous-même',
    'Copy the address': "Copier l'adresse",
    'Import the file...': 'Importer le fichier...',
    'Choose the file downloaded from the official page':
        'Choisir le fichier téléchargé depuis la page officielle',
    'Accepted files': 'Fichiers acceptés',
    # updates panel
    'The application, the engines and the model weights are three separate streams. '
    'They have their own versions and their own licences, and an update never replaces '
    'the data folder.':
        "L'application, les moteurs et les poids des modèles sont trois flux distincts. "
        "Ils ont leurs propres versions et leurs propres licences, et une mise à jour ne "
        "remplace jamais le dossier data.",
    'Application': 'Application',
    'GitHub repository (owner/name)': 'Dépôt GitHub (propriétaire/nom)',
    'Check automatically at start': 'Vérifier automatiquement au démarrage',
    'No repository configured for this Tool yet.':
        "Aucun dépôt configuré pour cet outil pour l'instant.",
    'Each engine pins the upstream revision it was built against, in app/engines.json. '
    'Reinstalling an engine from the Installation tab checks out that exact revision.':
        "Chaque moteur épingle la révision amont contre laquelle il a été construit, dans "
        "app/engines.json. Réinstaller un moteur depuis l'onglet Installation récupère "
        "exactement cette révision.",
    'version': 'version',
    'Check for an update': 'Vérifier les mises à jour',
    'Release available': 'Version disponible',
    'Latest release': 'Dernière version publiée',
    'Stage this release': 'Préparer cette version',
    'Release archive (URL or local .zip)': 'Archive de version (URL ou .zip local)',
    'Choose a file...': 'Choisir un fichier...',
    'Choose the release archive': "Choisir l'archive de la version",
    'Expected SHA-256 (optional)': 'SHA-256 attendu (facultatif)',
    'Stage': 'Préparer',
    'Staging only unpacks and verifies; nothing is replaced.':
        'La préparation ne fait que décompresser et vérifier ; rien n\'est remplacé.',
    'Staged, waiting for your decision': 'Préparé, en attente de votre décision',
    'files': 'fichiers',
    'staged on': 'préparé le',
    'Activate at next start': 'Activer au prochain démarrage',
    'Waiting for a restart': 'En attente d\'un redémarrage',
    'Cancel this change': 'Annuler ce changement',
    'Last applied': 'Dernière application',
    'Backups kept': 'Sauvegardes conservées',
    'Restore this one at next start': 'Restaurer celle-ci au prochain démarrage',
    'Recorded. Close and reopen the application to apply it.':
        "Enregistré. Fermer et rouvrir l'application pour l'appliquer.",
    'Open the Installation tab': "Ouvrir l'onglet Installation",
    'installed': 'installé',
    'not installed': 'non installé',
    'can be installed': 'peut être installé',
    'Model weights': 'Poids des modèles',
    'Weights follow their own catalogue (app/models/catalog.json) with their revision and '
    'their licence; see the Installation tab.':
        "Les poids suivent leur propre catalogue (app/models/catalog.json), avec leur "
        "révision et leur licence ; voir l'onglet Installation.",
    'Not implemented yet: checking a release, staging it under runtime/updates, verifying '
    'it, activating it at restart and rolling back. Until it is, update the Tool by '
    'replacing the app folder yourself; data/ is never part of a replacement.':
        "Pas encore implémenté : vérifier une release, la préparer dans runtime/updates, la "
        "contrôler, l'activer au redémarrage et la restaurer. En attendant, mettre l'outil à "
        "jour en remplaçant soi-même le dossier app ; data/ n'est jamais remplacé.",
}

# The CyUI pages: navigation, search fields, empty states, badges and toasts.
INTERFACE.update({
    'WORKSPACE': 'ESPACE DE TRAVAIL',
    'SYSTEM': 'SYSTÈME',
    'Navigation': 'Navigation',
    'Options': 'Options',
    'Interface': 'Interface',
    'Density': 'Densité',
    'Compact': 'Compacte',
    'Comfortable': 'Confortable',
    'Compact fits more on screen; comfortable gives every control more room.':
        "Compacte affiche plus de choses à l'écran ; confortable donne plus de place à chaque contrôle.",
    'The CyUI look: one palette for every panel, one accent for what is active.':
        "L'apparence CyUI : une palette pour tous les panneaux, une couleur d'accent pour ce qui est actif.",
    'Mid grey (CyDAW)': 'Gris moyen (CyDAW)',
    'Light grey (CyDAW)': 'Gris clair (CyDAW)',
    'Amber night (CyDAW)': 'Nuit ambrée (CyDAW)',
    'Violet (Shaderixel)': 'Violet (Shaderixel)',
    'Navy (CyEngineHub)': 'Bleu marine (CyEngineHub)',
    'Search operations': 'Rechercher une opération',
    'Search workflows': 'Rechercher un workflow',
    'Search models': 'Rechercher un modèle',
    'No operation matches': 'Aucune opération ne correspond',
    'Change or clear the search.': 'Modifier ou vider la recherche.',
    'This operation takes no parameter.': "Cette opération ne prend aucun paramètre.",
    'The engine that runs this operation; each has its own models.':
        'Le moteur qui exécute cette opération ; chacun a ses propres modèles.',
    'Every parameter back to its default': 'Remettre chaque paramètre à sa valeur par défaut',
    'No file chosen': 'Aucun fichier choisi',
    'No folder chosen': 'Aucun dossier choisi',
    'Copied to the clipboard': 'Copié dans le presse-papiers',
    'Log copied to the clipboard': 'Journal copié dans le presse-papiers',
    'Address copied to the clipboard': 'Adresse copiée dans le presse-papiers',
    'Runtime unavailable': 'Runtime indisponible',
    'Submitted': 'Envoyé :',
    'failed': 'a échoué',
    'cancelled': 'annulé',
    'entries': 'entrées',
    'file(s)': 'fichier(s)',
    'step(s)': 'étape(s)',
    # workflows
    'SAVED WORKFLOWS': 'WORKFLOWS ENREGISTRÉS',
    'New workflow': 'Nouveau workflow',
    'No workflow saved yet': 'Aucun workflow enregistré',
    'No workflow found': 'Aucun workflow trouvé',
    'Build one on the right, then save it.': "Composez-en un à droite, puis enregistrez-le.",
    'No step yet: choose an operation above and press Add step.':
        'Aucune étape : choisissez une opération ci-dessus et appuyez sur Ajouter une étape.',
    'The operation the new step runs': "L'opération exécutée par la nouvelle étape",
    'The step whose output this one reads.': "L'étape dont celle-ci lit la sortie.",
    'Move up': 'Monter',
    'Move down': 'Descendre',
    'SKIPPED': 'IGNORÉE',
    'One file to run the workflow on.': 'Un fichier sur lequel exécuter le workflow.',
    'Every matching file of a folder, instead of one file.':
        "Tous les fichiers correspondants d'un dossier, au lieu d'un seul fichier.",
    'Workflow saved': 'Workflow enregistré',
    # installation and updates
    'engines installed': 'moteurs installés',
    'models installed': 'modèles installés',
    'All families': 'Toutes les familles',
    'No model matches this family and search.': 'Aucun modèle ne correspond à cette famille et à cette recherche.',
    'NEW': 'NOUVEAU',
    'NON-COMMERCIAL': 'NON COMMERCIAL',
    'ACCEPTANCE': 'ACCEPTATION',
    'Its licence is accepted in person on its official page.':
        "Sa licence s'accepte en personne sur sa page officielle.",
    'Which PyTorch build an engine gets: auto picks CUDA when an NVIDIA card is present.':
        "La version de PyTorch installée pour un moteur : auto choisit CUDA quand une carte NVIDIA est présente.",
    'Stage a release by hand': 'Préparer une release à la main',
    'Where the releases are read from; the manifest declares it.':
        "D'où les releases sont lues ; le manifeste le déclare.",
    # 3D view
    'Not installed': 'Non installé',
    'Partially installed': 'Installé en partie',
    'No mesh open': 'Aucun maillage ouvert',
    'No 3D view in this build': 'Pas de vue 3D dans cette version',
    'The viewport reopens when the job ends.': "La vue se rouvre à la fin de la tâche.",
})

# ------------------------------------------------------------------------- field labels
FIELDS = {
    'Adaptivity': 'Adaptativité', 'Align': 'Aligner', 'Allow mirror': 'Autoriser le miroir',
    'Alpha mode': 'Mode alpha', 'Anisotropy': 'Anisotropie', 'Back': 'Dos',
    'Background': 'Fond', 'Bake normal map': 'Cuire la carte de normales',
    'Bake texture': 'Cuire la texture', 'Blend views': 'Fondre les vues',
    'Blockalign': 'Alignement par blocs', 'Body window': 'Fenêtre du corps',
    'Bruteforce': 'Force brute', 'Camera model': 'Modèle de caméra',
    'Candidates': 'Candidates', 'Cavity delight': 'Atténuation des cavités',
    'Chunk size': 'Taille de lot', 'Common framing': 'Cadrage commun',
    'Complexity': 'Complexité', 'Condition ratio': 'Ratio de conditionnement',
    'Contact sheet': 'Planche de contact', 'Count': 'Nombre', 'Deep': 'Approfondi',
    'Default azimuth': 'Azimut par défaut', 'Default elevation': 'Élévation par défaut',
    'Default fov': 'Champ de vision par défaut', 'Density threshold': 'Seuil de densité',
    'Depth margin': 'Marge de profondeur', 'Depth model': 'Modèle de profondeur',
    'Device': 'Périphérique', 'Disk budget gib': 'Budget disque (Gio)',
    'Edge scaling': 'Échelle des arêtes', 'Elevation': 'Élévation',
    'Embed textures': 'Intégrer les textures', 'Engine': 'Moteur',
    'Export glb': 'Exporter en GLB', 'Faces target': 'Cible de faces',
    'Family': 'Famille', 'Featureangle': 'Angle de caractéristique', 'Fidelity': 'Fidélité',
    'Fill holes': 'Boucher les trous', 'Fit weights': 'Poids d\'ajustement',
    'Fixwinding': 'Corriger l\'enroulement', 'Flip eval': 'Évaluation miroir',
    'Force same object': 'Forcer le même objet', 'Foreground ratio': 'Ratio du sujet',
    'Front': 'Face', 'Generate normals': 'Générer les normales',
    'Generated view bonus': 'Bonus des vues générées',
    'Generated view weight': 'Poids des vues générées', 'Generated views': 'Vues générées',
    'Global motion': 'Mouvement global', 'Gpu': 'GPU', 'Gpu index': 'Index GPU',
    'Grid resolution': 'Résolution de la grille', 'Guidance': 'Guidage',
    'Image file': 'Fichier image', 'Images': 'Images',
    'Include polar': 'Inclure les pôles', 'Include steps': 'Inclure les étapes',
    'Input': 'Entrée', 'Input file': 'Fichier d\'entrée', 'Input folder': 'Dossier d\'entrée',
    'Input pattern': 'Motif d\'entrée', 'Installed only': 'Installés seulement',
    'Iterations': 'Itérations', 'Keep input copies': 'Conserver les copies d\'entrée',
    'Keep intermediate': 'Conserver les intermédiaires',
    'Keep materials': 'Conserver les matériaux', 'Left': 'Gauche',
    'Low vram': 'VRAM réduite', 'Main axis': 'Axe principal',
    'Max polygon vertices': 'Sommets max par polygone', 'Max primitives': 'Primitives max',
    'Max sections': 'Sections max', 'Max views': 'Vues max', 'Maxcost': 'Coût max',
    'Mc resolution': 'Résolution marching cubes', 'Measure camera': 'Mesurer la caméra',
    'Mesh': 'Maillage', 'Mesh file': 'Fichier de maillage',
    'Metallic mode': 'Mode métallique', 'Metallic value': 'Valeur métallique',
    'Min facing': 'Orientation minimale', 'Min gain': 'Gain minimal',
    'Min part volume': 'Volume minimal d\'une pièce',
    'Min thickness ratio': 'Ratio d\'épaisseur minimal',
    'Mirrored view bonus': 'Bonus des vues miroir',
    'Mirrored view weight': 'Poids des vues miroir', 'Mode': 'Mode',
    'Model profile': 'Modèle personnalisé', 'Name': 'Nom',
    'Normal guidance': 'Guidage des normales', 'Origin at base': 'Origine à la base',
    'Output format': 'Format de sortie', 'Overwrite': 'Écraser', 'Padding': 'Marge',
    'Padding pixels': 'Marge en pixels', 'Part triangle penalty': 'Pénalité de triangles',
    'Prefer real': 'Préférer les vraies vues', 'Preremesh': 'Pré-remaillage',
    'Preview size': 'Taille de l\'aperçu', 'Preview views': 'Vues d\'aperçu',
    'Ram budget gib': 'Budget RAM (Gio)', 'Real size mm': 'Taille réelle (mm)',
    'Real view bonus': 'Bonus des vraies vues', 'Real view weight': 'Poids des vraies vues',
    'Refine': 'Affiner', 'Refine passes': 'Passes d\'affinage',
    'Refine poses': 'Affiner les poses', 'Register views': 'Recaler les vues',
    'Remesh': 'Remailler', 'Remove background': 'Détourer le fond',
    'Remove floaters': 'Retirer les débris', 'Repair': 'Réparer', 'Report': 'Rapport',
    'Resolution': 'Résolution', 'Reuse tolerance': 'Tolérance de réutilisation',
    'Right': 'Droite', 'Ring elevations': 'Élévations des anneaux',
    'Rotatecharts': 'Pivoter les îlots', 'Roughness mode': 'Mode de rugosité',
    'Roughness value': 'Valeur de rugosité', 'Sampler': 'Échantillonneur',
    'Scale': 'Échelle', 'Section vertices': 'Sommets par section', 'Seed': 'Graine',
    'Segmentation backend': 'Moteur de segmentation',
    'Segmentation model': 'Modèle de segmentation', 'Sharp edge': 'Arête vive',
    'Single view symmetry confidence': 'Confiance de symétrie sur une vue',
    'Smooth normal': 'Lisser les normales', 'Snap angle': 'Angle d\'accrochage',
    'Solverseconds': 'Secondes du solveur', 'Sources only': 'Sources seulement',
    'Split below': 'Séparer en dessous de', 'Start azimuth': 'Azimut de départ',
    'Steps': 'Pas', 'Steps shape': 'Pas de forme', 'Steps structure': 'Pas de structure',
    'Steps texture': 'Pas de texture', 'Stop on error': 'Arrêter en cas d\'erreur',
    'Subject set': 'Sujet préparé', 'Symmetry': 'Symétrie',
    'Symmetry threshold': 'Seuil de symétrie',
    'Synthesis coverage threshold': 'Seuil de couverture de synthèse',
    'Synthesis guidance': 'Guidage de synthèse', 'Synthesis seed': 'Graine de synthèse',
    'Synthesis source': 'Source de synthèse', 'Synthesis steps': 'Pas de synthèse',
    'Target faces': 'Faces cibles', 'Target quads': 'Quads cibles',
    'Target size': 'Taille cible', 'Target vertices': 'Sommets cibles',
    'Targets': 'Cibles', 'Tex guidance': 'Guidage de texture',
    'Texture blend': 'Fondu de texture', 'Texture padding': 'Marge de texture',
    'Texture resolution': 'Résolution de texture', 'Texture size': 'Taille de texture',
    'Thin as planes': 'Pièces fines en plans', 'Tier': 'Palier',
    'Transparency': 'Transparence', 'Triangulate': 'Trianguler',
    'Unobserved extent ratio': 'Ratio d\'étendue non observée', 'Up axis': 'Axe vertical',
    'Upscale': 'Agrandir', 'Use depth': 'Utiliser la profondeur', 'Uv mode': 'Mode UV',
    'Variants': 'Variantes', 'Video': 'Vidéo', 'View synthesis': 'Synthèse de vues',
    'View synthesis model': 'Modèle de synthèse de vues',
    'Visibility resolution': 'Résolution de visibilité',
    'Vram budget gib': 'Budget VRAM (Gio)', 'Weld tolerance': 'Tolérance de soudure',
    'Workflow': 'Workflow', 'Workflow name': 'Nom du workflow',
}

# ------------------------------------------------------------- operation names (manifest)
OPERATIONS = {
    'Quad remesh (AutoRemesher)': 'Remaillage quad (AutoRemesher)',
    'Quad remesh (QuadWild Bi-MDF)': 'Remaillage quad (QuadWild Bi-MDF)',
    'UV unwrap (xatlas)': 'Dépliage UV (xatlas)',
    'UV repack (xatlas)': 'Repacking UV (xatlas)',
    'Bake PBR channels': 'Cuire les canaux PBR',
    'Inspect a mesh': 'Inspecter un maillage',
    'Image to mesh (TripoSR)': 'Image vers maillage (TripoSR)',
    'Image to mesh (SPAR3D)': 'Image vers maillage (SPAR3D)',
    'Photographs to a textured mesh (TRELLIS.2)': 'Photos vers maillage texturé (TRELLIS.2)',
    'Construct a proxy mesh from pictures': 'Construire un maillage proxy depuis des photos',
    'Analyse a set of pictures': 'Analyser un jeu de photos',
    'Generate new views': 'Générer de nouvelles vues',
    'Complete a view set': 'Compléter un jeu de vues',
    'Turntable views': 'Vues en rotation',
    'Mirror a view': 'Mettre une vue en miroir',
    'Score candidate views': 'Noter des vues candidates',
    'Segment the object': "Segmenter l'objet",
    'Prepare the subject (shared front end)': 'Préparer le sujet (front-end partagé)',
    'Rig a mesh (UniRig)': 'Rigger un maillage (UniRig)',
    'Video to 3D human motion (WHAM)': 'Vidéo vers mouvement humain 3D (WHAM)',
    'Inspect a video': 'Inspecter une vidéo',
    'Edit a mesh': 'Éditer un maillage',
    'Convert a mesh': 'Convertir un maillage',
    'Run a workflow': 'Exécuter un workflow',
    'Save a workflow': 'Enregistrer un workflow',
    'List the workflows': 'Lister les workflows',
    'Install or repair an engine': 'Installer ou réparer un moteur',
    'Diagnose the installation': "Diagnostiquer l'installation",
    'List the models': 'Lister les modèles',
}


# ------------------------------------------------------ operation descriptions (manifest)
DESCRIPTIONS = {
    'Rebuild the topology as a quad dominant mesh with the official AutoRemesher program. '
    'Geometry only: UV sets and materials of the input are not carried over, and the quad target is approximate.':
        "Refait la topologie en un maillage majoritairement quad avec le programme officiel "
        "AutoRemesher. Géométrie seule : les UV et les matériaux de l'entrée ne sont pas repris, "
        "et la cible de quads est approximative.",
    'Field aligned quadrangulation of a triangulated mesh with the official QuadWild Bi-MDF binaries. '
    'Slower than AutoRemesher and bounded by a solver time limit, but follows the curvature field.':
        "Quadrangulation alignée sur le champ d'un maillage triangulé, avec les binaires officiels "
        "QuadWild Bi-MDF. Plus lent qu'AutoRemesher et borné par une limite de temps du solveur, "
        "mais il suit le champ de courbure.",
    'Generate UV charts and pack them into a single atlas with xatlas.':
        "Génère les îlots UV et les range dans un seul atlas avec xatlas.",
    'Repack the UV charts the mesh already carries, without recomputing the parametrisation.':
        "Réagence les îlots UV déjà portés par le maillage, sans recalculer la paramétrisation.",
    'Bake Base Color, Metallic, Roughness and Alpha into a UV atlas, plus the glTF packed '
    'metallic-roughness map. Colour carried by the mesh is baked; channels the mesh does not carry are '
    'derived with documented deterministic heuristics, not generated by a model.':
        "Cuit Base Color, Metallic, Roughness et Alpha dans un atlas UV, plus la carte "
        "metallic-roughness empaquetée du glTF. La couleur portée par le maillage est cuite ; les "
        "canaux qu'il ne porte pas sont dérivés par des heuristiques déterministes documentées, pas "
        "générés par un modèle.",
    'Report geometry, UV, colour source, materials and transparency of a mesh, plus the settings '
    'recommended before baking.':
        "Rend la géométrie, les UV, la source de couleur, les matériaux et la transparence d'un "
        "maillage, ainsi que les réglages conseillés avant la cuisson.",
    'Reconstruct one object from a single image in seconds: feed-forward NeRF then marching cubes, '
    'vertex colours or a baked texture atlas. Fast prototyping, not a measurement of the real object.':
        "Reconstruit un objet depuis une seule image en quelques secondes : NeRF en une passe puis "
        "marching cubes, couleurs par sommet ou atlas de texture cuit. Prototypage rapide, pas une "
        "mesure de l'objet réel.",
    'Reconstruct one object as a textured mesh with its point cloud. The backside is inferred by the '
    'model, not measured.':
        "Reconstruit un objet en maillage texturé avec son nuage de points. L'arrière est inféré par "
        "le modèle, pas mesuré.",
    'One photograph, or four views of the same subject, to a textured GLB with the TRELLIS.2 pipeline. '
    'Local CUDA inference.':
        "Une photo, ou quatre vues du même sujet, vers un GLB texturé avec la chaîne TRELLIS.2. "
        "Inférence CUDA locale.",
    'Build a simple, clean, mostly hard-surface proxy mesh (lofted cross-sections, extruded polygons, '
    'boxes, cylinders) from one or several pictures of the same object, and project the pictures on it. '
    'AI models only supply masks, relative depth, camera poses and optional synthetic views.':
        "Construit un maillage proxy simple et propre, surtout hard-surface (sections lissées, "
        "polygones extrudés, boîtes, cylindres) depuis une ou plusieurs photos du même objet, et y "
        "projette les photos. Les modèles IA ne fournissent que les masques, la profondeur relative, "
        "les poses de caméra et, en option, des vues synthétiques.",
    'Pre-flight for a reconstruction: segmentation, view poses, same-object check, coverage map and the '
    'list of viewpoints that are missing.':
        "Contrôle préalable à une reconstruction : segmentation, poses des vues, vérification qu'il "
        "s'agit du même objet, carte de couverture et liste des points de vue manquants.",
    'Generate the requested viewpoints of the object locally. Real photographs are reused when they '
    'already cover a requested angle.':
        "Génère localement les points de vue demandés de l'objet. Les vraies photos sont réutilisées "
        "quand elles couvrent déjà un angle demandé.",
    'Analyse the supplied images, decide which important viewpoints are missing and generate only those.':
        "Analyse les images fournies, décide quels points de vue importants manquent et ne génère "
        "que ceux-là.",
    'Produce N equally spaced views around the object, on one ring or on several rings at different '
    'elevations.':
        "Produit N vues également réparties autour de l'objet, sur un anneau ou sur plusieurs anneaux "
        "à des élévations différentes.",
    'Produce the opposite view by mirroring one real image. A geometric flip, not a generation: it is '
    'only valid for a symmetric object.':
        "Produit la vue opposée en retournant une vraie image. C'est un miroir géométrique, pas une "
        "génération : cela ne vaut que pour un objet symétrique.",
    'Score candidate views against the real photographs of the same object: identity, features, colour '
    'and materials.':
        "Note des vues candidates face aux vraies photos du même objet : identité, traits, couleur et "
        "matériaux.",
    'Isolate the object in every supplied image and return its mask, an RGBA cut-out and its bounding box.':
        "Isole l'objet dans chaque image fournie et rend son masque, un détourage RGBA et sa boîte "
        "englobante.",
    'Predict a skeleton and skinning weights for a mesh with UniRig Articulation-XL.':
        "Prédit un squelette et des poids de skinning pour un maillage avec UniRig Articulation-XL.",
    'Reconstruct SMPL poses, translations and time stamps of the people in a monocular video.':
        "Reconstruit les poses SMPL, les translations et les repères temporels des personnes d'une "
        "vidéo monoculaire.",
    'Decode every frame and report a JPEG preview and the metadata of the file.':
        "Décode toutes les images et rend un aperçu JPEG ainsi que les métadonnées du fichier.",
    'Apply a chain of geometric edits to a mesh and write the result: transforms, decimation, cleaning, '
    'hole filling, components and material stripping. Every step is deterministic and the input file is '
    'never modified.':
        "Applique une suite d'éditions géométriques à un maillage et écrit le résultat : "
        "transformations, décimation, nettoyage, bouchage des trous, composants et retrait des "
        "matériaux. Chaque étape est déterministe et le fichier d'entrée n'est jamais modifié.",
    'Convert a mesh between the supported formats, optionally triangulating it and embedding or '
    'extracting its textures.':
        "Convertit un maillage entre les formats pris en charge, en le triangulant si besoin et en "
        "intégrant ou en extrayant ses textures.",
    'Cut the subject out of every view once, at a common scale, and measure where each photograph was '
    'taken from. The result is a subject set that every reconstruction backend can consume, instead of '
    'each one carrying its own background remover and its own camera estimate.':
        "Détoure le sujet de chaque vue une seule fois, à une échelle commune, et mesure d'où chaque "
        "photo a été prise. Le résultat est un sujet préparé que tous les moteurs de reconstruction "
        "peuvent consommer, au lieu que chacun porte son propre détoureur et sa propre estimation de "
        "caméra.",
    'Run a saved chain of operations on one input or on every file of a folder. Each step is submitted '
    'as a real job on the same runtime as the interface, the CLI and MCP.':
        "Exécute une suite d'opérations enregistrée sur une entrée ou sur tous les fichiers d'un "
        "dossier. Chaque étape est soumise comme un vrai job, sur le même runtime que l'interface, la "
        "CLI et MCP.",
    'Write a workflow document to data/workflows so that the interface, the CLI and MCP can run it by name.':
        "Écrit un document de workflow dans data/workflows pour que l'interface, la CLI et MCP "
        "puissent l'exécuter par son nom.",
    'List the workflows saved in data/workflows with their steps and the operations they use.':
        "Liste les workflows enregistrés dans data/workflows, avec leurs étapes et les opérations "
        "qu'ils utilisent.",
    'Create or repair one of the engine environments declared in app/engines.json, including the '
    'upstream sources it needs. Downloads happen here, never during an inference job.':
        "Crée ou répare un des environnements moteurs déclarés dans app/engines.json, avec les "
        "sources amont dont il a besoin. Les téléchargements ont lieu ici, jamais pendant un job "
        "d'inférence.",
    'Report the state of every engine, backend, native program and model: what is installed, what is '
    'missing, and which device each backend would really use.':
        "Rend l'état de chaque moteur, backend, programme natif et modèle : ce qui est installé, ce "
        "qui manque, et quel périphérique chaque backend utiliserait réellement.",
    'List every model of the catalogue with its family, its engine, its size on disk, its licence and '
    'whether it is installed.':
        "Liste tous les modèles du catalogue avec leur famille, leur moteur, leur taille sur le "
        "disque, leur licence et s'ils sont installés.",
}


from locales_fr_parameters import PARAMETERS  # noqa: E402  (same folder, data only)
from locales_fr_titles import TITLES  # noqa: E402
from locales_fr_localmesh import LOCALMESH_PLUS  # noqa: E402


def catalogue():
    try:
        return json.loads(CATALOG.read_text('utf-8'))
    except (OSError, ValueError):
        return {}


def collect():
    """Every string the interface can display, so a missing translation is measurable."""
    strings = set(INTERFACE) | set(FIELDS) | set(OPERATIONS)
    manifest = json.loads(MANIFEST.read_text('utf-8'))
    for operation in manifest['operations']:
        strings.add(operation['name'])
        if operation.get('description'):
            strings.add(operation['description'])
        if operation.get('x-cy-category'):
            strings.add(operation['x-cy-category'])
        # The editor labels a field with its schema title when there is one, and only falls
        # back to the field name; collecting names alone reported "0 missing" while every
        # titled field of the absorbed Tools was still shown in English.
        def fields(properties):
            for name, schema in (properties or {}).items():
                if not isinstance(schema, dict):
                    continue
                yield name, schema
                yield from fields(schema.get('properties'))
                items = schema.get('items')
                if isinstance(items, dict):
                    yield from fields(items.get('properties'))

        for name, schema in fields(operation['inputSchema'].get('properties')):
            strings.add(schema.get('title') or name.replace('_', ' ').capitalize())
            if schema.get('description'):
                strings.add(schema['description'])
    # The pages of the façade (options, log, advanced, 3D view) translate their own strings too,
    # and the action buttons pass their English label to widgets.action, which translates it.
    sources = sorted((APP / 'gui').glob('*.py')) + [
        APP / name for name in ('ui_common.py', 'standalone_log.py', 'advanced_ui.py',
                                'mesh_viewer_ui.py', 'installation_ui.py') if (APP / name).exists()]
    pattern = re.compile(r"""\b_?(?:tr|action)\(\s*(?:'([^'\n]{2,200})'|"([^"\n]{2,200})")\s*[,)]""")
    for source in sources:
        text = source.read_text('utf-8')
        for match in pattern.finditer(text):
            strings.add(match.group(1) or match.group(2))
    # Labels translated through a variable: the navigation groups and the theme names.
    strings |= {'WORKSPACE', 'SYSTEM', 'Interface', 'Installed', 'Partially installed', 'Not installed'}
    try:
        sys.path.insert(0, str(APP))
        import cyui
        strings |= {name for _key, name, _values, _light in cyui.THEMES}
    except Exception:  # noqa: BLE001 - imgui missing: the themes are then not checked
        pass
    return strings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='only report, write nothing')
    args = parser.parse_args(argv)

    current = catalogue()
    translations = {**INTERFACE, **FIELDS, **OPERATIONS, **DESCRIPTIONS, **PARAMETERS, **TITLES, **LOCALMESH_PLUS}
    added = 0
    for english, french in translations.items():
        entry = current.get(english)
        if entry and entry.get('fr') == french:
            continue
        current[english] = {'en': english, 'fr': french}
        added += 1

    if not args.check:
        CATALOG.write_text(json.dumps(current, indent=1, ensure_ascii=False, sort_keys=True) + '\n',
                           encoding='utf-8')

    wanted = collect()
    # A handful of words are spelled the same in both languages (Application, Mode, UV...).
    # They are translated, they just look untranslated, so they are not counted as gaps.
    identical = {english for english, french in translations.items() if english == french}
    missing = sorted(text for text in wanted
                     if text not in current
                     or (current[text].get('fr') == text and text not in identical))
    print(f'{len(current)} entries in the catalogue, {added} written, '
          f'{len(wanted)} strings collected, {len(missing)} without a French translation '
          f'({len(identical & wanted)} are identical in both languages)')
    shown = len(missing) if args.check else 40
    for text in missing[:shown]:
        print('  -', text[:110])
    if len(missing) > shown:
        print(f'  ... and {len(missing) - shown} more')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
