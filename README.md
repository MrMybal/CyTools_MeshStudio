# CyTools_MeshStudio

Maintenance: **Cyberalien**.

One desktop Tool for meshes: reconstruction from pictures (LocalMesh / TRELLIS.2, Hi3DGen,
TripoSR, SPAR3D), generated and prepared views, quad remeshing (AutoRemesher, QuadWild),
UV unwrapping, PBR texturing, mesh editing and inspection, rigging (UniRig), motion from
video (WHAM), and workflows that chain all of it. It runs as a Dear ImGui application, as
a command line, and as an MCP server, on the same CyToolsCore runtime.

The user guide, in French, is [LISEZ-MOI.md](LISEZ-MOI.md). The developer notes are in
[app/README.md](app/README.md), the design in [app/Docs/Architecture.md](app/Docs/Architecture.md)
and [app/Docs/Workflow.md](app/Docs/Workflow.md).

Only Windows 10 with an NVIDIA card has been executed. The Linux launcher exists and has
never been run.

## What this repository contains, and what it does not

The repository carries the application (`app/`), the shipped workflows and the small test
fixtures (`data/workflows/`, `data/inputs/`), the user guide, the Linux launcher and the
licence texts (`LICENSE`, `LICENCES/`).

It does **not** carry:

- **model weights** (`data/models/`, about 61 GiB): installed from the Installation tab or
  with `install_model`, from the plans in `app/models/install.json`. Several are under
  non-commercial licences, and some ask for a personal acceptance on their page; the
  application says which, and never asks for credentials.
- **`runtime/`**: the private Python of the application, one environment per engine, the
  pinned upstream checkouts, the native programs, staged updates and backups. All of it is
  rebuilt with the steps below.
- **jobs, logs, settings, test reports** (`data/jobs/`, `data/logs/`, `data/settings/`,
  `data/reports/`): produced on the machine. The CLI token lives in `data/settings/`.
- **the Windows launcher** `CyTools_MeshStudio.exe`: compiled from `app/launcher.cpp` and
  attached to each release.

## Binary release (Windows x64)

Each GitHub release carries `CyTools_MeshStudio-<version>-windows-x64.zip`: unzip it into a
folder with a short path (QuadWild fails in paths longer than about 240 characters, and the
Tool says so instead of running it) and double-click `CyTools_MeshStudio.exe`. It holds the application, an embeddable CPython 3.12
with the application's packages, `uv`, and the two native programs of the geometry engine, so
nothing has to be installed first (Windows 10 or later, x64). The engines and the weights are
not in it: the Installation tab builds each engine environment and downloads the weights, tens
of gigabytes in all, from PyPI, GitHub and Hugging Face. What the archive is made of — each
part with its URL and SHA-256 — is in `runtime/RELEASE.json` inside it; the archives are built
by `app/scripts/build_release.py` from the tagged commit.

The lighter `CyTools_MeshStudio-<version>-app.zip` holds the `app/` folder and the guides of
the commit, without `data/`: what an installed Tool downloads from its Updates tab, which
replaces its `app/` folder and nothing else.

## From a clone

Windows, PowerShell, from the folder of the clone. Step 1 was executed on the development
machine in a fresh environment (the SDK from its repository, then this Tool's own tests with
that environment); steps 2 to 5 are the commands that were run here, not yet replayed from a
fresh clone on another machine.

