"""French for the field titles, and for the fields nested inside lists of objects.

The parameter editor labels a field with its schema title first and only falls back to the
field name, so these are the words actually on screen. They were missed until the collector in
``update_locales.py`` learned to read titles and nested fields.
"""

TITLES = {
    'Seed (-1 = random)': 'Graine (-1 = aléatoire)',
    'A preset viewpoint, or Custom to use the angles below.':
        "Un point de vue prédéfini, ou Custom pour utiliser les angles ci-dessous.",
    'Absolute face count for decimate; 0 uses "value" as a ratio.':
        'Nombre absolu de faces pour la décimation ; 0 utilise « value » comme rapport.',
    'Action': 'Action',
    'Allow mirrored views': 'Autoriser les vues en miroir',
    'Allow resampling above the native resolution':
        'Autoriser le rééchantillonnage au-dessus de la résolution native',
    'Also generate view-space normal maps':
        "Générer aussi des cartes de normales dans l'espace de la vue",
    'Angles in degrees. Azimuth 0 looks at the front of the object and positive values move the '
    'camera towards the object right side, so +90 is Right, -90 is Left and 180 is Rear. Positive '
    'elevation places the camera above the object.':
        "Angles en degrés. L'azimut 0 regarde l'avant de l'objet et les valeurs positives déplacent "
        "la caméra vers son côté droit : +90 = droite, -90 = gauche, 180 = arrière. Une élévation "
        "positive place la caméra au-dessus de l'objet.",
    'Axis': 'Axe',
    'Axis the edit applies to.': "Axe auquel s'applique la modification.",
    'Azimuth': 'Azimut',
    'Back image': 'Image de dos',
    'Backend id, when the operation supports several.':
        "Identifiant du moteur, quand l'opération en accepte plusieurs.",
    'Box': 'Boîte',
    'Camera roll in degrees, 0 when the horizon is level.':
        "Roulis de la caméra en degrés, 0 quand l'horizon est droit.",
    'Complexity primitive': 'Complexité par primitive',
    'Complexity triangle': 'Complexité par triangle',
    'Confidence weight of this real view (default 1.0).':
        'Poids de confiance de cette vue réelle (1.0 par défaut).',
    'Continue on error': "Continuer en cas d'erreur",
    'Declared viewpoint': 'Point de vue déclaré',
    'Declaring the viewpoint is exact and is the recommended input. Auto runs the automatic '
    'estimator, which only measures an azimuth for narrow baselines and reports its confidence.':
        "Déclarer le point de vue est exact et c'est l'entrée recommandée. auto lance "
        "l'estimateur automatique, qui ne mesure un azimut que pour des écarts faibles entre vues "
        "et indique sa confiance.",
    'Degrees above (+) or below (-) the horizontal plane.':
        'Degrés au-dessus (+) ou au-dessous (-) du plan horizontal.',
    "Degrees around the vertical axis: 0 = camera in front of the object, 90 = camera on the "
    "object's right side, 180 = behind. Overrides label.":
        "Degrés autour de l'axe vertical : 0 = caméra devant l'objet, 90 = caméra sur son côté "
        "droit, 180 = derrière. Remplace le libellé.",
    'Depth': 'Profondeur',
    'Diffusion steps': 'Pas de diffusion',
    'Edge': 'Contours',
    'Edit to apply.': 'Modification à appliquer.',
    'Field of view of the FULL picture along its longest side, in degrees. 0 = orthographic '
    'drawing. Default 35.':
        "Champ de vision de l'image ENTIÈRE sur son plus grand côté, en degrés. 0 = dessin "
        "orthographique. 35 par défaut.",
    'Field of view of the generator camera (Zero123++ v1.2: 30).':
        'Champ de vision de la caméra du générateur (Zero123++ v1.2 : 30).',
    'First azimuth': 'Premier azimut',
    'Fov': 'Champ de vision',
    'Front image': 'Image de face',
    'Guidance scale': 'Échelle de guidage',
    'Horizontal field of view': 'Champ de vision horizontal',
    'Horizontal field of view in degrees, when it is known.':
        "Champ de vision horizontal en degrés, quand il est connu.",
    'Id': 'Identifiant',
    'Identifier of this step inside the workflow.': "Identifiant de cette étape dans le workflow.",
    'Identifier used in the View Set; the file stem is used when it is empty.':
        "Identifiant utilisé dans le jeu de vues ; le nom du fichier sert s'il est vide.",
    'Image': 'Image',
    'Image path: an absolute local path, or a path relative to data/inputs. The file is copied '
    'into the private job workspace automatically; no manual import is required. PNG, JPEG or '
    'WebP, at most 48 MiB and 60 megapixels.':
        "Chemin d'image : un chemin local absolu, ou relatif à data/inputs. Le fichier est copié "
        "automatiquement dans l'espace de travail privé du job ; aucun import manuel n'est "
        "nécessaire. PNG, JPEG ou WebP, 48 Mio et 60 mégapixels au maximum.",
    'Image to mirror': 'Image à mettre en miroir',
    'Include Top and Bottom': 'Inclure le dessus et le dessous',
    'Index in `images` of the real picture the view was generated from.':
        "Indice, dans `images`, de la photo réelle d'où la vue a été générée.",
    'Input field': "Champ d'entrée",
    'Input images': "Images d'entrée",
    'Input mode': "Mode d'entrée",
    'Input to': 'Entrée vers',
    'Iterations for smooth and subdivide.': 'Itérations pour lisser et subdiviser.',
    'Keep going when this step fails: what it received is handed on, as when it is '
    'switched off, and the failure is listed in the report.':
        "Continuer quand cette étape échoue : ce qu'elle a reçu est transmis, comme lorsqu'elle "
        "est désactivée, et l'échec figure dans le rapport.",
    'Keep input copies after processing': 'Garder les copies des entrées après traitement',
    'Keep the private input copies after processing':
        'Garder les copies privées des entrées après traitement',
    'Label': 'Libellé',
    'Left image': 'Image de gauche',
    'Main value: factor for scale, angle in degrees for rotate, target ratio for decimate, '
    'distance for weld.':
        "Valeur principale : facteur pour scale, angle en degrés pour rotate, rapport cible pour "
        "decimate, distance pour weld.",
    'Mask': 'Masque',
    'Maximum generated views': 'Nombre maximal de vues générées',
    'Mesh OBJ / PLY / STL': 'Maillage OBJ / PLY / STL',
    'Multiview': 'Multivue',
    'Name of the produced view; a preset name is used when empty.':
        "Nom de la vue produite ; un nom prédéfini est utilisé s'il est vide.",
    'Never replace a real view by a generated one':
        'Ne jamais remplacer une vue réelle par une vue générée',
    'Normal guidance scale': 'Échelle de guidage des normales',
    'Object fill ratio of the conditioning image':
        "Taux de remplissage de l'objet dans l'image de conditionnement",
    'Operation id, as declared by this manifest.':
        "Identifiant de l'opération, tel que ce manifeste le déclare.",
    'Optional SAM prompt box [x0, y0, x1, y1] normalised to the picture, when the object is not '
    'the salient central subject.':
        "Boîte d'invite SAM facultative [x0, y0, x1, y1], normalisée à l'image, quand l'objet "
        "n'est pas le sujet central évident.",
    'Optional human view label. Internally converted to continuous angles. For Top/Bottom the '
    'in-plane orientation is searched automatically unless azimuth is given.':
        "Libellé de vue facultatif. Converti en angles continus en interne. Pour Top/Bottom, "
        "l'orientation dans le plan est cherchée automatiquement sauf si l'azimut est donné.",
    'Optional mask of the synthetic view.': 'Masque facultatif de la vue synthétique.',
    'Optional object mask (white = object). Replaces automatic segmentation for this picture.':
        "Masque d'objet facultatif (blanc = objet). Remplace la segmentation automatique pour "
        "cette photo.",
    'Output field of that step to use as the input.':
        "Champ de sortie de cette étape à utiliser comme entrée.",
    'Output resolution': 'Résolution de sortie',
    'Parameter of this step that receives it; empty uses the field the operation normally reads '
    'its input from.':
        "Paramètre de cette étape qui la reçoit ; vide = le champ où l'opération lit normalement "
        "son entrée.",
    'Parameters': 'Paramètres',
    'Parameters of the operation.': "Paramètres de l'opération.",
    'Picture of the object (PNG, JPEG, WebP, BMP, TIFF; 64 MiB max). An absolute path on the Tool '
    'host is accepted and imported automatically into the private job workspace; an alpha channel '
    'is used as the object mask.':
        "Photo de l'objet (PNG, JPEG, WebP, BMP, TIFF ; 64 Mio max). Un chemin absolu sur la "
        "machine de l'outil est accepté et importé automatiquement dans l'espace de travail privé "
        "du job ; un canal alpha sert de masque d'objet.",
    'Preset': 'Préréglage',
    'Real size in mm (0 = native)': 'Taille réelle en mm (0 = native)',
    'Relative azimuth': 'Azimut relatif',
    'Requested absolute elevation, degrees.': 'Élévation absolue demandée, en degrés.',
    'Requested azimuth relative to the source picture, degrees.':
        "Azimut demandé par rapport à la photo source, en degrés.",
    'Requested views': 'Vues demandées',
    'Right image': 'Image de droite',
    'Ring elevation': "Élévation de l'anneau",
    'Roll': 'Roulis',
    'Run this step.': 'Exécuter cette étape.',
    'Shape guidance (0 = recipe)': 'Guidage de la forme (0 = recette)',
    'Silhouette': 'Silhouette',
    'Size threshold: minimum component size for remove_floaters, maximum hole perimeter for '
    'fill_holes.':
        "Seuil de taille : taille minimale d'un composant pour remove_floaters, périmètre maximal "
        "d'un trou pour fill_holes.",
    'Step id whose output feeds this step; empty means the workflow input.':
        "Identifiant de l'étape dont la sortie alimente celle-ci ; vide = l'entrée du workflow.",
    'Steps Shape (0 = recipe)': 'Pas de forme (0 = recette)',
    'Steps Structure (0 = recipe)': 'Pas de structure (0 = recette)',
    'Steps Texture (0 = recipe)': 'Pas de texture (0 = recette)',
    'Synthetic view produced by a novel-view model (Zero123++, SyncDreamer, Wonder3D...). Never '
    'trusted like a photograph.':
        "Vue synthétique produite par un modèle de nouvelles vues (Zero123++, SyncDreamer, "
        "Wonder3D...). Jamais considérée comme une photo.",
    'Target faces (0 = recipe)': 'Faces cibles (0 = recette)',
    'Targetfaces': 'Faces cibles',
    'Texture guidance (0 = recipe)': 'Guidage de la texture (0 = recette)',
    'Texture size (0 = recipe)': 'Taille de texture (0 = recette)',
    'Three numbers for translate, scale or rotate per axis.':
        'Trois nombres pour translate, scale ou rotate, par axe.',
    'Threshold': 'Seuil',
    'Use the images even when they may show different objects':
        "Utiliser les images même si elles montrent peut-être des objets différents",
    'Variants per view': 'Variantes par vue',
    'Vector': 'Vecteur',
    'Views per ring': 'Vues par anneau',
    'Views to validate': 'Vues à valider',
    'Weight': 'Poids',
    'Weight of this synthetic view (default generated_view_weight).':
        'Poids de cette vue synthétique (generated_view_weight par défaut).',
    'What the workflow does.': 'Ce que fait le workflow.',
}
