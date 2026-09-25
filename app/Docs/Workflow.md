# Workflows

A workflow is a chain of operations of this Tool, stored as JSON in `data/workflows` and run
identically from the interface, the CLI and MCP. It is data, not code: `run_workflow` reads
the document and calls the same handlers a client would call one by one.

This page also records what the LocalMesh pipeline taught us, because the first real workflow
of this Tool is that pipeline, opened up.

## What LocalMesh did, and what it cost to learn

`Engine.generate()` chained twelve stages in one call: load, read the reference, cut the
subject out, measure the two profiles, sample the shape, clean the mesh, texture, finish,
repad the atlas, orient and scale, export, render a thumbnail. The tier recipe
(`draft` / `standard` / `high` / `max` / `extreme`) decided the pipeline type, the three step
counts, the sampler, the atlas size, the triangle budget and the guidance, in one table.

Several of its behaviours are not preferences, they are incidents that were paid for, and
any workflow built on top of it has to keep them:

* **A progress bar never goes backwards.** Two emitters were fighting: the bar reached 45 %,
  fell back to 20 %, climbed again. The invariant is held in one place, and a stale tick is
  dropped — but never its cancellation check.
* **A shape too heavy is refused before it saturates the card.** A multi-view job at the
  Standard tier produced 12.3 M faces and killed the display driver (BSOD 0x116). Above the
  ceiling, the job restarts at the lower tier instead of failing, and says so in a note.
* **VRAM is measured at the card, through NVML.** The `o_voxel` wheel allocates raw CUDA
  outside PyTorch's allocator: the manifests announced 2.07 GB where the driver read 5.6.
* **Cut-outs are framed together.** Framing each view on its own scales an elongated object
  differently per view — 37.9 % apart between a motorbike's profile and its front — and the
  fusion then thickens it.
* **Angles are measured, not assumed.** A view filed as "left" was really at −53.6°;
  projected at −90° it carved a cavity in the back of the subject.
* **A measurement that cannot be trusted is refused.** Over 30° of elevation, or the two
  heads disagreeing by more than 15°, and the round angles are used instead.
* **No WebP in the delivered glTF.** `EXT_texture_webp` is all-or-nothing: Unreal refused the
  whole file, geometry included.
* **Stage previews are deleted once the model is written** — they were 85 % of the library.

## The shared front end

Four of the absorbed Tools carried their own background remover (BiRefNet, u2net,
transparent-background, SAM 2.1) and three estimated the camera differently (Depth Anything 3,
DINOv2 + SAM 2.1, PerspectiveFields). `prepare_subject` does it once and writes a **subject
set**:

```
outputs/subject/
  front.png right.png left.png back.png   cut-outs, one common scale
  contact.png                             contact sheet
  subject.json                            what was measured
```

`subject.json` carries, per view, its source, its size, the framing geometry and its measured
azimuth when the measurement was accepted; and, for the set, the camera report with
`refusedBecause` when it was not. A reconstruction step consumes the folder through
`subject_set`, so the subject is segmented once for the whole workflow.

The refusal is surfaced rather than silently swallowed: *"the back view measures 32.7 degrees
of elevation, over the 30 degree limit"* tells the artist to re-shoot at eye level, where
"round angles used" alone would not.

Measured on this machine: `prepare_subject` 8.7 s for four views, then `photos_to_mesh`
96.2 s at the draft tier, 77 370 faces, 4.31 GB peak VRAM — 105 s for the chain.

## Feeding a step from another

A step names where its input comes from:

* `input_from` — the step whose output it reads (empty: the previous step, or the workflow
  input for the first one).
* `input_field` — which output field of that step to take (empty: the main mesh output).
* `input_to` — which parameter of this step receives it (empty: the field that operation
  normally reads its input from). This is what lets a step consume a prepared subject folder
  instead of a mesh file.

```json
{"id": "mesh", "operation": "photos_to_mesh",
 "input_from": "subject", "input_field": "subject_set", "input_to": "subject_set"}
```

A step that needs more than one thing lists the others in `extra_inputs`
(`{"from": "shape", "field": "file", "to": "detail_mesh"}`); `"from": "@input"` names the file
the workflow was started on, which is how a retopology gets its original texture back.

