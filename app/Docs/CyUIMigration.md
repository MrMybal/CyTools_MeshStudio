# Modular CyUI integration

The standalone application uses [CyUI](https://github.com/MrMybal/CyUI) 1.2.0,
pinned to [`ff023e6`](https://github.com/MrMybal/CyUI/tree/ff023e646c6a3038b3dfbfd53f6d2b4a2f5955e3).

## Selected modules and replacements

Core; Inspector; Viewport; Images; Canvas; Diagnostics.

- Boolean, enum and exact integer/float operation parameters use Inspector, stable IDs and host revisions. Only commit events update submitted parameters.
- The live PBR preview texture is presented by Viewport.
- Structured logs use Diagnostics; character selection and complete file copy remain available.
- Core replaces the old monolithic CyUI revision; the old `cyui.json` provenance record is replaced by the complete hashed source manifest.

## Reproducible source and delivery

`app/cyui-source.json` records every selected upstream file and its SHA-256.
`app/cyui.py` and `app/cyui_modules/*.py` are unchanged official sources, normalized
to LF. Do not edit them: host adapters live outside the library. Refresh only from
the exact pinned checkout:

```sh
python app/scripts/sync_cyui.py /path/to/CyUI
```

The sources are included with the application using its existing source-vendoring
mechanism. Neither a developer checkout elsewhere on disk nor an editable pip
installation is needed. There is one imgui-bundle renderer, at the version pinned
in `app/requirements.txt`; no C++ umbrella, CMake demo/gallery, CEF, extra model,
AI engine, NumPy installation or browser dependency is introduced by this migration.
Existing application/DSP/rendering dependencies are kept where required.

Keep `LICENCES/CyUI-MIT.txt` with the product. The application's own license does
not change. The Options licenses list identifies the upstream revision and source.

## Host responsibilities and retained adaptations

File pickers, nested schemas, mesh/PBR rendering, materials, scene presets, picking and six-axis orbit/free navigation remain host-owned. The shared viewport is deliberately used with navigation=False so its simpler orbit controller cannot remove the existing camera controls or impose a new zoom limit. Images/Canvas are only dependencies of this surface. The renderer keeps its existing moderngl/trimesh dependencies; CyUI supplies no 3D engine.

SDK operations, permissions, exclusive groups, temporary AI task files, model
installation, licenses/acceptance, generation recipes and Undo remain host-owned.
No CyToolsCore runtime or AI library is copied into CyUI. English remains the
default and French the persistent selectable second language.

## Verification

40/40 native forms; 49 native interaction checks; 12-triangle GLB fixture in the live shared viewport; int64/configuration replacement integration tests.

Run the adapter tests from `app/` with the private Python:

```sh
python -m unittest discover -s tests -p test_modular_ui.py -v
```

They verify pinned-source integrity, bounded log refresh/redaction and native ImGui
frames across five themes, both densities, EN/FR and scale 1.0/1.5/2.0, plus the
application-specific data/edit routing. This simulated DPI check is not a physical
multi-monitor test. Windows native views are tested locally. Linux/macOS remain
unverified by this migration; the source integration stays platform-independent.

Windows packages include the migrated sources and their license notices.

Final local results: runtime 5 passed; update fixtures 28/28; workflow fixtures 80/80; quad UV test 11/11 in the existing geometry engine; adapter tests 5/5; native forms 40/40 and interactions 49/49. The live viewport rendered the 12-triangle GLB fixture. The base environment intentionally has neither pytest nor xatlas; use unittest scripts and the geometry engine respectively.


CyUI license: [https://github.com/MrMybal/CyUI/blob/main/LICENSE](https://github.com/MrMybal/CyUI/blob/main/LICENSE). The complete MIT text ships with the application, including when the upstream repository is private.
