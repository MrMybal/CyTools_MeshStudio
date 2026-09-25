"""Runtime tests: the manifest, the isolation between clients, and a real mesh operation.

They run against a throw-away data directory, so they never touch ``data/``. The only heavy
thing they exercise is the geometry engine, which is CPU-only; the model backends are covered
by their own runs, reported in ``data/reports/VALIDATION.md``.

    runtime/python/Scripts/python.exe app/test_tool.py
"""
from pathlib import Path
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from tool import create_runtime  # noqa: E402

ROOT = APP.parent
FIXTURE = ROOT / 'data' / 'inputs' / 'test-sphere.obj'


class ManifestTests(unittest.TestCase):
    def test_every_operation_has_a_handler(self):
        with tempfile.TemporaryDirectory() as root, create_runtime(root) as runtime:
            declared = {item['id'] for item in runtime.descriptor['operations']}
            for operation in sorted(declared):
                # An operation nobody can run is a promise the manifest does not keep.
                self.assertIsNotNone(runtime.operation(operation), operation)
            self.assertIn('diagnose', declared)
            self.assertIn('photos_to_mesh', declared)

    def test_unknown_operation_is_refused(self):
        from cytools_core import CyToolError
        with tempfile.TemporaryDirectory() as root, create_runtime(root) as runtime:
            actor = runtime.authenticate(runtime.create_client('Alice')['token'])
            session = runtime.create_session(actor)
            with self.assertRaises(CyToolError):
                runtime.submit(actor, session['sessionId'], 'no_such_operation', {})


class IsolationTests(unittest.TestCase):
    def test_a_client_does_not_see_the_jobs_of_another(self):
        with tempfile.TemporaryDirectory() as root, create_runtime(root) as runtime:
            alice = runtime.authenticate(runtime.create_client('Alice')['token'])
            bob = runtime.authenticate(runtime.create_client('Bob')['token'])
            session = runtime.create_session(alice)
            job = runtime.submit(alice, session['sessionId'], 'list_models', {})
            result = runtime.wait(alice, job['jobId'])
            self.assertEqual(result['state'], 'Completed')
            self.assertIn('models', result['outputs'])
            self.assertEqual(runtime.list_jobs(bob), [])


@unittest.skipUnless(FIXTURE.is_file(), f'fixture mesh missing: {FIXTURE}')
class GeometryTests(unittest.TestCase):
    def test_mesh_inspect_reads_a_real_mesh(self):
        with tempfile.TemporaryDirectory() as root, create_runtime(root) as runtime:
            actor = runtime.authenticate(runtime.create_client('Alice')['token'])
            session = runtime.create_session(actor)
            job = runtime.submit(actor, session['sessionId'], 'mesh_inspect',
                                 {'mesh_file': str(FIXTURE)})
            result = runtime.wait(actor, job['jobId'], timeout=600)
            self.assertEqual(result['state'], 'Completed', result.get('error'))
            self.assertGreater(result['outputs'].get('faces', 0), 0)
            self.assertGreater(result['outputs'].get('vertices', 0), 0)

    def test_a_missing_file_fails_with_a_clear_error(self):
        with tempfile.TemporaryDirectory() as root, create_runtime(root) as runtime:
            actor = runtime.authenticate(runtime.create_client('Alice')['token'])
            session = runtime.create_session(actor)
            job = runtime.submit(actor, session['sessionId'], 'mesh_inspect',
                                 {'mesh_file': str(ROOT / 'data' / 'inputs' / 'nothing-here.obj')})
            result = runtime.wait(actor, job['jobId'], timeout=120)
            self.assertEqual(result['state'], 'Failed')
            self.assertIn(result['error']['code'], ('MissingInput', 'InvalidInput'))


if __name__ == '__main__':
    unittest.main()
