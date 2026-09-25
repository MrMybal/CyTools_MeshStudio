"""French for the LocalMesh+ chain: generated side views, texturing a remeshed model, and the
extra inputs of a workflow step."""

LOCALMESH_PLUS = {
    'Complete the subject with generated views (Wonder3D)':
        'Compléter le sujet avec des vues générées (Wonder3D)',
    'From one picture, generate the right, left and back views with Wonder3D around the '
    'vertical axis of the picture, then cut the four views out at one common scale: a subject '
    'set for the four-view path of LocalMesh. Only for a level front view: with a three-quarter '
    'or top view the generated views are tilted and the fusion deforms the object. The '
    'generated views are marked as such, and LocalMesh measures their angles itself.':
        "À partir d'une image, génère les vues de droite, de gauche et de dos avec Wonder3D autour "
        "de l'axe vertical de l'image, puis détoure les quatre vues à une échelle commune : un jeu "
        "de vues pour la voie à quatre vues de LocalMesh. Uniquement pour une vue de face bien "
        "droite : avec une vue de trois quarts ou de dessus, les vues générées sont inclinées et la "
        "fusion déforme l'objet. Les vues générées sont marquées comme telles, et LocalMesh mesure "
        "lui-même leurs angles.",
    'Texture a mesh for its own topology (LocalMesh)':
        'Texturer un maillage pour sa propre topologie (LocalMesh)',
    'Give a remeshed model — QuadWild quads, a retopology, any mesh aligned with the reference — '
    'a texture made for that exact topology. "generate" asks TRELLIS.2 to generate it on this mesh '
    'from the reference picture, as LocalMesh does on its own mesh; "transfer" re-projects the '
    'texture of the detailed model instead, with no model. The detailed model, when given, is also '
    'baked into a normal map. Quads are kept in the OBJ; the GLB is triangulated, as glTF '
    'requires.':
        "Donne à un maillage remaillé — quads QuadWild, retopologie, tout maillage aligné sur la "
        "référence — une texture faite pour cette topologie précise. « generate » demande à "
        "TRELLIS.2 de la générer sur ce maillage à partir de l'image de référence, comme LocalMesh "
        "le fait sur son propre maillage ; « transfer » reprojette plutôt la texture du modèle "
        "détaillé, sans aucun modèle. Le modèle détaillé, s'il est fourni, est aussi cuit en "
        "normal map. Les quads sont conservés dans l'OBJ ; le GLB est triangulé, comme glTF "
        "l'impose.",
    'Reference picture of the subject (the front).': 'Image de référence du sujet (la face).',
    'Folder produced by prepare_subject; its front cut-out is used.':
        'Dossier produit par prepare_subject ; son détourage de face est utilisé.',
    'Wonder3D random seed.': 'Graine aléatoire de Wonder3D.',
    'Diffusion steps of Wonder3D.': 'Pas de diffusion de Wonder3D.',
    'Guidance scale of Wonder3D.': 'Échelle de guidage de Wonder3D.',
    'Mesh to texture (OBJ keeps its quads; GLB, PLY, STL are read as triangles). Y-up, facing like '
    'the LocalMesh output.':
        "Maillage à texturer (l'OBJ garde ses quads ; GLB, PLY et STL sont lus en triangles). "
        "Axe vertical Y, orienté comme la sortie de LocalMesh.",
    'Folder produced by prepare_subject or complete_subject: the reference cut-out, and the other '
    'views for multi-view texturing.':
        "Dossier produit par prepare_subject ou complete_subject : le détourage de référence, et "
        "les autres vues pour la texturation multivue.",
    'Reference picture, when there is no subject set; it is cut out here.':
        "Image de référence, quand il n'y a pas de jeu de vues ; elle est détourée ici.",
    'Detail mesh': 'Modèle détaillé',
    'Detailed model aligned with this mesh (the LocalMesh output): baked into the normal map, and '
    'the source of "transfer".':
        "Modèle détaillé aligné sur ce maillage (la sortie de LocalMesh) : cuit dans la normal map, "
        "et source du mode « transfer ».",
    'Texture source': 'Source de la texture',
    'generate: TRELLIS.2 generates the texture on this mesh. transfer: the texture of the detailed '
    'model is re-projected.':
        "generate : TRELLIS.2 génère la texture sur ce maillage. transfer : la texture du modèle "
        "détaillé est reprojetée.",
    'Side of the atlas in pixels.': "Côté de l'atlas, en pixels.",
    'Multiview texture': 'Texture multivue',
    'Guide the texture with every view of the subject set, not only the front. Experimental: never '
    'measured upstream.':
        "Guider la texture avec toutes les vues du jeu, pas seulement la face. Expérimental : "
        "jamais mesuré en amont.",
    'Texture model grid: 512 uses the 512 model, 1024 the 1024 one.':
        'Grille du modèle de texture : 512 utilise le modèle 512, 1024 le modèle 1024.',
    'Sampling steps of the texture model.': "Pas d'échantillonnage du modèle de texture.",
    'Guidance of the texture model.': 'Guidage du modèle de texture.',
    'Seed (-1 draws one).': 'Graine (-1 en tire une).',
    'Up axis of the input mesh.': "Axe vertical du maillage d'entrée.",
    'Uv padding': 'Marge UV',
    'Padding between UV islands, in texels.': 'Marge entre les îles UV, en texels.',
    # refine_mesh
    'Refine a mesh with TRELLIS.2 (LocalMesh)': 'Raffiner un maillage avec TRELLIS.2 (LocalMesh)',
    "Regenerate the geometric detail of an existing mesh, keeping its overall shape: the mesh is "
    "encoded, its occupancy becomes the structure, and TRELLIS.2 samples the shape again on it "
    "from the reference picture, up to the 1536 grid. LocalMesh's own cleaning chain then closes "
    "the holes, removes the debris and brings it to the face budget, in the frame and at the "
    "scale of the input. Geometry only: texture the result with \"Texture a mesh for its own "
    "topology\".":
        "Régénère le détail géométrique d'un maillage existant en gardant sa forme d'ensemble : le "
        "maillage est encodé, son occupation devient la structure, et TRELLIS.2 échantillonne à "
        "nouveau la forme dessus à partir de l'image de référence, jusqu'à la grille 1536. La "
        "chaîne de nettoyage de LocalMesh bouche ensuite les trous, retire les débris et ramène "
        "au budget de faces, dans le repère et à l'échelle de l'entrée. Géométrie seule : "
        "texturer le résultat avec « Texturer un maillage pour sa propre topologie ».",
    'Mesh to refine, Y-up and facing like the LocalMesh output.':
        'Maillage à raffiner, axe vertical Y, orienté comme la sortie de LocalMesh.',
    'Folder produced by prepare_subject or complete_subject: the reference cut-out.':
        'Dossier produit par prepare_subject ou complete_subject : le détourage de référence.',
    'Grid the shape is sampled on again. 1536 needs a 24 GB card and is lowered by steps of 128 '
    'when the shape has too many tokens.':
        "Grille sur laquelle la forme est ré-échantillonnée. 1536 demande une carte de 24 Go et "
        "descend par pas de 128 quand la forme a trop de tokens.",
    'Face budget of the result; 0 takes the recipe of that grid (250 000 on 1024, 400 000 on 1536).':
        'Budget de faces du résultat ; 0 prend la recette de cette grille (250 000 en 1024, '
        '400 000 en 1536).',
    'Use all views': 'Utiliser toutes les vues',
    'Condition on every view of the subject set, not only the front. Experimental.':
        'Conditionner sur toutes les vues du jeu, pas seulement la face. Expérimental.',
    'Sampling steps of the shape model.': "Pas d'échantillonnage du modèle de forme.",
    "Shape guidance; 0 keeps the weights' own value.":
        'Guidage de la forme ; 0 garde la valeur des poids.',
    # Hi3DGen
    'Image to mesh (Hi3DGen)': 'Image vers maillage (Hi3DGen)',
    'Hi3DGen (Stable-X): the picture becomes a sharp normal map (StableNormal YOSO), and a TRELLIS '
    'v1 retrained on normal maps turns that normal map into a mesh. Geometry only, on a 256 grid, '
    'in the same frame as the LocalMesh output: texture it with "Texture a mesh for its own '
    'topology", or regenerate its detail on the 1536 grid first with "Refine a mesh". A picture '
    'without transparency is cut out first with the shared front end.':
        "Hi3DGen (Stable-X) : l'image devient une carte de normales nette (StableNormal YOSO), "
        "puis un TRELLIS v1 ré-entraîné sur des normales transforme cette carte en maillage. "
        "Géométrie seule, sur une grille 256, dans le même repère que la sortie de LocalMesh : la "
        "texturer avec « Texturer un maillage pour sa propre topologie », ou régénérer d'abord son "
        "détail sur la grille 1536 avec « Raffiner un maillage ». Une image sans transparence est "
        "d'abord détourée par le front-end partagé.",
    'Picture of the subject. With an alpha channel it is used as it is; otherwise it is cut out '
    'with BiRefNet first.':
        "Image du sujet. Avec un canal alpha, elle est utilisée telle quelle ; sinon elle est "
        "d'abord détourée par BiRefNet.",
    'Folder produced by prepare_subject or complete_subject: its front cut-out is used.':
        'Dossier produit par prepare_subject ou complete_subject : son détourage de face est utilisé.',
    'Normal map resolution': 'Résolution de la carte de normales',
    'Resolution of the normal map estimation.': "Résolution de l'estimation des normales.",
    'Structure steps': 'Pas de structure',
    'Sampling steps of the sparse structure.': "Pas d'échantillonnage de la structure éparse.",
    'Structure guidance': 'Guidage de la structure',
    'Guidance of the sparse structure.': 'Guidage de la structure éparse.',
    'Detail steps': 'Pas de détail',
    'Sampling steps of the structured latent.': "Pas d'échantillonnage du latent structuré.",
    'Detail guidance': 'Guidage du détail',
    'Guidance of the structured latent.': 'Guidage du latent structuré.',
    'Put the base of the object on the ground plane.': "Poser la base de l'objet sur le sol.",
    # workflow step: extra inputs
    'Extra inputs': 'Entrées supplémentaires',
    'More values taken from earlier steps, when one input is not enough: a retexturing step needs '
    'the new topology, the detailed original and the prepared views.':
        "D'autres valeurs prises dans des étapes précédentes, quand une seule entrée ne suffit "
        "pas : une étape de retexturation a besoin de la nouvelle topologie, de l'original "
        "détaillé et des vues préparées.",
    'From': 'Depuis',
    'Earlier step id, or @input for the workflow input.':
        "Identifiant d'une étape précédente, ou @input pour l'entrée du workflow.",
    'Field': 'Champ',
    'Output field of that step; empty takes its main output.':
        'Champ de sortie de cette étape ; vide = sa sortie principale.',
    'To': 'Vers',
    'Parameter of this step that receives it.': 'Paramètre de cette étape qui la reçoit.',
    'More inputs': "Plus d'entrées",
    'Workflow input': 'Entrée du workflow',
    'Add an input': 'Ajouter une entrée',
}
