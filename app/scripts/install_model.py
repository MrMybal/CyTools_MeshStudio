"""Download the weights of a model that is declared but absent.

The plan lives in ``app/models/install.json``. Automatic items are fetched and verified here;
an item marked ``manual`` is a file whose licence is accepted in person on its own page, so it
is never downloaded by the application — it is imported afterwards from the file the user
obtained, by the ``import_model_file`` operation.

Run as a subprocess by the ``install_model`` operation, so every line printed here becomes a
progress message and lands in ``data/logs/install-model-*.log``.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'app' / 'models' / 'install.json'
ARCHIVE_LIMIT = 4 * 1024 ** 3


def plans():
    return json.loads(PLAN.read_text('utf-8'))['models']


def say(message):
    print(message, flush=True)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def receipt_path(directory):
    return directory / 'cytools-receipt.json'


def read_receipt(directory):
    try:
        return json.loads(receipt_path(directory).read_text('utf-8'))
    except (OSError, ValueError):
        return {}


def key_of(directory, path):
    return str(path.relative_to(directory)).replace('\\', '/')


def record(directory, path):
    receipt = read_receipt(directory)
    receipt[key_of(directory, path)] = {'size': path.stat().st_size, 'sha256': sha256(path)}
    receipt_path(directory).write_text(json.dumps(receipt, indent=2, sort_keys=True),
                                       encoding='utf-8')


def verify_binary(path):
    """A refused Google Drive download arrives as an HTML page with a 200 status."""
    if path.stat().st_size < 1024:
        raise ValueError(f'Truncated download: {path.name}')
    with path.open('rb') as stream:
        head = stream.read(256).lstrip().lower()
    if head.startswith((b'<html', b'<!doctype', b'{"error')):
        raise ValueError('The server returned a page instead of the file '
                         f'({path.name}): Google Drive quota, or the file moved.')


def safe_member(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Unsafe path inside the archive: {name}')
    return path


def gdrive(file_id, destination):
    import gdown
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + '.partial')
    result = gdown.download(id=file_id, output=str(partial), quiet=False, resume=True)
    if not result:
        raise RuntimeError('Download refused, or the Google Drive quota was reached. '
                           'Try again later, or fetch the file by hand and import it.')
    verify_binary(partial)
    partial.replace(destination)
    return destination


USER_AGENT = 'CyTools_MeshStudio model installer'


def http_download(url, destination, size=None, expected_sha256=None, label=''):
    """Resumable HTTPS download into ``destination``, checked before it is put in place.

    A ``.partial`` file is continued with a Range request; the size and, when the publisher
    gives one, the SHA-256 are checked before the rename, so a truncated or substituted file
    never takes the place of a model.
    """
    import urllib.error
    import urllib.request

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + '.partial')
    offset = partial.stat().st_size if partial.exists() else 0
    if size and offset > size:
        partial.unlink()
        offset = 0
    if not (size and offset == size):
        headers = {'User-Agent': USER_AGENT}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as answer:
                resumed = offset and answer.status == 206
                mode = 'ab' if resumed else 'wb'
                done = offset if resumed else 0
                total = size or (done + int(answer.headers.get('Content-Length') or 0))
                step = max(total // 20, 16 * 1024 ** 2) if total else 64 * 1024 ** 2
                mark = done + step
                with partial.open(mode) as sink:
                    while True:
                        chunk = answer.read(4 * 1024 ** 2)
                        if not chunk:
                            break
                        sink.write(chunk)
                        done += len(chunk)
                        if done >= mark:
                            say(f'  {label or destination.name}: {done / 1024 ** 2:,.0f} / '
                                f'{total / 1024 ** 2:,.0f} MiB')
                            mark += step
        except urllib.error.URLError as exc:
            raise RuntimeError(f'Download failed for {url}: {exc}. Run the installation again: '
                               'it resumes where it stopped.') from exc
    if size and partial.stat().st_size != size:
        raise ValueError(f'{destination.name}: {partial.stat().st_size} bytes instead of {size}; '
                         'run the installation again to resume.')
    digest = sha256(partial)
    if expected_sha256 and digest != expected_sha256:
        partial.unlink()
        raise ValueError(f'{destination.name}: SHA-256 {digest[:16]}… does not match the '
                         f'published {expected_sha256[:16]}…; the file was discarded.')
    partial.replace(destination)
    return destination


def huggingface(item, directory):
    """Every file of a Hugging Face repository at a pinned revision, checked one by one."""
    written = []
    for entry in item['files']:
        target = directory / item.get('target', '.') / entry['path']
        if target.is_file() and (not entry.get('size') or target.stat().st_size == entry['size']):
            if not entry.get('sha256') or sha256(target) == entry['sha256']:
                written.append(target)
                continue
        url = (f'https://huggingface.co/{item["repo"]}/resolve/{item["revision"]}/'
               f'{entry["path"]}')
        http_download(url, target, size=entry.get('size'), expected_sha256=entry.get('sha256'),
                      label=entry['path'])
        written.append(target)
    return written


def extract_tar(archive, directory, item):
    """Extract one prefix of a tar archive under ``directory``, entry by entry."""
    target_root = directory / item['target']
    written = []
    with tarfile.open(archive) as bundle:
        entries = bundle.getmembers()
        if sum(entry.size for entry in entries) > ARCHIVE_LIMIT:
            raise ValueError('The auxiliary archive is larger than expected.')
        for entry in entries:
            safe_member(entry.name)
            if not (entry.isfile() or entry.isdir()):
                raise ValueError('The archive contains a link, which is refused.')
        for entry in entries:
            if not entry.isfile():
                continue
            relative = safe_member(entry.name)
            if item.get('prefix') and relative.parts[0] != item['prefix']:
                raise ValueError(f'Unexpected entry in the archive: {entry.name}')
            parts = relative.parts[1:] if item.get('prefix') else relative.parts
            destination = target_root.joinpath(*parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(entry) as source, destination.open('wb') as sink:
                shutil.copyfileobj(source, sink)
            written.append(destination)
    return written


def item_files(directory, item):
    """Every file this item is supposed to leave on disk."""
    if item['kind'] == 'huggingface':
        return [directory / item.get('target', '.') / entry['path'] for entry in item['files']]
    target = directory / item['target']
    if item['kind'] == 'gdrive-tar':
        return [target / name for name in item.get('provides', [])] or [target]
    return [target]


def present(directory, item):
    receipt = read_receipt(directory)
    for path in item_files(directory, item):
        if not path.is_file():
            return False
        key = key_of(directory, path)
        if key in receipt and path.stat().st_size != receipt[key]['size']:
            return False
    return True


def install(model, repair=False, include_optional=True):
    plan = plans().get(model)
    if plan is None:
        raise SystemExit(f'No install plan for model "{model}".')
    directory = ROOT / plan['directory']
    directory.mkdir(parents=True, exist_ok=True)
    say(f'Model "{model}" -> {directory}')
    say(f'Licence: {plan.get("license", "see the model page")}')

    automatic = [i for i in plan['items'] if i['kind'] != 'manual'
                 and (include_optional or not i.get('optional'))]
    manual = [i for i in plan['items'] if i['kind'] == 'manual']
    downloads = ROOT / 'runtime' / 'downloads'
    downloads.mkdir(parents=True, exist_ok=True)

    for index, item in enumerate(automatic, 1):
        head = f'[{index}/{len(automatic)}] {item["label"]}'
        if not repair and present(directory, item):
            say(f'{head}: already present, kept.')
            continue
        say(f'{head}: downloading (resumable)...')
        if item['kind'] == 'gdrive':
            path = gdrive(item['id'], directory / item['target'])
            record(directory, path)
            say(f'{head}: {path.stat().st_size / 1024 ** 2:.1f} MiB verified.')
        elif item['kind'] == 'gdrive-tar':
            archive = downloads / f'{model}-{item["id"]}.tar.gz'
            gdrive(item['id'], archive)
            for path in extract_tar(archive, directory, item):
                record(directory, path)
            say(f'{head}: archive extracted and recorded.')
        elif item['kind'] == 'huggingface':
            for path in huggingface(item, directory):
                record(directory, path)
            say(f'{head}: {len(item["files"])} file(s) of {item["repo"]} at '
                f'{item["revision"][:12]} verified.')
        elif item['kind'] == 'url':
            path = http_download(item['url'], directory / item['target'], size=item.get('size'),
                                 expected_sha256=item.get('sha256'), label=item['label'])
            record(directory, path)
            say(f'{head}: {path.stat().st_size / 1024 ** 2:.1f} MiB, SHA-256 recorded.')
        else:
            raise SystemExit(f'Unknown item kind "{item["kind"]}" in the plan.')

    for item in manual:
        path = directory / item['target']
        if path.is_file():
            say(f'Present: {item["label"]}.')
        else:
            say(f'STILL REQUIRED: {item["label"]} -> {item["page"]}')
            say(f'  {item["note"]}')
    say('Done.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model')
    parser.add_argument('--repair', action='store_true', help='download again even if present')
    parser.add_argument('--skip-optional', action='store_true', help='leave optional items out')
    args = parser.parse_args(argv)
    return install(args.model, repair=args.repair, include_optional=not args.skip_optional)


if __name__ == '__main__':
    raise SystemExit(main())
