---
id: operation-texture-pbr
title: texture_pbr
description: Bake Base Color, Metallic, Roughness et Alpha dans un atlas UV, plus la carte metallic-roughness glTF. La couleur portée par le maillage est bake; les canaux que le maillage ne porte pas sont dérivés avec des heuristiques…
section: Référence
order: 200
parent: operations
sourceRevision: f0a5d4e2b470abc6
---

Bake Base Color, Metallic, Roughness et Alpha dans un atlas UV, plus la carte metallic-roughness glTF. La couleur portée par le maillage est bake; les canaux que le maillage ne porte pas sont dérivés avec des heuristiques déterministes documentées, pas générés par un modèle.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `mesh_file` | `string` | Oui | Chemin du maillage à l'intérieur du répertoire de maillage configuré: GLB, GLTF, OBJ, PLY, STL, OFF.  |
| `resolution` | `value` | Non | Taille du carré en texels pour chaque carte générée. `default=1024`, `enum=[512, 1024, 2048, 4096]` |
| `uv_mode` | `value` | Non | auto conserve les existants UV et déplie seulement si aucun n'existe ; keep échoue sans UV ; unwrap reconstruit un atlas avec xatlas et tombe en reback sur grid si xatlas échoue ; grid donne à chaque triangle sa propre cellule, qui ne s'overlappe jamais mais gaspille des texels. `default="auto"`, `enum=["auto", "keep", "unwrap", "grid"]` |
| `padding_pixels` | `integer` | Non | Texels de l'padding par interpolation du voisin le plus proche ajoutés autour de chaque île UV. `default=8`, `minimum=0`, `maximum=64` |
| `cavity_delight` | `number` | Non | Agrandit les zones concaves pour atténuer l'ombrage intégré dans la couleur source. Heuristique géométrique, pas une dé-ombrage inverse de rendu. `default=0.0`, `minimum=0`, `maximum=1` |
| `metallic_mode` | `value` | Non | constant écrit metallic_value ; estimate applique la heuristique de couleur documentée ; source resample la texture metallic-roughness de la maille. `default="constant"`, `enum=["constant", "estimate", "source"]` |
| `metallic_value` | `number` | Non | Constant metallic, et bornes inférieures de l'estimation de metallic. `default=0.0`, `minimum=0`, `maximum=1` |
| `roughness_mode` | `value` | Non | estimate applique la heuristique de détail documentée ; constant écrit roughness_value ; source resample la texture metallic-roughness de la maille. `default="estimate"`, `enum=["estimate", "constant", "source"]` |
| `roughness_value` | `number` | Non | Constant roughness, et centre de l'estimation de roughness. `default=0.5`, `minimum=0`, `maximum=1` |
| `alpha_mode` | `value` | Non | from_source conserve la transparence de la source ; opaque écrit blanc ; from_coverage marque les texels couverts par un triangle, sans padding. `default="from_source"`, `enum=["from_source", "opaque", "from_coverage"]` |
| `export_glb` | `boolean` | Non | Écrivez également un GLB qui transporte le UV de disposition et le matériel généré PBR. `default=true` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `base_color_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `metallic_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `roughness_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `alpha_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `metallic_roughness_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `material_mesh_file` | `string` | Oui | Vide lorsque export_glb est faux.  |
| `report_file` | `string` | Oui | Voir les paramètres de l’opération.  |
| `resolution` | `value` | Oui | Voir les paramètres de l’opération. `enum=[512, 1024, 2048, 4096]` |
| `vertices` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=1` |
| `faces` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=1` |
| `uv_source` | `value` | Oui | Voir les paramètres de l’opération. `enum=["existing", "xatlas", "grid"]` |
| `padding_pixels` | `integer` | Oui | Padding appliqué ; le mode grille le réduit pour s'adapter à ses cellules. `minimum=0`, `maximum=64` |
| `color_source` | `value` | Oui | Voir les paramètres de l’opération. `enum=["texture", "vertex_colors", "base_color_factor", "none"]` |
| `metallic_mode` | `value` | Oui | Voir les paramètres de l’opération. `enum=["constant", "estimate", "source"]` |
| `roughness_mode` | `value` | Oui | Voir les paramètres de l’opération. `enum=["estimate", "constant", "source"]` |
| `alpha_mode` | `value` | Oui | Voir les paramètres de l’opération. `enum=["from_source", "opaque", "from_coverage"]` |
| `texel_coverage` | `number` | Oui | Partie de texels couverts par un triangle, avant padding. `minimum=0`, `maximum=1` |
| `padded_coverage` | `number` | Oui | Partie de texels contenant une valeur après padding. `minimum=0`, `maximum=1` |
| `stamped_faces` | `integer` | Oui | Triangles plus petits qu'un texel, forcés sur un seul texel. `minimum=0` |
| `source_texture_size` | `array` | Oui | Voir les paramètres de l’opération.  |
| `worker_memory_bytes` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `memory_measurement` | `string` | Oui | Voir les paramètres de l’opération.  |
| `formulas` | `object` | Oui | Voir les paramètres de l’opération.  |
| `color_space_note` | `string` | Oui | Voir les paramètres de l’opération.  |
| `warnings` | `array` | Oui | Voir les paramètres de l’opération.  |
| `timings` | `object` | Oui | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : `pbrbake`
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation texture_pbr
```