1. The application environment — CPython 3.12. `app/requirements.txt` installs the
   [CyToolsCore](https://github.com/MrMybal/CyToolsCore) SDK 0.10.1 (MIT) from the archive of
   a pinned commit of its repository; neither `git` nor a published wheel is needed:

```powershell
py -3.12 -m venv runtime\python
runtime\python\Scripts\python.exe -m pip install -r app\requirements.txt
```

2. The launcher, with the MSVC compiler (a "x64 Native Tools" prompt):

```powershell
powershell -File app\build_launcher.ps1
```

3. The engines, one private environment each under `runtime\engines`, with their pinned
   upstream sources (`app/engines.json`). The interpreters come from `runtime\interpreters`,
   the `py` launcher, or `uv python install`:

```powershell
runtime\python\Scripts\python.exe app\setup_engine.py geometry
```

   then `torch-cu124`, `trellis`, `diffusion`, `wonder3d`, `syncdreamer`, `wham`, `hi3dgen`.
   The Installation tab of the application does the same.

4. The two native programs of the geometry engine are not downloaded by `setup_engine.py`
   yet. Unzip them so that these files exist:

   - `runtime\natives\autoremesher-1.2.0\autoremesher.exe` from
     [autoremesher-1.2.0-win32-x86_64.zip](https://github.com/huxingyi/autoremesher/releases/download/1.2.0/autoremesher-1.2.0-win32-x86_64.zip)
   - `runtime\natives\quadwild-bimdf-v0.0.2\quadwild.exe` from
     [windows-binaries.zip](https://github.com/cgg-bern/quadwild-bimdf/releases/download/v0.0.2/windows-binaries.zip)

5. The weights: Installation tab, or for one model:

```powershell
runtime\python\Scripts\python.exe app\tool.py invoke install_model --params "{\"model\":\"trellis2-4b\"}" --timeout 7200
```

Then double-click `CyTools_MeshStudio.exe`, or run `runtime\python\Scripts\python.exe app\desktop.py`.

## Updates

The Updates tab reads the releases of this repository — `MrMybal/CyTools_MeshStudio`, declared
in the manifest and changeable in the tab — stages one, activates it at the next start and can
roll it back; `data/` is never replaced. No release is published yet.

## Updating from 0.1.0, and going back

0.1.1 moves the SDK from CyToolsCore 0.9.0 to 0.10.1, now under the MIT licence, and adds
the `LICENCES` folder. The operations, the manifest schema, the protocol and `data/` are
unchanged, and 0.1.1 runs on either SDK.

- **A fresh installation**: the 0.1.1 binary archive carries the SDK 0.10.1 and `LICENCES`.
- **An existing binary installation**: the Updates tab replaces `app/` only, and the Tool
  keeps running on the SDK it was shipped with. To move its SDK too, install the wheel the
  update brings, from the folder of the Tool:
  `runtime\python\python.exe -m pip install --no-index --find-links app\wheels "cytools-core==0.10.1"`.
  The embedded Python cannot build a package from source, which is why the wheel is shipped
  and why `pip install -r app\requirements.txt` is for clones only. The `LICENCES` folder
  comes with the full archive; an update brings the SDK's own notice as
  `app/LICENSE-CyToolsCore.txt`. Engine environments are not relocatable: keep the folder
  rather than moving `runtime/engines` to a new one.
- **A clone**: `git pull`, then `runtime\python\Scripts\python.exe -m pip install -r app\requirements.txt`.
- **Going back**: the Updates tab rolls `app/` back to the copy it kept under
  `runtime/backups`; 0.1.0 runs on the SDK 0.10.1 too, so the SDK can stay. A clone goes back
  with `git checkout v0.1.0` and the same `pip install -r`. Copies received under the earlier
  licence keep their terms.

## Tests

```powershell
runtime\python\Scripts\python.exe app\test_tool.py
runtime\python\Scripts\python.exe app\tests\test_workflow_inputs.py
runtime\python\Scripts\python.exe app\tests\test_updates.py
runtime\python\Scripts\python.exe app\tests\validate_forms.py
runtime\python\Scripts\python.exe app\desktop.py --ui-test-interactions
runtime\python\Scripts\python.exe app\desktop.py --ui-test-interactions --ui-test-language=fr
runtime\engines\trellis\Scripts\python.exe app\tests\test_quadtex.py
```

Never run two of them at the same time: one runtime owns `data/` at a time.

## Licence

Copyright (C) 2026 Cyberalien.

CyTools_MeshStudio is distributed under the **GNU General Public License, version 3 only**
(`GPL-3.0-only`); the full text is in [LICENSE](LICENSE). It is built on the
[CyToolsCore](https://github.com/MrMybal/CyToolsCore) SDK 0.10.1, which is under the MIT
licence; the licence of the SDK does not change the licence of this program.

The [LICENCES](LICENCES) folder holds the full licence texts of what is shipped — the SDK
and, for the Windows binary archive, Python, pip, uv, AutoRemesher and QuadWild — and
[LICENCES/SOURCES.txt](LICENCES/SOURCES.txt) gives the source of each.

You may redistribute and modify this program under the terms of its licence. It comes
without any warranty, including the implied warranties of merchantability and fitness for a
particular purpose.

The engines, upstream sources, native programs and model weights are fetched at
installation, under their own licences — several of them non-commercial. They are listed in
[app/Docs/ThirdPartyNotices.md](app/Docs/ThirdPartyNotices.md), generated from
`app/engines.json` and `app/models/catalog.json`.
