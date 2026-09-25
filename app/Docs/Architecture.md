# CyTools_MeshStudio — architecture

CyTools_MeshStudio replaces eleven Tools with one standalone application: specialised
mesh operations, and complete workflows that chain them the way CyTools_LocalMesh chained
its own pipeline. It is built on the CyToolsCore SDK 0.9.0 and follows
`Docs/StandaloneDelivery.md`, `Docs/MeshViewer.md` and `Docs/Localization.md` of the SDK.

## What it absorbs

| Absorbed Tool | What comes over | Where it lands |
|---|---|---|
| CyTools_AutoRemesher | AutoRemesher 1.2.0 binaries, `remesh` | `remesh_auto`, engine `geometry` |
| CyTools_QuadWild | QuadWild Bi-MDF binaries, `remesh` | `remesh_field`, engine `geometry` |
| CyTools_Xatlas | `unwrap`, `repack` | `uv_unwrap`, `uv_repack`, engine `geometry` |
| CyTools_Trellis2Texture | `inspect_mesh`, `generate_pbr` | `mesh_inspect`, `texture_pbr`, engine `geometry` |
| CyTools_TripoSR | TripoSR weights and source | `image_to_mesh` backend `triposr` |
| CyTools_SPAR3D | SPAR3D weights and source | `image_to_mesh` backend `spar3d` |
| CyTools_UniRig | Articulation-XL weights and source | `mesh_to_rig` |
| CyTools_LocalMesh | TRELLIS.2-4B, DINOv3, BiRefNet, multivue | `photos_to_mesh` |
| CyTools_ViewGenerator | Zero123++, ControlNet, DINOv2, SAM 2.1 | the `views_*` operations |
| CyTools_MeshConstruct | SAM 2.1 large, Depth Anything, PerspectiveFields, Wonder3D, SyncDreamer | `construct_proxy`, `analyze_views` |
| CyTools_WHAM | WHAM source (its weights had never been installed; they are now) | `video_to_motion`, `video_inspect` |

Their weights were **moved**, not copied: `app/scripts/migrate_assets.py` performed
49.9 GiB of same-volume renames and wrote `data/reports/migration-manifest.json`, which
`rollback` replays in reverse. The application sources of the eleven Tools are kept under
`runtime/legacy-apps/` so that every ported worker can be compared against its original.

## Deduplication

The point of the merge is to stop paying several times for the same thing.

* **Weights.** Zero123++ v1.2 had been installed twice (MeshConstruct and ViewGenerator),
  5.2 GiB each. The migration compared the two trees file by file and then by SHA-256 of
  `unet/diffusion_pytorch_model.safetensors`, found them identical, and kept one. The
  catalogue in `app/models/catalog.json` is now the single declaration of every model:
  26 entries, 60.7 GiB, each with its engine, its backends, its licence and its revision.
* **Environments.** The eleven Tools carried thirteen virtual environments totalling
  73 GiB, most of them a different copy of the same PyTorch build. `app/engines.json`
  declares eight, grouped strictly by dependency stack — never by theme.

| Engine | Stack | Backends |
|---|---|---|
| `geometry` | Python 3.11, CPU, trimesh/xatlas + native binaries | autoremesher, quadwild, xatlas, pbrbake, meshedit, proxyfit |
| `torch-cu124` | Python 3.11, torch 2.5.1+cu124 | triposr, spar3d, unirig |
| `trellis` | Python 3.12, torch 2.8.0+cu128, transformers 5.x | trellis, birefnet |
| `diffusion` | Python 3.12, torch 2.8.0+cu128, diffusers 0.35.2, transformers 4.57 | zero123plus, mirror, sam2, depthanything, perspectivefields |
| `wonder3d` | Python 3.10, torch 2.1.2+cu121, diffusers 0.19.3 | wonder3d |
| `syncdreamer` | Python 3.10, torch 2.1.2+cu121, pytorch-lightning 1.9 | syncdreamer |
| `wham` | Python 3.9, torch 1.11+cu113 | wham |
| `hi3dgen` | Python 3.10, torch 2.4.0+cu121, spconv 2.3.8, xformers 0.0.27, transformers 4.46.3, numpy 1.26.4 | hi3dgen |