Every step's parameters are validated against the operation's schema, and completed with its
defaults, before the step runs — exactly as a job submitted on its own. A misspelt parameter
fails on the step that carries it, naming it, instead of inside a worker after the steps
before it have been paid for.

## What a folder means: `input_mode`

`each` (the default) runs the whole chain once per file of the folder: a batch of meshes. For
four photographs of one statue that is wrong — each would become its own subject, and the
four-view mode would never see four views. `together` runs the chain once, and the first step
receives every file as one list. `prepare_subject` then gives each photograph its role from
its file name (`front`, `right`, `left`, `back`, or `face`, `droite`, `gauche`, `dos`; accents
ignored); a photograph without a role becomes the front if there is none. The mode is saved in
the document and shown under the input in the editor; `run_workflow` can override it.

## When a step fails: `continue_on_error`

Without it, a failed step stops the workflow. With it, the failure is listed in the report and
logged as a warning, and the step hands on what it received — exactly what it does when it is
switched off — so the chain goes on. The engine comparison relies on it (one engine failing
leaves the others), and so does *Mesh to game asset*: an input with no UV texture to transfer
still gets its quad mesh.

## The workflows shipped in `data/workflows`

| Workflow | Input | Chain |
|---|---|---|
| Image to quick preview (LocalMesh draft) | picture | cut-out, LocalMesh draft |
| Image to high-quality mesh (LocalMesh) | picture | cut-out, LocalMesh high |
| Image to maximum-quality mesh (LocalMesh max) | picture | cut-out, LocalMesh max (1536 grid, 24 GB card) |
| Image to production mesh (LocalMesh+) | picture | cut-out, LocalMesh high, [refine], 60 000 faces, QuadWild, 4K texture + normal map |
| Image to production mesh with Hi3DGen | picture | the same with Hi3DGen for the shape |
| Image to production mesh with generated views (experimental) | level front view | Wonder3D views, LocalMesh four views, then the same |
| Four photos to production mesh (LocalMesh+) | folder, together | four photos, LocalMesh four views, [refine], QuadWild, texture from the four photos |
| Photos to textured mesh | folder, together | four photos, LocalMesh four views |
| Image to game asset (LocalMesh, AutoRemesher) | picture | LocalMesh high, 20 000 faces, ~4 000 quads, 2K texture + normal map |
| Image to rigged character (LocalMesh, UniRig) | picture | the game asset with ~6 000 quads, then UniRig |
| Image to 3D print (STL) | picture | LocalMesh high, largest part, holes, normals, Z-up, 100 mm, STL |
| Compare the shape engines on one image | picture | one cut-out to TripoSR, SPAR3D, Hi3DGen and LocalMesh |
| Mesh to game asset | textured mesh | 20 000-face OBJ, ~4 000 quads, its texture transferred back |
| Retopologise a textured mesh (QuadWild, texture kept) | textured mesh | 60 000 faces, QuadWild, its texture transferred back |

`app/tests/test_workflow_inputs.py` runs every one of them with stand-ins in place of the
models, its steps validated against the manifest, with its optional steps off and then on.

## Resident sessions

Splitting a heavy pipeline into steps is only worth it if the steps can hand each other what
they produced. Writing a TRELLIS volume to disk and reading it back would cost more than
recomputing it, so a worker keeps the intermediates in memory under a `session` key
(`workers/_protocol.py`, `SessionStore`): at most two sessions, least recently used evicted,
everything dropped when the worker exits — which is also what a cancellation does, since the
host kills the process.

The store and the protocol are in place. The TRELLIS steps that will use it — `shape`,
`clean`, `texture`, `finish` — are not written yet: they are what makes "re-texture this shape
with another seed" and "edit between shape and texture" possible, and they must reproduce the
ceiling, the fallback and the metering listed above rather than quietly dropping them. Until
they exist, `photos_to_mesh` runs the engine's own chain, which keeps every one of those
behaviours.

## Resources

The steps of a workflow run inside the job that started it, one after another, so the job
reserves the maximum of its steps rather than their sum (`runner.estimate`). A step that
needs more than the job reserved is reported by the scheduler before anything starts.
