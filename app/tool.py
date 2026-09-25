"""CyTools_MeshStudio runtime: one Runtime shared by the interface, the CLI, JSONL, HTTP and MCP.

Nothing heavy is imported here. Every model and every native program runs in a worker
process started with the interpreter of its engine (see app/engines.json); this process
only validates, schedules and reports.
"""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from installation_ui import configure as configure_storage  # noqa: E402

configure_storage()

from cytools_core import Runtime, load_manifest  # noqa: E402
from cytools_core.transports.cli import run_cli  # noqa: E402

from meshstudio import paths  # noqa: E402
from meshstudio.operations import ai, common, construct, geometry, maintenance, quality, workflows  # noqa: E402

# Operation -> the input fields the SDK imports automatically for an AI session.
INPUT_FIELDS = {
    'remesh_auto': ['input_file'],
    'remesh_field': ['input'],
    'uv_unwrap': ['input'],
    'uv_repack': ['input'],
    'texture_pbr': ['mesh_file'],
    'mesh_inspect': ['mesh_file'],
    'mesh_edit': ['mesh_file'],
    'mesh_convert': ['mesh_file'],
    'image_to_mesh_triposr': ['image_file'],
    'image_to_mesh_spar3d': ['image_file'],
    'photos_to_mesh': ['front', 'right', 'left', 'back'],
    'prepare_subject': ['front', 'right', 'left', 'back', 'images'],
    'complete_subject': ['image'],
    'texture_mesh': ['mesh_file', 'detail_mesh', 'image'],
    'refine_mesh': ['mesh_file', 'image'],
    'image_to_mesh_hi3dgen': ['image'],
    'construct_proxy': ['images', 'generated_views'],
    'analyze_views': ['images', 'generated_views'],
    'views_generate': ['images'],
    'views_auto_complete': ['images'],
    'views_turntable': ['images'],
    'views_mirror': ['images'],
    'views_validate': ['images', 'candidates'],
    'segment_object': ['images'],
    'mesh_to_rig': ['mesh'],
    'video_to_motion': ['video'],
    'video_inspect': ['video'],
    'run_workflow': ['input_file'],
}


def create_runtime(data_dir, **options):
    paths.ensure_data_layout()
    manifest = load_manifest(APP / 'CyTool.json')
    runtime = Runtime(manifest, data_dir, **options)
    runtime.configure_inputs(paths.INPUTS, fields=INPUT_FIELDS)

    services = common.Services(runtime)
    runtime.services = services      # the interface stops the worker pool when it closes
    handlers = {}
    handlers.update(geometry.register(runtime, services))
    handlers.update(ai.register(runtime, services))
    handlers.update(construct.register(runtime, services))
    handlers.update(quality.register(runtime, services))
    handlers.update(maintenance.register(runtime, services))

    # The workflow runner calls the very same handlers, so it is registered last.
    manifest_operations = {item['id']: item for item in manifest['operations']}
    workflows.register(runtime, services, handlers, manifest_operations)

    from cytools_core.shared_installation import register_operations
    register_operations(runtime, paths.ROOT)
    return runtime


if __name__ == '__main__':
    # An update activated earlier is applied here, before anything else is loaded, by a
    # separate process that renames the folders; see app/updates.py.
    from updates import apply_at_startup  # noqa: E402

    apply_at_startup(paths.ROOT)
    argv = sys.argv[1:]
    if '--data-dir' not in argv:
        argv = ['--data-dir', str(paths.JOBS), *argv]
    raise SystemExit(run_cli(create_runtime, argv))