Seven, not the six first planned: Wonder3D and SyncDreamer run the same torch build but need
diffusers 0.19.3 with transformers 4.35.2 on one side, and pytorch-lightning 1.9 with
transformers 4.37.2 and taming-transformers on the other. The install steps the absorbed Tool
had validated said so; the merge was undone before it was built.

Three extensions of `torch-cu124` have no wheel for this ABI and are compiled at install
time (torchmcubes, texture_baker, uv_unwrapper). The installer downloads the official NVIDIA
redistributables into `runtime/cuda-12.4` and loads the MSVC toolchain into its own process:
no driver is touched, the machine PATH is untouched, and no system CUDA installation is
required. torch-scatter and torch-cluster come from the PyTorch Geometric wheel index.

A backend also declares the environment variables its upstream code expects
(`HF_HUB_CACHE`, `U2NET_HOME`, `ALPHA_CLIP_PATH`…), and the host sets them **before** the
process starts: huggingface_hub reads its cache path when it is imported, so a handler that
sets it afterwards is already too late — which is exactly how TripoSR failed its first run here.

`trellis` and `diffusion` both run torch 2.8.0+cu128 and would look mergeable, but the
LocalMesh engine needs transformers 5.17 with huggingface_hub 1.x while the diffusers
0.35.2 stack needs transformers 4.57 with huggingface_hub 0.36. Those are incompatible
majors, so the two engines stay separate. `torch-cu124` is the opposite case: TripoSR and
SPAR3D shipped with transformers 4.42.3 / trimesh 4.4.1 and UniRig with 4.51.3 / 5.1.0;
the merged engine pins the newer pair, and **each of the three backends has to be executed
here before it is declared supported**. If one of them cannot be made to work on the
shared pins, it gets its own engine and that is written down rather than hidden.

## Runtime structure

The façade, the CLI and MCP all submit to the same `Runtime`; there is no second
scheduler. Heavy work never runs in the application process: each backend runs in a
persistent worker process started with its engine's interpreter, speaking the JSON-lines
protocol in `meshstudio/engines/workerhost.py` (handshake, streamed progress, log
forwarding, cancellation by killing the process tree, idle unload). That host and
`workers/_protocol.py` come from CyTools_AudioStudio, where the same problem was already
solved; they are Tool-local infrastructure, not additions to the Core.

```
app/
  CyTool.json          manifest: every operation, its schema, its backends
  engines.json         the eight engine environments and their sources
  tool.py              create_runtime + one handler per operation
  setup_engine.py      builds one engine environment at its final path
  meshstudio/          business package (paths, engines, catalog, mesh, workflow)
  workers/             one worker per backend, run by the engine interpreter
  gui/                 Dear ImGui interface: tools, workflows, installation, updates
  desktop.py           graphical entry point started by the launcher
  launcher.cpp         source of CyTools_MeshStudio.exe (build_launcher.ps1)
  models/catalog.json  generated by scripts/build_catalog.py
  models/install.json  what an absent model needs to become installable
  updates.py           the three update streams, and the swap done at the next start
  scripts/             migrate_assets.py, build_catalog.py, install_model.py
data/
  inputs models jobs settings logs reports workflows presets library
runtime/
  python/              light application interpreter
  engines/             the eight heavy environments
  sources/             upstream engine checkouts, pinned by revision
  natives/             AutoRemesher and QuadWild binaries
  legacy-apps/         sources of the eleven absorbed Tools, for reference
  downloads/ updates/ backups/
```

## Operations

Specialised operations keep the contract of the Tool they come from, so a client that
drove the old Tool keeps its parameters. Workflows are the second half of the brief: a
saved chain of operations (for example *photos → views → mesh → remesh → UV → PBR → rig*)
applied to one input or to a folder, runnable identically from the interface, the CLI and
MCP. A workflow is data, not code: it is stored in `data/workflows` and executed by the
runner in `meshstudio/workflow`, which submits each step as a real job.

## Models: catalogue, install plan, licensed files

Two files describe the weights, and they answer different questions.

