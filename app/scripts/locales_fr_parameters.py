"""French for the parameter tooltips and the remaining interface strings.

These are the descriptions the manifest carries for every input field, which the parameter
editor shows as a tooltip. They live apart from ``update_locales.py`` only because of their
number; that script merges this table like the others.

The vocabulary follows the rest of the interface: *vue* for a viewpoint, *maillage* for a mesh,
*graine* for a seed, *moteur* for an engine, *poids* for model weights. Names of programs,
models and file formats are kept as they are.
"""

PARAMETERS = {
    # ------------------------------------------------------------ short field labels
    'Application': 'Application',
    'Backup': 'Sauvegarde',
    'Candidates': 'Candidates',
    'Description': 'Description',
    'Images': 'Images',
    'Inspection': 'Inspection',
    'Installation': 'Installation',
    'Licence': 'Licence',
    'Maintenance': 'Maintenance',
    'Mode': 'Mode',
    'Reconstruction': 'Reconstruction',
    'Release file': 'Fichier de version',
    'Repository': 'Dépôt',
    'Sha256': 'SHA-256',
    'Skip optional': 'Ignorer les fichiers facultatifs',
    'Source': 'Source',
    'Staged': 'Préparé',
    'Stream': 'Flux',
    'Target': 'Cible',
    'UV': 'UV',
    'Version': 'Version',
    'version': 'version',
    'Workflow': 'Workflow',
    'Workflows': 'Workflows',

    # ------------------------------------------------------------ LocalMesh
    'Image or photos to a textured mesh (LocalMesh)':
        'Image ou photos vers maillage texturé (LocalMesh)',
    'LocalMesh: one image, or four photographs of the same subject, to a textured GLB. The TRELLIS.2 '
    'model generates the shape; the mesh is then cleaned, remeshed and decimated, and its PBR texture '
    'is generated for that final mesh, with a baked normal map. Local CUDA inference.':
        "LocalMesh : une image, ou quatre photos du même sujet, vers un GLB texturé. Le modèle "
        "TRELLIS.2 génère la forme ; le maillage est ensuite nettoyé, remaillé et décimé, et sa "
        "texture PBR est générée pour ce maillage final, avec une normal map cuite. Inférence CUDA "
        "locale.",
    'draft: 512 grid, 80 000 faces, 2K atlas, to judge the shape. '
    'standard: 1024 grid, 150 000 faces, 4K atlas. '
    'high: 1024 grid, 16 passes, 250 000 faces, 4K atlas. '
    'max: 1536 grid, 400 000 faces, 8K atlas; needs a 24 GB card, and with '
    'four photos it uses the older view mixer because the four-view models '
    'stop at 1024.':
        "draft : grille 512, 80 000 faces, atlas 2K, pour juger la forme. "
        "standard : grille 1024, 150 000 faces, atlas 4K. "
        "high : grille 1024, 16 passes, 250 000 faces, atlas 4K. "
        "max : grille 1536, 400 000 faces, atlas 8K ; demande une carte de 24 Go, et avec "
        "quatre photos il passe par l'ancien mélangeur de vues, car les modèles à quatre vues "
        "s'arrêtent à 1024.",
    'Quality': 'Qualité',

    # ------------------------------------------------------------ operation names
    'Activate a staged update': 'Activer une mise à jour préparée',
    'Import a licensed model file': 'Importer un fichier de modèle sous licence',
    'Install or repair a model': 'Installer ou réparer un modèle',
    'Roll back to a backup': 'Revenir à une sauvegarde',
    'Stage an update': 'Préparer une mise à jour',
    'Update state': 'État des mises à jour',

    # ------------------------------------------------------ operation descriptions
    'Ask the configured GitHub repository for its latest release and compare it with the '
    'installed version. The engines and the weights streams answer from local files: they are '
    'updated by reinstalling an engine or a model, not by a release.':
        "Demande au dépôt GitHub configuré sa dernière version publiée et la compare à la "
        "version installée. Les flux des moteurs et des poids répondent depuis des fichiers "
        "locaux : ils se mettent à jour en réinstallant un moteur ou un modèle, pas par une "
        "version publiée.",
    'Download or copy a release archive, check its SHA-256 when one is given, unpack it under '
    'runtime/updates and verify it holds this Tool and no data folder. Nothing is activated: '
    'the running application is untouched.':
        "Télécharge ou copie une archive de version, vérifie son SHA-256 quand il est donné, la "
        "décompresse dans runtime/updates et contrôle qu'elle contient bien cet outil et aucun "
        "dossier data. Rien n'est activé : l'application en cours d'exécution n'est pas touchée.",
    'Download the weights of a model that is declared but absent, into data/models. Files whose '
    'licence is accepted in person are never downloaded here: the answer names them, and '
    'import_model_file puts them in place once obtained.':
        "Télécharge dans data/models les poids d'un modèle déclaré mais absent. Les fichiers dont "
        "la licence s'accepte en personne ne sont jamais téléchargés ici : la réponse les nomme, "
        "et import_model_file les met en place une fois obtenus.",
    'Put in place a file the user downloaded themselves after accepting its licence, such as the '
    'SMPL body model. The application never asks for the credentials of those sites; it checks '
    'the file, copies it into data/models and records its hash.':
        "Met en place un fichier que vous avez téléchargé vous-même après en avoir accepté la "
        "licence, comme le modèle corporel SMPL. L'application ne demande jamais les identifiants "
        "de ces sites ; elle vérifie le fichier, le copie dans data/models et enregistre son "
        "empreinte.",
    'Record the reverse swap: the next start restores a kept backup of the app folder. Cancelling '
    'instead drops a pending request. Your data is never part of either move.':
        "Enregistre l'échange inverse : le prochain démarrage restaure une sauvegarde conservée du "
        "dossier app. L'annulation abandonne plutôt une demande en attente. Vos données ne font "
        "jamais partie de l'un ni de l'autre.",
    'Verify a staged update once more and record the swap for the next start. The folders are '
    'exchanged by a separate process before the application loads, so the running code is never '
    'replaced underneath itself, the previous app folder is kept as a backup, and data/ is not '
    'touched.':
        "Vérifie une dernière fois une mise à jour préparée et enregistre l'échange pour le "
        "prochain démarrage. Les dossiers sont échangés par un processus distinct avant le "
        "chargement de l'application : le code en cours d'exécution n'est jamais remplacé sous "
        "ses propres pieds, le dossier app précédent est conservé en sauvegarde, et data/ n'est "
        "pas touché.",
    'Where the three streams stand: the application version and its repository, what is staged, '
    'what is pending for the next start, the backups kept, the engines and their pinned '
    'revisions, and the model catalogue. Reads local files only.':
        "Où en sont les trois flux : la version de l'application et son dépôt, ce qui est préparé, "
        "ce qui attend le prochain démarrage, les sauvegardes conservées, les moteurs avec leurs "
        "révisions épinglées, et le catalogue des modèles. Ne lit que des fichiers locaux.",

    # ------------------------------------------------------------ update parameters
    'A release description already on disk, instead of asking GitHub (used by the tests).':
        "Une description de version déjà présente sur le disque, au lieu d'interroger GitHub "
        "(utilisé par les tests).",
    'Backup folder to restore; the most recent one when left empty.':
        'Dossier de sauvegarde à restaurer ; la plus récente si le champ est vide.',
    'Download again even when the files are already present.':
        'Retélécharger même si les fichiers sont déjà présents.',
    'Drop the pending request instead of rolling back.':
        "Abandonner la demande en attente au lieu de revenir en arrière.",
    'Expected SHA-256 of the archive; refused when it differs.':
        "SHA-256 attendu de l'archive ; refusée s'il diffère.",
    'GitHub repository owner/name; saved in data/settings/updates.json.':
        'Dépôt GitHub propriétaire/nom ; enregistré dans data/settings/updates.json.',
    'Leave the optional files out (global motion for WHAM).':
        'Laisser de côté les fichiers facultatifs (mouvement global pour WHAM).',
    'Model identifier, as list_models reports it.':
        'Identifiant du modèle, tel que list_models le rapporte.',
    'Name of the staging folder; defaults to the archive digest.':
        "Nom du dossier de préparation ; par défaut l'empreinte de l'archive.",
    'Staged folder; the most recent one when left empty.':
        'Dossier préparé ; le plus récent si le champ est vide.',
    'The file downloaded from the official page (.pkl, or the .zip holding it).':
        'Le fichier téléchargé depuis la page officielle (.pkl, ou le .zip qui le contient).',
    'URL of the release asset, or a local .zip.':
        "URL du fichier de la version publiée, ou un .zip local.",
    'Which declared file this is, when the model expects several.':
        'De quel fichier déclaré il s\'agit, quand le modèle en attend plusieurs.',
    'Which stream to check.': 'Quel flux vérifier.',

    # ------------------------------------------------------- reconstruction, views
    '-1 draws a seed. The resolved seed is reported in the outputs and in the View Set so a run '
    'can be repeated.':
        "-1 tire une graine au hasard. La graine retenue est indiquée dans les sorties et dans le "
        "jeu de vues, pour pouvoir rejouer l'exécution.",
    '0 keeps the native resolution of the backend. A larger value only applies when resampling is '
    'enabled; resampling adds no detail.':
        "0 conserve la résolution native du moteur. Une valeur plus grande ne s'applique que si le "
        "rééchantillonnage est activé ; le rééchantillonnage n'ajoute aucun détail.",
    'Views of the same subject. Without a front view, the role of each is read from its file '
    'name (front, right, left, back, or face, droite, gauche, dos); the first one without a role '
    'becomes the front.':
        "Vues du même sujet. Sans vue de face, le rôle de chacune est lu dans son nom de fichier "
        "(front, right, left, back, ou face, droite, gauche, dos) ; la première sans rôle devient "
        "la face.",
    'Angular distance in degrees within which a real photograph answers a requested viewpoint.':
        "Écart angulaire, en degrés, dans lequel une photo réelle répond à un point de vue demandé.",
    'Auto selects CUDA when a device is present. CPU works for segmentation and analysis; '
    'generation on CPU is extremely slow and is not validated.':
        "auto choisit CUDA quand une carte est présente. Le CPU convient à la segmentation et à "
        "l'analyse ; la génération sur CPU est extrêmement lente et n'est pas validée.",
    'Auto symmetry: minimal ratio of silhouette coherence with/without mirrored views.':
        "Symétrie automatique : rapport minimal de cohérence de silhouette avec/sans vues "
        "miroir.",
    'Azimuth assumed when nothing else is known (degrees).':
        "Azimut supposé quand rien d'autre n'est connu (degrés).",
    'Back view.': 'Vue de dos.',
    'CPU is supported by the upstream code but is far slower; it is not a validated path here.':
        "Le CPU est pris en charge par le code amont mais il est bien plus lent ; ce chemin n'est "
        "pas validé ici.",
    'Classical registration of real views (OpenCV SIFT + essential matrix) for pictures without a '
    'pose.':
        "Recalage classique des vues réelles (OpenCV SIFT + matrice essentielle) pour les photos "
        "sans pose.",
    'Classifier-free guidance of the generation backend.':
        'Guidage sans classifieur du moteur de génération.',
    'Classifier-free guidance scale. Omitted = the generator default (Zero123++ 4.0, Wonder3D 3.0, '
    'SyncDreamer 2.0).':
        "Échelle du guidage sans classifieur. Omise = la valeur par défaut du générateur "
        "(Zero123++ 4.0, Wonder3D 3.0, SyncDreamer 2.0).",
    'Confidence of the assumed symmetry when it cannot be measured.':
        "Confiance accordée à la symétrie supposée quand elle ne peut pas être mesurée.",
    'Cut every view at one common scale. Required by a multi-view fusion: framing each view on its '
    'own scales an elongated object differently per view.':
        "Détourer toutes les vues à une échelle commune. Indispensable à une fusion multi-vues : "
        "cadrer chaque vue séparément met un objet allongé à une échelle différente selon la vue.",
    'Depth Anything V2 checkpoint (relative depth, low-confidence cue). Base and Large are '
    'CC-BY-NC-4.0 and require a personal licence acceptance.':
        "Modèle Depth Anything V2 (profondeur relative, indice de faible confiance). Les variantes "
        "Base et Large sont en CC-BY-NC-4.0 et demandent une acceptation personnelle de la licence.",
    'Device of the AI understanding stage. auto = CUDA when PyTorch sees it, else CPU. The fitting '
    'engine always runs on the CPU.':
        "Périphérique de l'étape de compréhension par IA. auto = CUDA quand PyTorch la voit, sinon "
        "CPU. Le moteur d'ajustement tourne toujours sur le CPU.",
    'Diffusion steps of the generator. Omitted = its own default (Zero123++ 36, Wonder3D 50, '
    'SyncDreamer 50).':
        "Pas de diffusion du générateur. Omis = sa propre valeur par défaut (Zero123++ 36, "
        "Wonder3D 50, SyncDreamer 50).",
    'Each variant is a complete generation with its own seed, so the best one can be selected '
    'afterwards.':
        "Chaque variante est une génération complète avec sa propre graine, pour pouvoir choisir "
        "la meilleure ensuite.",
    'Elevation assumed when nothing else is known (degrees).':
        "Élévation supposée quand rien d'autre n'est connu (degrés).",
    'Field of view assumed for pictures without one (degrees, 0 = orthographic).':
        "Champ de vision supposé pour les photos qui n'en ont pas (degrés, 0 = orthographique).",
    'Folder produced by prepare_subject. Its cut-outs are used as the views, so the subject is '
    'segmented once for the whole workflow instead of once per backend.':
        "Dossier produit par prepare_subject. Ses détourages servent de vues : le sujet est "
        "segmenté une seule fois pour tout le workflow au lieu d'une fois par moteur.",
    'Folder produced by prepare_subject; its front cut-out replaces the image and switches the '
    'internal background removal off.':
        "Dossier produit par prepare_subject ; son détourage de face remplace l'image et désactive "
        "le détourage interne.",
    'Fraction of the frame occupied by the object after cropping.':
        "Fraction du cadre occupée par l'objet après recadrage.",
    'Fraction of the square conditioning image the object occupies before generation.':
        "Fraction de l'image carrée de conditionnement occupée par l'objet avant génération.",
    'Index in `images` of the picture given to Zero123++. -1 = first picture that is not a '
    'top/bottom view.':
        "Indice, dans `images`, de la photo donnée à Zero123++. -1 = première photo qui n'est pas "
        "une vue de dessus ou de dessous.",
    'Largest dimension of the exported mesh, in glTF units (metres). Relative proportions only: no '
    'absolute scale is recovered from pictures.':
        "Plus grande dimension du maillage exporté, en unités glTF (mètres). Proportions relatives "
        "seulement : aucune échelle absolue n'est retrouvée à partir de photos.",
    'Left side view.': 'Vue de profil gauche.',
    'Marching cubes grid resolution. Lower is faster and coarser.':
        'Résolution de la grille marching cubes. Plus bas = plus rapide et plus grossier.',
    'Measure the azimuth of each view instead of assuming a regular turntable.':
        "Mesurer l'azimut de chaque vue au lieu de supposer un tour régulier.",
    'Minimum silhouette symmetry score accepted for an automatic mirror.':
        'Score minimal de symétrie de silhouette accepté pour un miroir automatique.',
    'Mirror plane normal. Auto measures bilateral symmetry (normal = Z, left/right) from several '
    'views, or assumes it for a single picture. Force X = front/back, Force Y = top/bottom, Force '
    'Z = left/right.':
        "Normale du plan de symétrie. auto mesure la symétrie bilatérale (normale = Z, "
        "gauche/droite) sur plusieurs vues, ou la suppose pour une photo unique. Force X = "
        "avant/arrière, Force Y = haut/bas, Force Z = gauche/droite.",
    'Mirroring an existing view is instant and uses no model, but it assumes bilateral symmetry.':
        "Mettre une vue existante en miroir est instantané et n'utilise aucun modèle, mais cela "
        "suppose une symétrie bilatérale.",
    'Missing-view generation with Zero123++ v1.2 (six views at known poses from one real picture, '
    'CUDA only). auto = only when the Real Coverage Score is below synthesis_coverage_threshold '
    'and the model is installed; always = generate or fail; off = never. Generated views vote with '
    'generated_view_weight and never override a real picture.':
        "Génération des vues manquantes avec Zero123++ v1.2 (six vues à poses connues depuis une "
        "photo réelle, CUDA uniquement). auto = seulement quand le score de couverture réelle est "
        "sous synthesis_coverage_threshold et que le modèle est installé ; always = générer ou "
        "échouer ; off = jamais. Les vues générées votent avec generated_view_weight et ne "
        "prennent jamais le pas sur une photo réelle.",
    'Missing-view generator. auto = first installed of Zero123++ v1.2 (6 views, absolute elevations '
    '+20/-10, FOV 30), Wonder3D v1.0 (6 orthographic views in the frame of the input picture, '
    'colour + normals) and SyncDreamer (16 views at a fixed elevation of 30 degrees). Wonder3D and '
    'SyncDreamer run in their own environment and pinned source checkout (Installation tab). All '
    'need a CUDA GPU.':
        "Générateur de vues manquantes. auto = le premier installé parmi Zero123++ v1.2 (6 vues, "
        "élévations absolues +20/-10, champ 30), Wonder3D v1.0 (6 vues orthographiques dans le "
        "repère de la photo d'entrée, couleur + normales) et SyncDreamer (16 vues à une élévation "
        "fixe de 30 degrés). Wonder3D et SyncDreamer tournent dans leur propre environnement et "
        "leur source épinglée (onglet Installation). Tous demandent une carte CUDA.",
    'One or more images of the same object. Image path: an absolute local path, or a path relative '
    'to data/inputs. The file is copied into the private job workspace automatically; no manual '
    'import is required. PNG, JPEG or WebP, at most 48 MiB and 60 megapixels.':
        "Une ou plusieurs images du même objet. Chemin d'image : un chemin local absolu, ou relatif "
        "à data/inputs. Le fichier est copié automatiquement dans l'espace de travail privé du "
        "job ; aucun import manuel n'est nécessaire. PNG, JPEG ou WebP, 48 Mio et 60 mégapixels au "
        "maximum.",
    'One ring per elevation, for example [0, 30, -20]. Overrides the single ring elevation when '
    'present.':
        "Un anneau par élévation, par exemple [0, 30, -20]. Remplace l'élévation d'anneau unique "
        "quand la liste est fournie.",
    'One to twelve real pictures of the SAME object. Real pictures always win over synthetic data.':
        "De une à douze photos réelles du MÊME objet. Les photos réelles l'emportent toujours sur "
        "les données synthétiques.",
    'Optional synthetic views with their requested poses. They only vote with a reduced weight and '
    'can never carve away what a real picture shows.':
        "Vues synthétiques facultatives avec les poses demandées. Elles ne votent qu'avec un poids "
        "réduit et ne peuvent jamais creuser ce qu'une photo réelle montre.",
    'Number of NeRF-rendered turntable PNG previews. 0 skips rendering.':
        "Nombre d'aperçus PNG en rotation rendus par le NeRF. 0 n'en rend aucun.",
    'Number of equally spaced azimuths on each ring.':
        'Nombre d\'azimuts régulièrement espacés sur chaque anneau.',
    'Only used by backends that expose a step count.':
        "Utilisé seulement par les moteurs qui exposent un nombre de pas.",
    'Perspective Fields (Paramnet-360Cities-edina-centered): roll, pitch (elevation = -pitch) and '
    'field of view of each real picture. Applied only to values the user did not give and only when '
    'the picture shows a scene; on a cut-out object the cue is reported but not used. Adobe '
    'Research License, non-commercial: personal acceptance required.':
        "Perspective Fields (Paramnet-360Cities-edina-centered) : roulis, tangage (élévation = "
        "-tangage) et champ de vision de chaque photo réelle. Appliqué seulement aux valeurs que "
        "vous n'avez pas données et seulement quand la photo montre une scène ; sur un objet "
        "détouré, l'indice est rapporté mais pas utilisé. Licence Adobe Research, non commerciale : "
        "acceptation personnelle requise.",
    'Preset viewpoints, arbitrary azimuth/elevation/roll, or a mix. A requested view already '
    'covered by a real photograph is reused instead of generated.':
        "Points de vue prédéfinis, azimut/élévation/roulis libres, ou un mélange. Une vue demandée "
        "déjà couverte par une photo réelle est réutilisée au lieu d'être générée.",
    'Reference view of the subject. Optional when images are given.':
        'Vue de référence du sujet. Facultative quand des images sont données.',
    'Refine unposed views by silhouette coherence.':
        'Affiner les vues sans pose par cohérence de silhouette.',
    'Right side view.': 'Vue de profil droit.',
    'Run rembg on the input. Disable only for an image that already has a clean, centred '
    'foreground.':
        "Passer rembg sur l'entrée. Ne le désactiver que pour une image dont l'avant-plan est déjà "
        "propre et centré.",
    'SAM 2.1 checkpoint for the object mask. auto = preferred installed model, else classical '
    'segmentation (alpha / plain background / GrabCut). none = classical only.':
        "Modèle SAM 2.1 pour le masque de l'objet. auto = le modèle installé préféré, sinon la "
        "segmentation classique (alpha / fond uni / GrabCut). none = classique seulement.",
    'Same-object verification reports suspicious images and refuses to generate from them. Enable '
    'this to proceed anyway.':
        "La vérification « même objet » signale les images suspectes et refuse de générer à partir "
        "d'elles. Activer ceci pour continuer malgré tout.",
    'Uses the Zero123++ normal ControlNet. It also produces a matted alpha channel that is more '
    'accurate than the segmentation backend.':
        "Utilise le ControlNet de normales de Zero123++. Il produit aussi un canal alpha détouré "
        "plus précis que celui du moteur de segmentation.",
    'Use the depth maps for pose estimation and concavity carving.':
        "Utiliser les cartes de profondeur pour estimer les poses et creuser les concavités.",
    'Used when no explicit list of ring elevations is given.':
        "Utilisé quand aucune liste explicite d'élévations d'anneaux n'est donnée.",
    'When a real photograph already covers a requested viewpoint it is reused instead of generated.':
        "Quand une photo réelle couvre déjà un point de vue demandé, elle est réutilisée au lieu "
        "d'être générée.",
    'When no picture limits the object along an axis (single front view, two opposite views), its '
    'extent on that axis is assumed to be this ratio times the largest observed dimension. The '
    'report lists every assumed axis.':
        "Quand aucune photo ne borne l'objet selon un axe (vue de face unique, deux vues opposées), "
        "son étendue sur cet axe est supposée valoir ce rapport multiplié par la plus grande "
        "dimension observée. Le rapport liste chaque axe supposé.",
    'Write a contact sheet of the prepared views.':
        'Écrire une planche-contact des vues préparées.',
    'Zero123++ random seed. The same seed, weights and runtime give the same views; bit-exact '
    'reproduction across GPUs is not promised.':
        "Graine aléatoire de Zero123++. Mêmes graine, poids et environnement donnent les mêmes "
        "vues ; la reproduction bit à bit d'une carte à l'autre n'est pas promise.",
    'auto mirrors an existing view only when the measured silhouette symmetry passes the threshold. '
    'force mirrors regardless and marks the result. off never mirrors.':
        "auto ne met une vue en miroir que si la symétrie de silhouette mesurée passe le seuil. "
        "force met en miroir quoi qu'il arrive et le signale sur le résultat. off ne fait jamais "
        "de miroir.",
    'sam2 uses the local SAM 2.1 weights. classical is a GrabCut fallback that needs no model. '
    'alpha uses the alpha channel of the supplied image.':
        "sam2 utilise les poids SAM 2.1 locaux. classical est un repli GrabCut qui ne demande aucun "
        "modèle. alpha utilise le canal alpha de l'image fournie.",
    'transparent writes RGBA using the object mask. neutral composites on a flat grey. original '
    'keeps the background the backend produced.':
        "transparent écrit du RGBA avec le masque de l'objet. neutral compose sur un gris uni. "
        "original conserve le fond produit par le moteur.",
    'view_synthesis = auto generates views when the Real Coverage Score is below this value.':
        "view_synthesis = auto génère des vues quand le score de couverture réelle est sous cette "
        "valeur.",

    # -------------------------------------------------------------- proxy construction
    'A component fitted below this volumetric IoU is split (plate peeling) and refitted.':
        "Un composant ajusté sous cette IoU volumétrique est scindé (pelage en plaques) puis "
        "réajusté.",
    'Appendages shorter than this fraction of the main axis are separated from the body.':
        "Les appendices plus courts que cette fraction de l'axe principal sont séparés du corps.",
    'Axis of the main loft. X = front/back, Y = up, Z = left/right.':
        "Axe du loft principal. X = avant/arrière, Y = vertical, Z = gauche/droite.",
    'Budget preset. UltraSimple: 2-4 sections, about 20-100 triangles. Simple: 4-8 sections, '
    '100-500. Medium: 8-16 sections, 500-2000. Targets, not hard limits.':
        "Préréglage de budget. UltraSimple : 2 à 4 sections, environ 20 à 100 triangles. Simple : "
        "4 à 8 sections, 100 à 500. Medium : 8 à 16 sections, 500 à 2000. Des cibles, pas des "
        "limites strictes.",
    'Coordinate-descent passes of the final silhouette refinement.':
        "Passes de descente par coordonnées de l'affinage final sur la silhouette.",
    'Depth carving safety margin, fraction of the object size.':
        "Marge de sécurité du creusement par profondeur, en fraction de la taille de l'objet.",
    'Depth-buffer size of the occlusion test.':
        "Taille du tampon de profondeur du test d'occlusion.",
    'FitScore weights. Defaults: silhouette 1.0, depth 0.25, edge 0.35, multiview 0.4, symmetry '
    '0.15, complexity_primitive 0.004, complexity_triangle 0.002 (per 100 triangles).':
        "Poids du FitScore. Par défaut : silhouette 1.0, profondeur 0.25, contours 0.35, multivue "
        "0.4, symétrie 0.15, complexity_primitive 0.004, complexity_triangle 0.002 (pour 100 "
        "triangles).",
    'Hard-surface snapping: directions and outline edges closer than this to an axis become exactly '
    'parallel/perpendicular (degrees). 0 disables.':
        "Alignement « hard surface » : les directions et arêtes de contour plus proches que cela "
        "d'un axe deviennent exactement parallèles ou perpendiculaires (degrés). 0 désactive.",
    'Override: maximum cross-sections of the main loft.':
        'Forçage : nombre maximal de sections du loft principal.',
    'Override: maximum fitted components besides the main body (a mirrored pair counts once).':
        "Forçage : nombre maximal de composants ajustés en plus du corps principal (une paire "
        "en miroir compte pour un).",
    'Override: maximum outline vertices of an extruded polygon.':
        "Forçage : nombre maximal de sommets de contour d'un polygone extrudé.",
    'Override: smallest component kept, as a fraction of the support volume.':
        "Forçage : plus petit composant conservé, en fraction du volume support.",
    'Override: support volume resolution per axis (RAM grows with the cube).':
        "Forçage : résolution du volume support par axe (la RAM croît au cube).",
    'Override: vertices per rounded cross-section (box sections always use 4).':
        "Forçage : sommets par section arrondie (les sections boîte en utilisent toujours 4).",
    'Per-triangle penalty when choosing the primitive type of a component.':
        "Pénalité par triangle lors du choix du type de primitive d'un composant.",
    'Progressive optimisation: a section or component is kept only if FitScore improves by more '
    'than this.':
        "Optimisation progressive : une section ou un composant n'est conservé que si le FitScore "
        "s'améliore de plus que cela.",
    'Represent one-voxel-thin surfaces as zero-thickness double-sided Plane primitives.':
        "Représenter les surfaces épaisses d'un seul voxel par des primitives Plane d'épaisseur "
        "nulle, visibles des deux côtés.",
    'Thinnest allowed plate, relative to its largest outline span.':
        'Plaque la plus fine autorisée, relativement à sa plus grande dimension de contour.',
    'Vertex welding distance of proxy_geometry.obj, relative to target_size.':
        'Distance de soudure des sommets de proxy_geometry.obj, relative à target_size.',
    'Weight of mirrored real views, multiplied by the symmetry confidence.':
        'Poids des vues réelles mises en miroir, multiplié par la confiance de symétrie.',
    'Weight of real pictures.': 'Poids des photos réelles.',
    'Weight of synthetic views (recommended 0.3 to 0.6).':
        'Poids des vues synthétiques (0,3 à 0,6 recommandé).',

    # ------------------------------------------------------------- texturing and UV
    'A camera may texture a face only when cos(angle) exceeds this.':
        "Une caméra ne peut texturer une face que si cos(angle) dépasse cette valeur.",
    'Also write a GLB carrying the UV layout and the generated PBR material.':
        'Écrire aussi un GLB portant le dépliage UV et le matériau PBR généré.',
    'Bake a texture atlas with xatlas and moderngl instead of vertex colours. Needs a working '
    'OpenGL context and output_format obj.':
        "Cuire un atlas de texture avec xatlas et moderngl au lieu de couleurs par sommet. "
        "Nécessite un contexte OpenGL fonctionnel et output_format obj.",
    'BaseColor atlas size in pixels (square).':
        "Taille de l'atlas BaseColor en pixels (carré).",
    'Brightens concave areas to attenuate shading baked into the source colour. Geometric '
    'heuristic, not an inverse-rendering de-lighting.':
        "Éclaircit les zones concaves pour atténuer l'ombrage cuit dans la couleur source. "
        "Heuristique géométrique, pas un dé-éclairage par rendu inverse.",
    'Cameras mixed per face when texture_blend = blend.':
        'Nombre de caméras mélangées par face quand texture_blend = blend.',
    'Constant metallic, and lower bound of the estimated metallic.':
        'Métallicité constante, et borne basse de la métallicité estimée.',
    'Constant roughness, and centre of the estimated roughness.':
        'Rugosité constante, et centre de la rugosité estimée.',
    'Square size in texels of every generated map.':
        'Taille carrée, en texels, de chaque carte générée.',
    'Texels of nearest-neighbour padding grown around each UV island.':
        "Texels de remplissage au plus proche voisin ajoutés autour de chaque île UV.",
    'TextureViewScore factor of mirrored real pictures.':
        'Facteur TextureViewScore des photos réelles mises en miroir.',
    'TextureViewScore factor of real pictures.': 'Facteur TextureViewScore des photos réelles.',
    'TextureViewScore factor of synthetic views.': 'Facteur TextureViewScore des vues synthétiques.',
    'auto keeps existing UV and unwraps only when there is none; keep fails without UV; unwrap '
    'rebuilds an atlas with xatlas and falls back to grid if xatlas fails; grid gives every '
    'triangle its own cell, which never overlaps but wastes texels.':
        "auto conserve les UV existantes et ne déplie que s'il n'y en a pas ; keep échoue sans UV ; "
        "unwrap reconstruit un atlas avec xatlas et se replie sur grid en cas d'échec ; grid donne "
        "à chaque triangle sa propre case, ce qui ne se recouvre jamais mais gaspille des texels.",
    'best = best camera per face. blend = weighted multi-view blend of the best cameras.':
        "best = la meilleure caméra par face. blend = mélange multivue pondéré des meilleures "
        "caméras.",
    'constant writes metallic_value; estimate applies the documented colour heuristic; source '
    'resamples the metallic-roughness texture of the mesh.':
        "constant écrit metallic_value ; estimate applique l'heuristique de couleur documentée ; "
        "source rééchantillonne la texture métallicité-rugosité du maillage.",
    'estimate applies the documented detail heuristic; constant writes roughness_value; source '
    'resamples the mesh metallic-roughness texture.':
        "estimate applique l'heuristique de détail documentée ; constant écrit roughness_value ; "
        "source rééchantillonne la texture métallicité-rugosité du maillage.",
    'from_source keeps the source transparency; opaque writes white; from_coverage marks the '
    'texels covered by a triangle, without padding.':
        "from_source conserve la transparence de la source ; opaque écrit du blanc ; from_coverage "
        "marque les texels couverts par un triangle, sans remplissage.",
    'xatlas chart padding in pixels.': "Marge des chartes xatlas, en pixels.",
    'Lanczos resampling only. This Tool performs no super resolution.':
        "Rééchantillonnage Lanczos uniquement. Cet outil ne fait aucune super-résolution.",

    # ----------------------------------------------------------- meshes and formats
    'Approximate remeshing vertex target; -1 preserves upstream default.':
        "Cible approximative de sommets du remaillage ; -1 conserve la valeur par défaut amont.",
    'Carry materials and textures over to the result when the format allows it.':
        'Reporter les matériaux et les textures sur le résultat quand le format le permet.',
    'Edits applied in order.': 'Modifications appliquées dans l\'ordre.',
    'Embed the textures in the file when the format allows it.':
        'Intégrer les textures dans le fichier quand le format le permet.',
    'Format of the written mesh.': 'Format du maillage écrit.',
    'GLB carries vertex colours. Baking a texture atlas requires obj.':
        "Le GLB porte des couleurs par sommet. Cuire un atlas de texture demande obj.",
    'GLB triangulates faces even after quad remeshing.':
        'Le GLB triangule les faces même après un remaillage quad.',
    'Mesh path inside the configured mesh root: GLB, GLTF, OBJ, PLY, STL, OFF.':
        "Chemin du maillage dans la racine de maillages configurée : GLB, GLTF, OBJ, PLY, STL, OFF.",
    'Mesh to convert.': 'Maillage à convertir.',
    'Mesh to edit (GLB, glTF, OBJ, PLY, STL, OFF).':
        'Maillage à éditer (GLB, glTF, OBJ, PLY, STL, OFF).',
    'Target format.': 'Format cible.',
    'Triangulate faces during the conversion.': 'Trianguler les faces pendant la conversion.',
    'Uniform scale applied during the conversion.':
        'Facteur d\'échelle uniforme appliqué pendant la conversion.',

    # ------------------------------------------------------------------- input paths
    'Chemin relatif dans data/inputs, importe depuis ImGui.':
        "Chemin relatif dans data/inputs, importé depuis l'interface.",
    'Image path: absolute local path or relative to data/inputs. Automatically copied into the '
    'private job workspace; no manual import required. PNG/JPEG/WebP, at most 32 MiB and 40 '
    'megapixels. Optional when subject_set is given.':
        "Chemin d'image : chemin local absolu ou relatif à data/inputs. Copié automatiquement dans "
        "l'espace de travail privé du job ; aucun import manuel n'est nécessaire. PNG/JPEG/WebP, "
        "32 Mio et 40 mégapixels au maximum. Facultatif quand subject_set est donné.",
    'PNG/JPEG/WEBP inside CYTOOLS_SPAR3D_INPUT_ROOT (default: inputs). Optional when subject_set '
    'is given.':
        'PNG/JPEG/WEBP dans CYTOOLS_SPAR3D_INPUT_ROOT (par défaut : inputs). Facultatif quand '
        'subject_set est donné.',
    'PNG/JPEG/WEBP inside CYTOOLS_TRIPOSR_INPUT_ROOT (default: inputs). Optional when subject_set '
    'is given.':
        'PNG/JPEG/WEBP dans CYTOOLS_TRIPOSR_INPUT_ROOT (par défaut : inputs). Facultatif quand '
        'subject_set est donné.',
    'By default private input copies are deleted after the worker stops, including '
    'failure/cancellation. Enable only to retain them for debugging. Original files and generated '
    'outputs are never deleted.':
        "Par défaut, les copies privées des entrées sont supprimées après l'arrêt du worker, y "
        "compris en cas d'échec ou d'annulation. À n'activer que pour les conserver à des fins de "
        "débogage. Les fichiers d'origine et les résultats générés ne sont jamais supprimés.",
    'Private input copies are deleted when the worker stops, including on failure and '
    'cancellation. Original files and generated results are never deleted.':
        "Les copies privées des entrées sont supprimées à l'arrêt du worker, y compris en cas "
        "d'échec et d'annulation. Les fichiers d'origine et les résultats générés ne sont jamais "
        "supprimés.",

    # ------------------------------------------------------------ engines, workflows
    'Build the CUDA variant or the CPU variant when the engine offers one.':
        "Construire la variante CUDA ou la variante CPU quand le moteur en propose une.",
    'Engine to install.': 'Moteur à installer.',
    'Folder to process instead of a single file.':
        "Dossier à traiter au lieu d'un fichier unique.",
    'GPU index.': 'Indice du GPU.',
    'Glob applied inside the folder.': 'Motif glob appliqué dans le dossier.',
    'Guidance used for the normal pass only.':
        'Guidage utilisé pour la passe de normales uniquement.',
    'Include the full step list of every workflow.':
        'Inclure la liste complète des étapes de chaque workflow.',
    'Inline workflow document, instead of a saved name.':
        "Document de workflow en ligne, au lieu d'un nom enregistré.",
    'Input of the first step.': 'Entrée de la première étape.',
    'Keep the output of every step, not only the last one.':
        'Conserver la sortie de chaque étape, pas seulement la dernière.',
    'NVIDIA device index, ignored when device is cpu.':
        'Indice de la carte NVIDIA, ignoré quand device vaut cpu.',
    'Name of a workflow saved in data/workflows.':
        'Nom d\'un workflow enregistré dans data/workflows.',
    'Name of the workflow.': 'Nom du workflow.',
    'Only fetch or update the upstream sources.':
        'Récupérer ou mettre à jour uniquement les sources amont.',
    'Only the models present on disk.': 'Uniquement les modèles présents sur le disque.',
    'Reinstall even when the engine reports itself as installed.':
        "Réinstaller même quand le moteur se déclare installé.",
    'Replace an existing workflow with the same name.':
        'Remplacer un workflow existant portant le même nom.',
    'Restrict the report to one engine.': 'Restreindre le rapport à un seul moteur.',
    'Restrict to one family.': 'Restreindre à une seule famille.',
    'What a folder given as input means. each: the workflow runs once per file. together: it '
    'runs once, and its first step receives every file as one list: the photographs of one '
    'subject, whose roles prepare_subject reads from the file names.':
        "Ce que signifie un dossier donné en entrée. each : le workflow s'exécute une fois par "
        "fichier. together : il s'exécute une seule fois, et sa première étape reçoit tous les "
        "fichiers en une liste : les photos d'un même sujet, dont prepare_subject lit le rôle dans "
        "les noms de fichiers.",
    'Overrides the input mode of the workflow: each (one run per file) or together (one run with '
    'every file). Empty: the workflow decides.':
        "Remplace le mode d'entrée du workflow : each (une exécution par fichier) ou together (une "
        "seule exécution avec tous les fichiers). Vide : le workflow décide.",
    'Stop the whole workflow at the first failed step.':
        "Arrêter tout le workflow à la première étape en échec.",
    'The workflow document.': 'Le document du workflow.',
    'Write a JSON report with the state before and after every step.':
        "Écrire un rapport JSON avec l'état avant et après chaque étape.",
    'Also start each installed engine to report its real torch and device.':
        "Démarrer aussi chaque moteur installé pour rapporter son torch et son périphérique réels.",
}
