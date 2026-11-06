---
id: operations
title: Automatisation et API
description: Connectez un client et consultez les opérations disponibles.
section: Référence
order: 80
parent: overview
sourceRevision: 615b0a0a48781d6c
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
