"""Real MCP round trip: start the stdio server, list the tools, run a job, wait for it.

    runtime/python/Scripts/python.exe app/tests/validate_mcp.py

Nothing is simulated: the server is the very ``app/tool.py mcp`` an AI client would start,
and the evidence it writes to data/reports/mcp-validation.json is the job the client saw.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import time

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

from tool import create_runtime  # noqa: E402

DATA = ROOT / 'data'
SPHERE = DATA / 'inputs' / 'test-sphere.obj'


async def main():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    if not SPHERE.is_file():
        raise SystemExit(f'Missing test input {SPHERE}; create it first (see app/tests/README.md).')

    directory = DATA / 'test-runs' / 'mcp'
    directory.mkdir(parents=True, exist_ok=True)
    with create_runtime(directory) as runtime:
        token = runtime.create_client('MCP validation', ['filesystemExternal'])['token']

    server = StdioServerParameters(
        command=sys.executable, args=[str(APP / 'tool.py'), '--data-dir', str(directory), 'mcp'],
        env={**os.environ, 'CYTOOLS_TOKEN': token, 'PYTHONIOENCODING': 'utf-8'})

    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            expected = {'op_uv_unwrap', 'op_remesh_auto', 'op_mesh_edit', 'op_run_workflow', 'op_diagnose'}
            missing = expected - names
            if missing:
                raise SystemExit(f'The MCP catalogue is missing {sorted(missing)}')

            response = await session.call_tool('op_uv_unwrap', {'parameters': {
                'input': str(SPHERE), 'resolution': 512, 'padding': 4, 'iterations': 1,
                'maxCost': 2.0, 'bruteForce': False, 'rotateCharts': True,
                'blockAlign': False, 'fixWinding': False}})
            if response.isError:
                raise SystemExit(f'MCP call failed: {response}')
            job = json.loads(response.content[0].text)

            deadline = time.monotonic() + 180
            while job['state'] not in ('Completed', 'Failed', 'Cancelled'):
                if time.monotonic() > deadline:
                    raise SystemExit(f'The job did not finish within 180s: {job["state"]}')
                await asyncio.sleep(0.1)
                response = await session.call_tool('cy_get_job', {'jobId': job['jobId']})
                job = json.loads(response.content[0].text)
            if job['state'] != 'Completed':
                raise SystemExit(f'Job ended as {job["state"]}: {json.dumps(job.get("error"))}')

            evidence = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'transport': 'MCP stdio',
                        'toolCount': len(names), 'tools': sorted(names), 'job': job}
            report = DATA / 'reports' / 'mcp-validation.json'
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding='utf-8')
            print(json.dumps({'transport': 'MCP stdio', 'tools': len(names), 'state': job['state'],
                              'charts': job['outputs']['charts'], 'report': str(report)}))


if __name__ == '__main__':
    asyncio.run(main())