* `app/models/catalog.json` is built by `app/scripts/build_catalog.py` and says what exists:
  every model, its family, its engine, its backends, its size, its revision when a receipt
  recorded one, its licence. It also lists a model that is **declared but absent**, so the
  interface can show what is missing instead of staying silent until a job fails.
* `app/models/install.json` says how an absent model becomes installable. Each item is either
  automatic (downloaded and hashed by `app/scripts/install_model.py`, with a receipt in
  `cytools-receipt.json`) or `manual`.

A `manual` item is a file whose licence is accepted in person, such as `SMPL_NEUTRAL.pkl`.
The application never downloads it and never asks for the credentials of those sites: it shows
the page, and `import_model_file` puts in place the file the user obtained, after checking it
really is that file. A worker whose weights are incomplete refuses before loading anything, so
the error names the missing files and the page rather than failing inside a pickle.

The state shown by `list_models` and `diagnose` comes from the files on disk, crossed with the
plan: a half-downloaded model reads `Partial`, never `Installed`.

## Updates: three streams, one swap

`app/updates.py` keeps the three apart because they change for different reasons:

* the **application** is a GitHub release of the `app` folder — check, stage, verify, activate,
  roll back;
* an **engine** is rebuilt from the revision pinned in `app/engines.json` by `install_engine`;
* the **weights** follow the catalogue and the install plan above.

Staging never touches the running application: the archive is downloaded (or copied), hashed
against the expected SHA-256 when one is given, unpacked under `runtime/updates` and verified —
same tool id, no `data/` folder, a complete tree. Activation only records the request in
`pending.json`. The directory rename itself happens at the **next start**, performed by a
separate process (`runtime/updates/apply.py`) before anything of the application is imported,
so the folder holding the running code is never swapped underneath it; the previous `app` is
kept under `runtime/backups`, and a rollback records the reverse move the same way. If the
rename fails, the working folder is put back.

`data/` is never read, replaced or removed by any of this.

## Interface tests

Two tests guard the interface, and both exist because a defect shipped without them:

* `app/tests/validate_forms.py` draws **every** operation's form, one process per operation,
  with one entry pre-filled in each list of objects so the sub-form of an entry is drawn too.
  A form is generated from its schema, so a shape no widget supports only crashes when that
  operation is selected — rendering one form and calling the interface tested is how eight
  operations shipped with a seed slider that asserts inside Dear ImGui, and drawing those
  lists only while they were empty is how their sub-forms went untested.
* `app/gui/interaction_tests.py` (`--ui-test-interactions`) drives the Dear ImGui test engine:
  it clicks every tool of the list, opens the advanced section of each, walks the tabs, adds
  and removes a workflow step, refreshes the installation report, and checks that a model that
  can be installed offers its button, that a licensed file shows its page, and that the updates
  tab reads the real version. It found a Remove button that was clipped out of its child window
  and never answered a click.

Run both after touching `gui/`, in English and with `--ui-test-language=fr`. They must not run
at the same time: one runtime owns the data directory.

## The parameter editor

`gui/widgets.py` turns an `inputSchema` into controls, which is what keeps 36 operations
usable without a line of UI written per operation. The shapes it handles, and why each one
exists:

| Schema | Control |
|---|---|
| `enum` | combo |
| `boolean` | checkbox |
| number with `minimum` and `maximum` close enough | slider |
| number otherwise, and every `x-cy-kind: Seed` | typed field (a seed's range is wider than a Dear ImGui slider accepts) plus a *Random* button writing -1 |
| `x-cy-kind: File / Image / Video / Directory` | text field, *Browse*, *Clear*, with the filter of that kind |
| array of strings | list with *Add* and per-item removal |
| array of objects | one sub-form per entry, *Add files* (one entry per file chosen) and *Add empty* |
| object, or an array of anything else | JSON box, the last resort |

A file dialog is asynchronous, so the pending request carries a path — `views_generate#images#1#file`
— and the answer is written at that exact place, including inside a list entry.

## Verification rules

Nothing is declared supported before it has been executed here. `platforms[].tested`
entries are filled only from runs that actually happened on this machine, and the
migration, the engine merges, cancellation, the model installer and the update flow each
need their own evidence in `data/reports`. Linux has a launcher and instructions but no
run on this machine, and is declared as such.
