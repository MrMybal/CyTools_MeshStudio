"""Move the assets of the absorbed Tools into CyTools_MeshStudio.

The eleven Tools listed in ``SOURCE_TOOLS`` are replaced by this one. Their model
weights, engine sources and native binaries are *moved* (not copied): the machine has
no room for a second copy, and the user deletes the old folders afterwards. Every move
is recorded in ``data/reports/migration-manifest.json`` so that ``rollback`` can put
every folder back where it came from.

Two weight folders can hold the same upstream revision (Zero123++ v1.2 was installed
both by MeshConstruct and by ViewGenerator). Such an entry declares ``duplicate_of``;
before the copy is skipped, the two trees are compared file by file (relative path and
size, then SHA-256 of the largest common file). A copy that does not match is kept and
reported instead of being silently dropped.

Nothing here downloads anything and nothing is deleted: a skipped duplicate stays in
the old Tool, which the user removes when they remove the folder.

Usage:
    python app/scripts/migrate_assets.py plan
    python app/scripts/migrate_assets.py apply [--only ID ...] [--yes]
    python app/scripts/migrate_assets.py rollback [--only ID ...]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
WORKSPACE = ROOT.parent
MANIFEST = ROOT / 'data' / 'reports' / 'migration-manifest.json'

SOURCE_TOOLS = ('CyTools_AutoRemesher', 'CyTools_QuadWild', 'CyTools_Xatlas', 'CyTools_Trellis2Texture',
                'CyTools_TripoSR', 'CyTools_SPAR3D', 'CyTools_UniRig', 'CyTools_LocalMesh',
                'CyTools_ViewGenerator', 'CyTools_MeshConstruct', 'CyTools_WHAM')

# id, kind, source tool, path inside that tool, destination inside CyTools_MeshStudio
MIGRATIONS = [
    # ---------------------------------------------------------------- model weights
    ('trellis2-4b', 'model', 'CyTools_LocalMesh', 'data/models/TRELLIS.2-4B', 'data/models/trellis2-4b', None),
    ('trellis-image-large', 'model', 'CyTools_LocalMesh', 'data/models/microsoft/TRELLIS-image-large', 'data/models/trellis-image-large', None),
    ('trellis2-4b-reconviagen', 'model', 'CyTools_LocalMesh', 'data/models/microsoft/TRELLIS.2-4B', 'data/models/trellis2-4b-reconviagen', None),
    ('localmesh-multivue', 'model', 'CyTools_LocalMesh', 'data/models/multivue', 'data/models/localmesh-multivue', None),
    ('dinov3-vitl16', 'model', 'CyTools_LocalMesh', 'data/models/facebook/dinov3-vitl16-pretrain-lvd1689m', 'data/models/dinov3-vitl16', None),
    ('birefnet-hr', 'model', 'CyTools_LocalMesh', 'data/models/BiRefNet_HR', 'data/models/birefnet-hr', None),
    ('localmesh-hf-modules', 'model', 'CyTools_LocalMesh', 'data/models/hf', 'data/models/localmesh-hf-modules', None),

    ('triposr', 'model', 'CyTools_TripoSR', 'data/models/triposr', 'data/models/triposr', None),
    ('triposr-cache', 'model', 'CyTools_TripoSR', 'data/models/cache', 'data/models/triposr-cache', None),

    ('spar3d', 'model', 'CyTools_SPAR3D', 'data/models/spar3d', 'data/models/spar3d', None),
    ('spar3d-cache', 'model', 'CyTools_SPAR3D', 'data/models/cache', 'data/models/spar3d-cache', None),

    ('unirig', 'model', 'CyTools_UniRig', 'data/models', 'data/models/unirig', None),

    ('zero123plus-v1.2', 'model', 'CyTools_MeshConstruct', 'data/models/zero123plus-v1.2', 'data/models/zero123plus-v1.2', None),
    ('zero123plus-v1.2-viewgen', 'model', 'CyTools_ViewGenerator', 'data/models/zero123plus-v1.2', 'data/models/zero123plus-v1.2', 'zero123plus-v1.2'),
    ('zero123plus-pipeline', 'model', 'CyTools_ViewGenerator', 'data/models/zero123plus-pipeline', 'data/models/zero123plus-pipeline', None),
    ('controlnet-zp12-normal', 'model', 'CyTools_ViewGenerator', 'data/models/controlnet-zp12-normal-gen-v1', 'data/models/controlnet-zp12-normal-gen-v1', None),
    ('dinov2-base', 'model', 'CyTools_ViewGenerator', 'data/models/dinov2-base', 'data/models/dinov2-base', None),
    ('sam2.1-hiera-base-plus', 'model', 'CyTools_ViewGenerator', 'data/models/sam2.1-hiera-base-plus', 'data/models/sam2.1-hiera-base-plus', None),

    ('sam2.1-hiera-large', 'model', 'CyTools_MeshConstruct', 'data/models/sam2.1-hiera-large', 'data/models/sam2.1-hiera-large', None),
    ('depth-anything-v2-small', 'model', 'CyTools_MeshConstruct', 'data/models/depth-anything-v2-small', 'data/models/depth-anything-v2-small', None),
    ('perspective-fields', 'model', 'CyTools_MeshConstruct', 'data/models/perspective-fields-paramnet-360cities', 'data/models/perspective-fields-paramnet-360cities', None),
    ('wonder3d-v1.0', 'model', 'CyTools_MeshConstruct', 'data/models/wonder3d-v1.0', 'data/models/wonder3d-v1.0', None),
    ('syncdreamer', 'model', 'CyTools_MeshConstruct', 'data/models/syncdreamer', 'data/models/syncdreamer', None),

    # ------------------------------------------------------------- engine sources
    ('src-triposr', 'source', 'CyTools_TripoSR', 'runtime/source/TripoSR', 'runtime/sources/TripoSR', None),
    ('src-spar3d', 'source', 'CyTools_SPAR3D', 'runtime/source/SPAR3D', 'runtime/sources/SPAR3D', None),
    ('src-unirig', 'source', 'CyTools_UniRig', 'runtime/backends/UniRig', 'runtime/sources/UniRig', None),
    ('src-localmesh', 'source', 'CyTools_LocalMesh', 'runtime/backends/localmesh-engine', 'runtime/sources/localmesh-engine', None),
    ('src-wham', 'source', 'CyTools_WHAM', 'runtime/backends/WHAM', 'runtime/sources/WHAM', None),
    ('src-wonder3d', 'source', 'CyTools_MeshConstruct', 'runtime/engines/wonder3d', 'runtime/sources/Wonder3D', None),
    ('src-syncdreamer', 'source', 'CyTools_MeshConstruct', 'runtime/engines/syncdreamer', 'runtime/sources/SyncDreamer', None),
    ('src-perspectivefields', 'source', 'CyTools_MeshConstruct', 'runtime/engines/perspectivefields', 'runtime/sources/PerspectiveFields', None),

    # ------------------------------------------------------------ native binaries
    ('native-autoremesher', 'native', 'CyTools_AutoRemesher', 'runtime/engines/1.2.0-1789863730411644000', 'runtime/natives/autoremesher-1.2.0', None),
    ('native-quadwild', 'native', 'CyTools_QuadWild', 'runtime/backends/v0.0.2', 'runtime/natives/quadwild-bimdf-v0.0.2', None),
    ('native-quadwild-archive', 'native', 'CyTools_QuadWild', 'runtime/sources/quadwild-bimdf-v0.0.2.zip', 'runtime/natives/quadwild-bimdf-v0.0.2.zip', None),
]


def entries(only=None):
    for item in MIGRATIONS:
        if only and item[0] not in only:
            continue
        yield dict(zip(('id', 'kind', 'tool', 'source', 'dest', 'duplicate_of'), item))


def tree_size(path):
    total = 0
    for base, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(base) / name).stat().st_size
            except OSError:
                pass
    return total


def size_of(path):
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    return tree_size(path)


def file_map(root):
    """Relative path -> size for every file of a tree, ignoring download caches."""
    result = {}
    root = Path(root)
    if root.is_file():
        return {root.name: root.stat().st_size}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ('.cache', '.huggingface', '__pycache__')]
        for name in files:
            path = Path(base) / name
            try:
                result[str(path.relative_to(root)).replace('\\', '/')] = path.stat().st_size
            except OSError:
                pass
    return result


def sha256(path, limit=None):
    digest = hashlib.sha256()
    read = 0
    with open(path, 'rb') as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            read += len(chunk)
            if limit and read >= limit:
                break
    return digest.hexdigest()


def compare_trees(left, right):
    """Report whether two model folders hold the same weights."""
    a, b = file_map(left), file_map(right)
    shared = sorted(set(a) & set(b), key=lambda k: -a[k])
    mismatched = [k for k in shared if a[k] != b[k]]
    only_left = sorted(set(a) - set(b))
    only_right = sorted(set(b) - set(a))
    result = {'sharedFiles': len(shared), 'mismatchedSizes': mismatched[:20],
              'onlyInExisting': only_left[:20], 'onlyInCandidate': only_right[:20],
              'identical': False, 'checkedFile': '', 'sha256': ''}
    if shared and not mismatched:
        biggest = shared[0]
        left_hash = sha256(Path(left) / biggest)
        right_hash = sha256(Path(right) / biggest)
        result.update({'checkedFile': biggest, 'sha256': left_hash,
                       'identical': left_hash == right_hash and not only_right})
    return result


def load_manifest():
    try:
        return json.loads(MANIFEST.read_text('utf-8'))
    except (OSError, ValueError):
        return {'schemaVersion': 1, 'moves': []}


def save_manifest(manifest):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def plan(only=None):
    rows, total, duplicate_bytes, missing = [], 0, 0, []
    for item in entries(only):
        source = WORKSPACE / item['tool'] / item['source']
        dest = ROOT / item['dest']
        if not source.exists():
            missing.append(item['id'])
            continue
        size = size_of(source)
        if item['duplicate_of']:
            duplicate_bytes += size
        elif not dest.exists():
            total += size
        rows.append((item, source, dest, size))
    return rows, total, duplicate_bytes, missing


def human(value):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(value) < 1024 or unit == 'TiB':
            return f'{value:,.1f} {unit}'.replace(',', ' ')
        value /= 1024.0


def command_plan(args):
    rows, total, duplicate_bytes, missing = plan(args.only)
    print(f'{"id":<28}{"kind":<8}{"size":>12}  source -> destination')
    for item, source, dest, size in rows:
        mark = ' [duplicate]' if item['duplicate_of'] else (' [destination exists]' if dest.exists() else '')
        print(f'{item["id"]:<28}{item["kind"]:<8}{human(size):>12}  {item["tool"]}/{item["source"]}{mark}')
    print()
    print(f'To move          : {human(total)}')
    print(f'Duplicates found : {human(duplicate_bytes)} (verified, then left in the old Tool)')
    if missing:
        print(f'Not present      : {", ".join(missing)}')
    return 0


def command_apply(args):
    rows, total, duplicate_bytes, missing = plan(args.only)
    if not rows:
        print('Nothing to migrate.')
        return 0
    if not args.yes:
        print(f'About to move {human(total)} into {ROOT}. Re-run with --yes to proceed.')
        return command_plan(args)
    manifest = load_manifest()
    done = {move['id'] for move in manifest['moves'] if move['state'] == 'Moved'}
    for item, source, dest, size in rows:
        if item['id'] in done:
            print(f'= {item["id"]}: already migrated')
            continue
        record = {'id': item['id'], 'kind': item['kind'], 'tool': item['tool'],
                  'from': str(source), 'to': str(dest), 'bytes': size,
                  'time': time.strftime('%Y-%m-%dT%H:%M:%S'), 'state': 'Pending'}
        if item['duplicate_of']:
            existing = ROOT / next(e['dest'] for e in entries() if e['id'] == item['duplicate_of'])
            if not existing.exists():
                print(f'! {item["id"]}: {item["duplicate_of"]} is not migrated yet, skipping this pass')
                continue
            comparison = compare_trees(existing, source)
            record['comparison'] = comparison
            record['state'] = 'DuplicateVerified' if comparison['identical'] else 'DuplicateMismatch'
            if comparison['identical']:
                print(f'~ {item["id"]}: identical to {item["duplicate_of"]} ({human(size)} not moved, '
                      f'checked {comparison["checkedFile"]})')
            else:
                print(f'! {item["id"]}: differs from {item["duplicate_of"]}, left untouched for review')
            manifest['moves'].append(record)
            save_manifest(manifest)
            continue
        if dest.exists():
            print(f'! {item["id"]}: destination already exists, skipped')
            record['state'] = 'DestinationExists'
            manifest['moves'].append(record)
            save_manifest(manifest)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        try:
            os.replace(source, dest)          # same volume: instant rename
            record['method'] = 'rename'
        except OSError:
            shutil.move(str(source), str(dest))
            record['method'] = 'copy+delete'
        record['state'] = 'Moved'
        record['seconds'] = round(time.monotonic() - started, 2)
        manifest['moves'].append(record)
        save_manifest(manifest)
        print(f'+ {item["id"]}: {human(size)} -> {item["dest"]} ({record["method"]}, {record["seconds"]}s)')
    print(f'\nManifest: {MANIFEST}')
    return 0


def command_rollback(args):
    manifest = load_manifest()
    restored = 0
    for move in reversed(manifest['moves']):
        if move['state'] != 'Moved':
            continue
        if args.only and move['id'] not in args.only:
            continue
        source, dest = Path(move['from']), Path(move['to'])
        if not dest.exists():
            print(f'! {move["id"]}: {dest} is gone, cannot restore')
            continue
        if source.exists():
            print(f'! {move["id"]}: {source} exists again, not overwriting')
            continue
        source.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(dest, source)
        except OSError:
            shutil.move(str(dest), str(source))
        move['state'] = 'RolledBack'
        restored += 1
        print(f'< {move["id"]}: restored to {source}')
    save_manifest(manifest)
    print(f'{restored} folder(s) restored.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name, handler in (('plan', command_plan), ('apply', command_apply), ('rollback', command_rollback)):
        item = sub.add_parser(name)
        item.add_argument('--only', nargs='*', default=None, help='restrict to these migration ids')
        if name == 'apply':
            item.add_argument('--yes', action='store_true', help='actually move the folders')
        item.set_defaults(handler=handler)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == '__main__':
    raise SystemExit(main())
