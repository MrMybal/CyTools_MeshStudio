---
id: operations
title: Automatisation et API
description: Connectez un client et consultez les opérations disponibles.
section: Référence
order: 80
parent: overview
sourceRevision: 52eace874db50eec
---

## Ligne de commande {#cli}

Depuis la racine de l’application, utilisez son interpréteur Python privé. `describe` et `list-operations` examinent le contrat public.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe
runtime\python\Scripts\python.exe app\tool.py list-operations
runtime\python\Scripts\python.exe app\tool.py invoke list_workflows --params "{}"
```

## MCP {#mcp}

Configurez votre client MCP pour lancer l’interpréteur privé avec `app/tool.py mcp`, en utilisant le dossier de l’application comme dossier de travail. Reconnectez-le lorsque le catalogue d’opérations exposées change.

## Fichiers des tâches {#task-files}

Les entrées locales acceptent des chemins absolus lisibles et sont importées automatiquement dans l’espace de la tâche. Exportez les résultats utiles avant de terminer la tâche. Ne réutilisez pas les chemins temporaires après nettoyage.

## Opérations {#operations}

- [`remesh_auto`](doc:operation-remesh-auto)
- [`remesh_field`](doc:operation-remesh-field)
- [`uv_unwrap`](doc:operation-uv-unwrap)
- [`uv_repack`](doc:operation-uv-repack)
- [`texture_pbr`](doc:operation-texture-pbr)
- [`mesh_inspect`](doc:operation-mesh-inspect)
- [`image_to_mesh_triposr`](doc:operation-image-to-mesh-triposr)
- [`image_to_mesh_spar3d`](doc:operation-image-to-mesh-spar3d)
- [`photos_to_mesh`](doc:operation-photos-to-mesh)
- [`construct_proxy`](doc:operation-construct-proxy)
- [`analyze_views`](doc:operation-analyze-views)
- [`views_generate`](doc:operation-views-generate)
- [`views_auto_complete`](doc:operation-views-auto-complete)
- [`views_turntable`](doc:operation-views-turntable)
- [`views_mirror`](doc:operation-views-mirror)
- [`views_validate`](doc:operation-views-validate)
- [`segment_object`](doc:operation-segment-object)
- [`mesh_to_rig`](doc:operation-mesh-to-rig)
- [`video_to_motion`](doc:operation-video-to-motion)
- [`video_inspect`](doc:operation-video-inspect)
- [`mesh_edit`](doc:operation-mesh-edit)
- [`mesh_convert`](doc:operation-mesh-convert)
- [`prepare_subject`](doc:operation-prepare-subject)
- [`complete_subject`](doc:operation-complete-subject)
- [`image_to_mesh_hi3dgen`](doc:operation-image-to-mesh-hi3dgen)
- [`refine_mesh`](doc:operation-refine-mesh)
- [`texture_mesh`](doc:operation-texture-mesh)
- [`run_workflow`](doc:operation-run-workflow)
- [`save_workflow`](doc:operation-save-workflow)
- [`list_workflows`](doc:operation-list-workflows)
- [`install_engine`](doc:operation-install-engine)
- [`install_model`](doc:operation-install-model)
- [`import_model_file`](doc:operation-import-model-file)
- [`update_status`](doc:operation-update-status)
- [`check_update`](doc:operation-check-update)
- [`stage_update`](doc:operation-stage-update)
- [`activate_update`](doc:operation-activate-update)
- [`rollback_update`](doc:operation-rollback-update)
- [`diagnose`](doc:operation-diagnose)
- [`list_models`](doc:operation-list-models)


## Communication native {#native-communication}

Le paquet Windows contient CyToolsCore 0.12.0 et la bibliothèque de communication
native CyMCPSDK 0.7.1. Les mêmes paramètres complets des opérations sont disponibles
pour les clients IA et l’application autonome. Lancez `ai_communication_status` avec
`includeOperations: true` pour consulter le catalogue effectif. Cette opération ne
contacte aucun fournisseur IA et ne génère pas de contenu.

Les fichiers générés par la CLI sont temporaires par défaut. Ajoutez `--export-dir`
suivi d’un dossier absolu hors du stockage des jobs pour les conserver. Par MCP,
exportez avec `cy_export_job` avant `cy_finish_task`. Le nettoyage des tâches ne
supprime pas les entrées originales, modèles installés, conversations et documents
de projet persistants.

Pour la première migration depuis Core 0.10.x, installez le paquet Windows complet.
Une mise à jour de l’application seule ne peut pas ajouter la bibliothèque native
au précédent runtime. Les intégrations de modèles et de fournisseurs conservent
leurs compatibilités et permissions : cette mise à jour ne rend pas compatible un
modèle ou une plateforme non pris en charge.


## Accès MCP local {#local-mcp-access}

Core **0.12.0** embarque CyMCPSDK natif au commit **`34d4bca`**. Depuis la racine du
Tool, démarrez explicitement le service local :

```powershell
runtime/python/Scripts/python.exe app/tool.py --data-dir data/jobs serve --port 8766
```

Free est le profil initial : connectez-vous avec seulement `http://127.0.0.1:8766/mcp`.
Toutes les opérations exposées sont accessibles sans jeton ni confirmation de transport.
La validation des arguments, l’acceptation des licences et les confirmations explicites
des actions destructives restent des règles métier. L’API portable reste sur `/v1` ;
le serveur écoute uniquement sur 127.0.0.1.

Un choix absent devient Free ; les profils explicites sont conservés. L’option du serveur
accepte `--access-profile free`, `--access-profile local_controlled`,
`--access-profile token_only` ou `--access-profile protected_access`. Local contrôlé
applique les permissions choisies par l’hôte. Jeton seul et Protégé exigent un jeton
valide ; Protégé conserve les permissions de l’identité. Avec la commande ci-dessus,
le choix persiste dans `data/jobs/communication.json`. Redémarrez le service pour changer
le profil actif. Les droits CLI/embarqués et du fournisseur de chat sont inchangés.
Utilisez `ai_communication_status` avec `includeOperations: true` pour la découverte.

Installez le paquet Windows complet pour remplacer le runtime natif ; les mises à jour
de l’application seule refusent l’ancien ABI. Pour une mise à niveau locale des sources :

```powershell
runtime/python/Scripts/python.exe -m pip install --no-deps app/packages/cytools_core-0.12.0-py3-none-win_amd64.whl
```

Exportez les résultats voulus avant `cy_finish_task`. Le nettoyage préserve les entrées
originales, modèles installés, conversations et documents de projet persistants.
Cette mise à jour est validée sur Windows x64 ; les builds natifs Linux/macOS restent
à vérifier sur leur plateforme.
