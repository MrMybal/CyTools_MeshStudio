---
id: operations
title: Automation and API
description: Connect a client and inspect the available operations.
section: Reference
order: 80
parent: overview
revision: 615b0a0a48781d6c
---

## Command line {#cli}

From the application root, use the private Python interpreter. `describe` and `list-operations` inspect the public contract.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe
runtime\python\Scripts\python.exe app\tool.py list-operations
runtime\python\Scripts\python.exe app\tool.py invoke list_workflows --params "{}"
```

## MCP {#mcp}

Configure your MCP client to start the private interpreter with `app/tool.py mcp`, using the application folder as its working directory. Restart the connection when its exposed operation catalogue changes.

## Task files {#task-files}

Local file inputs accept absolute readable paths and are imported into the task workspace automatically. Export wanted results before finishing the task. Do not rely on temporary paths after task cleanup.

## Operations {#operations}

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
