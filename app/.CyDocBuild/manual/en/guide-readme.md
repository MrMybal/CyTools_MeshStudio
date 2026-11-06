---
id: guide-readme
title: Features and installation
description: Choose the right workflow and prepare the application.
section: Guide
order: 20
parent: overview
revision: 150f52aeaabb0b59
---

Reconstruct meshes from images, prepare views, remesh, unwrap UVs, texture, rig and inspect 3D assets. Run one operation or chain compatible operations in a workflow.

## Main workflow {#workflow}

1. Choose the workspace and backend for your source images, video or mesh. Install its engine and weights if required.
2. Provide the inputs, select the model and device, and adjust the parameters. Use a workflow when several stages must be chained.
3. Inspect the generated mesh in the 3D viewer. Orbit, pan and zoom before exporting; inspect textures and topology after remeshing or baking.

## Requirements and installation {#requirements}

Each reconstruction, rigging or texturing backend has its own installation and hardware requirements. Installing one backend does not install all others. Models, engines and application updates are separate; gated weights require the user’s account and licence acceptance.

Read [Installation and models](doc:installation) for setup, the [User guide](doc:guide-lisez-moi) for detailed controls, and [Automation and API](doc:operations) for the public operation contracts.
