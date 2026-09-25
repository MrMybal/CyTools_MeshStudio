"""Wiring of the saved workflows, checked without running a single model.

Each operation is replaced by a stand-in that records the parameters it received and returns
outputs shaped like the real ones. What is checked is what the runner does between steps: the
texturing step must receive the quad mesh, the detailed LocalMesh model and the subject set from
three different steps. Every saved workflow is then run once with its steps validated against the
manifest, exactly as the Tool validates them, with its optional steps off and then on.

    runtime/python/Scripts/python.exe app/tests/test_workflow_inputs.py
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

from cytools_core import CyToolError  # noqa: E402
from meshstudio.operations.ai import roles_from_names  # noqa: E402
from meshstudio.workflow import model, runner  # noqa: E402

PASSED, FAILED = [], []
MANIFEST = {item['id']: item for item in json.loads((APP / 'CyTool.json').read_text('utf-8'))['operations']}
SCHEMAS = {name: item['inputSchema'] for name, item in MANIFEST.items()}
#: What each operation returns, as far as the steps after it read it.
OUTPUTS = {
    'prepare_subject': {'subject_set': 'subject', 'subject_file': 'subject/subject.json',
                        'views': [], 'viewCount': 1},
    'complete_subject': {'subject_set': 'subject', 'subject_file': 'subject/subject.json',
                         'views': [], 'viewCount': 4},
    'photos_to_mesh': {'file': 'localmesh.glb', 'report': 'report.json'},
    'image_to_mesh_hi3dgen': {'file': 'hi3dgen.glb', 'normal_file': 'normal.png'},
    'image_to_mesh_triposr': {'file': 'triposr.glb'},
    'image_to_mesh_spar3d': {'file': 'spar3d.glb'},
    'refine_mesh': {'file': 'refined.glb', 'report': 'refine.json', 'grid_resolution': 1536},
    'mesh_edit': {'mesh_file': 'light.obj'},
    'mesh_convert': {'mesh_file': 'converted.glb'},
    'remesh_field': {'file': 'quad.obj', 'report': 'quad.json'},
    'remesh_auto': {'file': 'remeshed.obj', 'report': 'report.json'},
    'uv_unwrap': {'mesh': 'mesh.obj'},
    'texture_pbr': {'material_mesh_file': 'material.glb'},
    'texture_mesh': {'file': 'textured.glb', 'obj_file': 'textured.obj',
                     'base_color_file': 'base_color.png'},
    'mesh_to_rig': {'rigged_mesh': 'rigged.glb', 'skeleton': 'skeleton.json'},
}
MESH_FIRST = {'mesh_edit', 'remesh_field', 'remesh_auto', 'uv_unwrap', 'texture_pbr', 'mesh_convert',
              'texture_mesh', 'refine_mesh', 'mesh_to_rig'}


def check(title, condition, detail=''):
    (PASSED if condition else FAILED).append(title)
    print(f'{"ok  " if condition else "FAIL"} {title}' + (f'  [{detail}]' if detail and not condition else ''))


class Cancellation:
    def check(self):
        return None


class Context:
    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.cancellation = Cancellation()
        self.ticks = []
        self.logs = []

    def progress(self, percent, **fields):
        self.ticks.append(percent)

    def log(self, message, level='Info'):
        self.logs.append((level, message))

    def path(self, relative):
        target = self.workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        return target


def stand_ins(received, failing=()):
    def make(name, outputs):
        def handler(context, parameters):
            received[name] = dict(parameters)
            if name in failing:
                raise CyToolError('BackendFailure', f'{name} stand-in failed on purpose')
            return {key: str(Path(context.workspace) / value) if isinstance(value, str) else value
                    for key, value in outputs.items()}
        return handler

    return {name: make(name, outputs) for name, outputs in OUTPUTS.items()}


def load(name):
    return model.load(ROOT / 'data' / 'workflows' / (model.safe_name(name) + '.json'), set(MANIFEST))


def sample_input(document):
    """What a workflow is started on: a picture, a mesh, or the photographs of one subject."""
    if document.get('input_mode') == 'together':
        return [f'D:/photos/statue-{side}.jpg' for side in ('front', 'droite', 'gauche', 'dos')]
    first = next(step for step in document['steps'] if step['enabled'])
    return 'D:/models/scan.glb' if first['operation'] in MESH_FIRST else 'D:/pictures/statue.png'


def run(name, workspace, enable=(), source=None, failing=(), document=None):
    document = document or load(name)
    for step in document['steps']:
        if enable == 'all' or step['id'] in enable:
            step['enabled'] = True
    received = {}
    context = Context(workspace)
    source = sample_input(document) if source is None else source
    result = runner.run(context, document, stand_ins(received, failing), [source], schemas=SCHEMAS)
    return received, result, context


def main():
    folder = Path(tempfile.mkdtemp(prefix='wf-inputs-'))
    try:
        received, result, context = run('Image to production mesh (LocalMesh+)', folder / 'a')
        texture = received.get('texture_mesh', {})
        check('the first step receives the workflow input',
              received.get('prepare_subject', {}).get('front') == 'D:/pictures/statue.png',
              received.get('prepare_subject'))
        check('LocalMesh receives the prepared subject set',
              received.get('photos_to_mesh', {}).get('subject_set', '').endswith('subject'),
              received.get('photos_to_mesh'))
        check('QuadWild receives the lightened mesh',
              received.get('remesh_field', {}).get('input', '').endswith('light.obj'),
              received.get('remesh_field'))
        check('the texture step receives the quad mesh',
              texture.get('mesh_file', '').endswith('quad.obj'), texture)
        check('the texture step receives the detailed LocalMesh model',
              texture.get('detail_mesh', '').endswith('localmesh.glb'), texture)
        check('the texture step receives the subject set of the first step',
              texture.get('subject_set', '').endswith('subject')
              and '1-subject' in texture.get('subject_set', ''), texture)
        check('the workflow output is the textured model',
              result['outputs'] and result['outputs'][0].endswith('textured.glb'), result['outputs'])
        check('progress only moves forward', context.ticks == sorted(context.ticks), context.ticks)
        check('a step receives the defaults of its schema',
              received.get('remesh_field', {}).get('solverSeconds') == 300
              and 'featureAngle' in received.get('remesh_field', {}), received.get('remesh_field'))

        received, result, _ = run('Image to production mesh with generated views (experimental)',
                                  folder / 'b')
        check('the experimental workflow starts with the Wonder3D views',
              received.get('complete_subject', {}).get('image') == 'D:/pictures/statue.png',
              received.get('complete_subject'))
        check('its LocalMesh step fuses four views',
              received.get('photos_to_mesh', {}).get('mode') == 'four', received.get('photos_to_mesh'))
        check('its texture step still gets all three inputs',
              all(received.get('texture_mesh', {}).get(key) for key in
                  ('mesh_file', 'detail_mesh', 'subject_set')), received.get('texture_mesh'))

        # the optional refine step: off by default, and nothing downstream notices
        check('the refine step is off by default and does not run',
              'refine_mesh' not in received, sorted(received))
        received, result, _ = run('Image to production mesh (LocalMesh+)', folder / 'c')
        skipped = [step for step in result['results'][0]['steps'] if step.get('skipped')]
        check('a disabled step is reported as passed through',
              [step['id'] for step in skipped] == ['refine'], skipped)
        check('with refine off, QuadWild still gets the LocalMesh model, lightened',
              received.get('mesh_edit', {}).get('mesh_file', '').endswith('localmesh.glb'),
              received.get('mesh_edit'))
        check('with refine off, the normal map is still baked from the LocalMesh model',
              received.get('texture_mesh', {}).get('detail_mesh', '').endswith('localmesh.glb'),
              received.get('texture_mesh'))
        check('with refine off, the texture step keeps folder 6',
              '6-texture' in json.dumps(result['results'][0]['steps'][-1]['outputs']),
              result['results'][0]['steps'][-1])

        received, result, _ = run('Image to production mesh (LocalMesh+)', folder / 'd',
                                  enable=('refine',))
        check('switched on, refine receives the LocalMesh model and the subject set',
              received.get('refine_mesh', {}).get('mesh_file', '').endswith('localmesh.glb')
              and received.get('refine_mesh', {}).get('subject_set', '').endswith('subject'),
              received.get('refine_mesh'))
        check('switched on, the chain continues from the refined mesh',
              received.get('mesh_edit', {}).get('mesh_file', '').endswith('refined.glb'),
              received.get('mesh_edit'))
        check('switched on, the normal map is baked from the refined mesh',
              received.get('texture_mesh', {}).get('detail_mesh', '').endswith('refined.glb'),
              received.get('texture_mesh'))
        check('switched on, the texture step still gets its own folder number',
              '6-texture' in json.dumps(result['results'][0]['steps'][-1]['outputs']),
              result['results'][0]['steps'][-1])

        # the Hi3DGen variant: same chain, Hi3DGen for the shape
        received, result, _ = run('Image to production mesh with Hi3DGen', folder / 'e')
        check('Hi3DGen receives the prepared subject set',
              received.get('image_to_mesh_hi3dgen', {}).get('subject_set', '').endswith('subject'),
              received.get('image_to_mesh_hi3dgen'))
        check('the Hi3DGen mesh is lightened and remeshed',
              received.get('mesh_edit', {}).get('mesh_file', '').endswith('hi3dgen.glb'),
              received.get('mesh_edit'))
        check('the normal map is baked from the Hi3DGen mesh',
              received.get('texture_mesh', {}).get('detail_mesh', '').endswith('hi3dgen.glb'),
              received.get('texture_mesh'))
        received, result, _ = run('Image to production mesh with Hi3DGen', folder / 'f',
                                  enable=('refine',))
        check('ticked, refine regenerates the Hi3DGen mesh before the quads',
              received.get('refine_mesh', {}).get('mesh_file', '').endswith('hi3dgen.glb')
              and received.get('mesh_edit', {}).get('mesh_file', '').endswith('refined.glb'),
              [received.get('refine_mesh'), received.get('mesh_edit')])

        # the game asset and the rigged character: AutoRemesher between the model and its texture
        received, result, _ = run('Image to game asset (LocalMesh, AutoRemesher)', folder / 'g')
        check('AutoRemesher receives the lightened OBJ',
              received.get('remesh_auto', {}).get('input_file', '').endswith('light.obj')
              and received.get('mesh_edit', {}).get('output_format') == 'obj',
              [received.get('remesh_auto'), received.get('mesh_edit')])
        check('the game asset is textured on the AutoRemesher quads, relief from LocalMesh',
              received.get('texture_mesh', {}).get('mesh_file', '').endswith('remeshed.obj')
              and received.get('texture_mesh', {}).get('detail_mesh', '').endswith('localmesh.glb')
              and received.get('texture_mesh', {}).get('texture_size') == 2048,
              received.get('texture_mesh'))
        received, result, _ = run('Image to rigged character (LocalMesh, UniRig)', folder / 'h')
        check('UniRig rigs the textured game mesh',
              received.get('mesh_to_rig', {}).get('mesh', '').endswith('textured.glb'),
              received.get('mesh_to_rig'))
        check('the rigged model is the workflow output',
              result['outputs'] and result['outputs'][0].endswith('rigged.glb'), result['outputs'])

        # retopology of an existing textured mesh: its own texture is transferred back
        received, result, _ = run('Retopologise a textured mesh (QuadWild, texture kept)', folder / 'i')
        texture = received.get('texture_mesh', {})
        check('the retopology starts from the mesh it was given',
              received.get('mesh_edit', {}).get('mesh_file') == 'D:/models/scan.glb',
              received.get('mesh_edit'))
        check('the texture is transferred from the original onto the quads',
              texture.get('texture_source') == 'transfer' and texture.get('mesh_file', '').endswith('quad.obj')
              and texture.get('detail_mesh') == 'D:/models/scan.glb', texture)

        # a textured mesh to a game asset: AutoRemesher reads only OBJ and drops the materials
        received, result, _ = run('Mesh to game asset', folder / 'i2')
        check('the game asset gives AutoRemesher an OBJ, then transfers the original texture',
              received.get('mesh_edit', {}).get('output_format') == 'obj'
              and received.get('remesh_auto', {}).get('input_file', '').endswith('light.obj')
              and received.get('texture_mesh', {}).get('texture_source') == 'transfer'
              and received.get('texture_mesh', {}).get('detail_mesh') == 'D:/models/scan.glb',
              [received.get('remesh_auto'), received.get('texture_mesh')])
        received, result, _ = run('Mesh to game asset', folder / 'i3', failing=('texture_mesh',))
        check('without a texture to transfer, the quad mesh is still delivered',
              result['outputs'] and result['outputs'][0].endswith('remeshed.obj')
              and result['failedSteps'][0]['id'] == 'texture', result)

        # the print: one clean, Z-up, 100 mm STL
        received, result, _ = run('Image to 3D print (STL)', folder / 'j')
        edit = received.get('mesh_edit', {})
        actions = [item['action'] for item in edit.get('steps', [])]
        check('the print step cleans, turns Z-up, scales and exports STL',
              edit.get('mesh_file', '').endswith('localmesh.glb') and edit.get('output_format') == 'stl'
              and actions == ['keep_largest', 'fill_holes', 'fix_normals', 'swap_up_axis',
                              'scale_to_size', 'recenter_base'], edit)

        # the comparison: every engine reads the same cut-out, and one failure stops nothing
        received, result, context = run('Compare the shape engines on one image', folder / 'k')
        engines = ('image_to_mesh_triposr', 'image_to_mesh_spar3d', 'image_to_mesh_hi3dgen', 'photos_to_mesh')
        check('the four engines all receive the prepared subject set',
              all(received.get(name, {}).get('subject_set', '').endswith('subject') for name in engines),
              {name: received.get(name, {}).get('subject_set') for name in engines})
        received, result, context = run('Compare the shape engines on one image', folder / 'l',
                                        failing=('image_to_mesh_spar3d',))
        steps = {step['id']: step for step in result['results'][0]['steps']}
        check('an engine that fails is reported and the others still run',
              steps['spar3d']['ok'] is False and steps['hi3dgen']['ok'] and steps['localmesh']['ok']
              and 'photos_to_mesh' in received and result['failedSteps'][0]['id'] == 'spar3d',
              steps)
        check('the comparison still ends on the LocalMesh model',
              result['outputs'] and result['outputs'][0].endswith('localmesh.glb'), result['outputs'])
        check('the tolerated failure is logged as a warning',
              any(level == 'Warning' and 'spar3d' in message.lower() for level, message in context.logs),
              context.logs)
        try:
            run('Image to production mesh (LocalMesh+)', folder / 'm', failing=('remesh_field',))
            check('a failure without continue_on_error still stops the workflow', False)
        except CyToolError as exc:
            check('a failure without continue_on_error still stops the workflow',
                  'remesh_field' in str(exc), str(exc))

        # four photographs taken together as one subject
        document = load('Four photos to production mesh (LocalMesh+)')
        check('the four-photo workflow takes its folder together', document['input_mode'] == 'together')
        received, result, _ = run('', folder / 'n', document=document)
        prepared = roles_from_names(received.get('prepare_subject', {}))
        check('prepare_subject receives the four photographs as one list',
              len(received.get('prepare_subject', {}).get('images', [])) == 4, received.get('prepare_subject'))
        check('their roles come from the file names, in French as in English',
              prepared.get('front', '').endswith('front.jpg') and prepared.get('right', '').endswith('droite.jpg')
              and prepared.get('left', '').endswith('gauche.jpg') and prepared.get('back', '').endswith('dos.jpg')
              and prepared.get('images') == [], prepared)
        check('the four-photo chain fuses four views and textures from them',
              received.get('photos_to_mesh', {}).get('mode') == 'four'
              and received.get('texture_mesh', {}).get('multiview_texture') is True,
              [received.get('photos_to_mesh'), received.get('texture_mesh')])
        check('the report keeps the list of photographs as the input',
              result['results'][0]['input'] == sample_input(document), result['results'][0]['input'])
        unnamed = roles_from_names({'images': ['D:/x/IMG_0001.jpg', 'D:/x/IMG_0002.jpg', 'D:/x/Arrière.png']})
        check('without a named front, the first unnamed photograph becomes the front',
              unnamed.get('front') == 'D:/x/IMG_0001.jpg' and unnamed.get('back') == 'D:/x/Arrière.png'
              and unnamed.get('images') == ['D:/x/IMG_0002.jpg'], unnamed)
        kept = roles_from_names({'front': 'D:/x/a.png', 'images': ['D:/x/b-left.png']})
        check('an explicit front leaves the list untouched', kept.get('images') == ['D:/x/b-left.png']
              and not kept.get('left'), kept)

        # every saved workflow: valid, runs with its optional steps off and on
        for path in sorted((ROOT / 'data' / 'workflows').glob('*.json')):
            for enable in ((), 'all'):
                label = f'"{path.stem}"' + (' with every step on' if enable else '')
                try:
                    document = model.load(path, set(MANIFEST))
                    _, result, context = run('', folder / 'all' / path.stem / str(bool(enable)),
                                             enable=enable, document=document)
                    ran = [step for step in result['results'][0]['steps'] if not step.get('skipped')]
                    check(f'{label} runs every enabled step and produces an output',
                          all(step['ok'] for step in ran) and result['outputs'],
                          result['results'][0]['steps'])
                except Exception as exc:  # noqa: BLE001 - the report names the workflow
                    check(f'{label} runs every enabled step and produces an output', False, exc)

        # an unticked step reserves nothing: a disabled 24 GiB refinement once made the whole
        # workflow ask for more than the card had, and the scheduler refused it silently
        document = load('Image to production mesh (LocalMesh+)')
        per_step = {'refine_mesh': 24, 'photos_to_mesh': 14, 'texture_mesh': 10}

        def stub(step):
            gib = per_step.get(step['operation'])
            return {'vramBytes': {'auto': gib * 1024 ** 3}} if gib else {}

        off = runner.estimate(document, MANIFEST, step_estimate=stub)['vramBytes']['auto'] / 1024 ** 3
        for step in document['steps']:
            if step['id'] == 'refine':
                step['enabled'] = True
        on = runner.estimate(document, MANIFEST, step_estimate=stub)['vramBytes']['auto'] / 1024 ** 3
        check('an unticked step reserves nothing', off == 14, off)
        check('a ticked step counts in the reservation', on == 24, on)

        # an extra input may not read from a later step
        try:
            model.validate({'steps': [{'id': 'a', 'operation': 'mesh_edit',
                                       'extra_inputs': [{'from': 'b', 'to': 'mesh_file'}]},
                                      {'id': 'b', 'operation': 'mesh_edit'}]})
            check('an extra input from a later step is refused', False)
        except model.WorkflowError:
            check('an extra input from a later step is refused', True)
        document = model.validate({'steps': [{'id': 'a', 'operation': 'mesh_edit',
                                              'extra_inputs': [{'from': '@input', 'to': 'report'}]}]})
        check('@input names the file the workflow was started on',
              document['steps'][0]['extra_inputs'][0]['from'] == '@input')
        try:
            model.validate({'input_mode': 'sometimes', 'steps': [{'id': 'a', 'operation': 'mesh_edit'}]})
            check('an unknown input mode is refused', False)
        except model.WorkflowError:
            check('an unknown input mode is refused', True)
        # a misspelt parameter is refused before the step runs, naming the step
        document = model.validate({'steps': [{'id': 'quads', 'operation': 'remesh_field',
                                              'parameters': {'solverSeconds': 99999}}]})
        try:
            runner.run(Context(folder / 'o'), document, stand_ins({}), ['D:/models/scan.obj'], schemas=SCHEMAS)
            check('a parameter outside its schema is refused before the step runs', False)
        except CyToolError as exc:
            check('a parameter outside its schema is refused before the step runs',
                  exc.code == 'InvalidParameters' and '"quads"' in str(exc), str(exc))
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    print(json.dumps({'passed': len(PASSED), 'failed': len(FAILED)}))
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
