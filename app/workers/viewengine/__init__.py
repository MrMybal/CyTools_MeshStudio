"""Inference-side modules. Imported only by the worker interpreter (runtime/engine).

Nothing here is imported by the CyTools runtime, the CLI, the MCP bridge or the
Dear ImGui interface: those processes never load torch or a model.
"""
