"""Build app/models/catalog.json from what is actually installed in data/models.

The catalogue is the single place where the Tool declares a model: which family it
belongs to, which engine and backends use it, where it comes from, under which licence,
how big it is and which files prove it is complete. Sizes and file lists are measured on
disk; revisions and hashes are read from the installation receipts the absorbed Tools
left next to the weights. A value that no receipt provides is written as null rather
than guessed, and the entry is marked ``revisionKnown: false``.

Run it again after installing or repairing a model:
    python app/scripts/build_catalog.py
"""
import json
import os
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
MODELS = ROOT / 'data' / 'models'
OUT = APP / 'models' / 'catalog.json'

# id -> descriptive metadata. Everything measurable is read from disk instead.
METADATA = {
    'trellis2-4b': dict(
        name='TRELLIS.2-4B (FP8)', family='reconstruction', engine='trellis', backends=['trellis'],
        repository='Qtn-Cls/LocalMeshEngine', url='https://huggingface.co/Qtn-Cls/LocalMeshEngine',
        license='MIT (engine packaging); TRELLIS.2 weights under their upstream terms',
        nonCommercial=False, gated=False, required=True,
        purpose='Photographs to a textured mesh: sparse structure, shape and texture flows.'),
    'trellis-image-large': dict(
        name='TRELLIS-image-large (sparse decoder)', family='reconstruction', engine='trellis', backends=['trellis'],
        repository='microsoft/TRELLIS-image-large', url='https://huggingface.co/microsoft/TRELLIS-image-large',
        license='MIT', nonCommercial=False, gated=False, required=True,
        purpose='Sparse structure decoder used by the TRELLIS.2 pipeline.'),
    'trellis2-4b-reconviagen': dict(
        name='TRELLIS.2-4B pipeline description', family='reconstruction', engine='trellis', backends=['trellis'],
        repository='microsoft/TRELLIS.2-4B', url='https://huggingface.co/microsoft/TRELLIS.2-4B',
        license='MIT', nonCommercial=False, gated=False, required=True,
        purpose='Pipeline definition consumed by the engine.'),
    'localmesh-multivue': dict(
        name='LocalMesh multi-view camera stack', family='reconstruction', engine='trellis', backends=['trellis'],
        repository='Qtn-Cls/LocalMeshEngine', url='https://huggingface.co/Qtn-Cls/LocalMeshEngine',
        license='See the engine LICENSE and NOTICE', nonCommercial=False, gated=False, required=False,
        purpose='Camera estimation and vendored dependencies for the four-view mode.'),
    'dinov3-vitl16': dict(
        name='DINOv3 ViT-L/16', family='features', engine='trellis', backends=['trellis'],
        repository='facebook/dinov3-vitl16-pretrain-lvd1689m',
        url='https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m',
        license='Meta DINOv3 License; personal acceptance required on the model page',
        nonCommercial=False, gated=True, required=True,
        purpose='Image features for the TRELLIS.2 pipeline. Built with DINOv3.'),
    'birefnet-hr': dict(
        name='BiRefNet HR', family='matting', engine='trellis', backends=['trellis'],
        repository='ZhengPeng7/BiRefNet_HR', url='https://huggingface.co/ZhengPeng7/BiRefNet_HR',
        license='MIT (includes model Python code)', nonCommercial=False, gated=False, required=False,
        purpose='High resolution background removal before reconstruction.'),
    'localmesh-hf-modules': dict(
        name='Hugging Face dynamic modules cache', family='support', engine='trellis', backends=['trellis'],
        repository='', url='', license='Belongs to the models it was generated from',
        nonCommercial=False, gated=False, required=False,
        purpose='Remote code modules already downloaded for the engine.'),

    'triposr': dict(
        name='TripoSR', family='reconstruction', engine='torch-cu124', backends=['triposr'],
        repository='stabilityai/TripoSR', url='https://huggingface.co/stabilityai/TripoSR',
        license='MIT (code); weights under the Stability AI Community License',
        nonCommercial=False, gated=False, required=True,
        purpose='Single image to mesh in seconds, feed-forward NeRF plus marching cubes.'),
    'triposr-cache': dict(
        name='TripoSR auxiliary models (DINO ViT-B/16, U2Net)', family='support', engine='torch-cu124',
        backends=['triposr'], repository='facebook/dino-vitb16',
        url='https://huggingface.co/facebook/dino-vitb16',
        license='Apache-2.0 (DINO); U2Net under Apache-2.0', nonCommercial=False, gated=False, required=True,
        purpose='Image backbone and background removal used by TripoSR.'),

    'spar3d': dict(
        name='SPAR3D', family='reconstruction', engine='torch-cu124', backends=['spar3d'],
        repository='stabilityai/stable-point-aware-3d',
        url='https://huggingface.co/stabilityai/stable-point-aware-3d',
        license='Stability AI Community License', nonCommercial=False, gated=True, required=True,
        purpose='Image to a textured mesh and a point cloud, with editable backside inference.'),
    'spar3d-cache': dict(
        name='SPAR3D auxiliary models (DINOv2-L, Alpha-CLIP, transparent-background)', family='support',
        engine='torch-cu124', backends=['spar3d'], repository='facebook/dinov2-large',
        url='https://huggingface.co/facebook/dinov2-large',
        license='Apache-2.0 (DINOv2); Alpha-CLIP and transparent-background under their own terms',
        nonCommercial=False, gated=False, required=True,
        purpose='Image backbone, region conditioning and matting used by SPAR3D.'),

    'unirig': dict(
        name='UniRig Articulation-XL (skeleton and skin)', family='rigging', engine='torch-cu124',
        backends=['unirig'], repository='VAST-AI/UniRig', url='https://huggingface.co/VAST-AI/UniRig',
        license='MIT (code); Articulation-XL weights under their own terms',
        nonCommercial=False, gated=False, required=True,
        purpose='Predicts a skeleton and skinning weights for a mesh.'),

    'zero123plus-v1.2': dict(
        name='Zero123++ v1.2', family='views', engine='diffusion', backends=['zero123plus'],
        repository='sudo-ai/zero123plus-v1.2', url='https://huggingface.co/sudo-ai/zero123plus-v1.2',
        license='CC-BY-NC-4.0 (weights); reference code Apache-2.0', nonCommercial=True, gated=False, required=True,
        purpose='Six consistent synthetic views of an object from one reference image.'),
    'zero123plus-pipeline': dict(
        name='Zero123++ pipeline code', family='views', engine='diffusion', backends=['zero123plus'],
        repository='sudo-ai/zero123plus-pipeline', url='https://huggingface.co/sudo-ai/zero123plus-pipeline',
        license='Apache-2.0', nonCommercial=False, gated=False, required=True,
        purpose='Diffusers pipeline implementation loaded with the weights.'),
    'controlnet-zp12-normal-gen-v1': dict(
        name='Zero123++ normal ControlNet', family='views', engine='diffusion', backends=['zero123plus'],
        repository='sudo-ai/controlnet-zp12-normal-gen-v1',
        url='https://huggingface.co/sudo-ai/controlnet-zp12-normal-gen-v1',
        license='CC-BY-NC-4.0', nonCommercial=True, gated=False, required=False,
        purpose='Optional normal map generation alongside the synthetic views.'),
    'dinov2-base': dict(
        name='DINOv2 ViT-B/14', family='features', engine='diffusion', backends=['zero123plus', 'mirror'],
        repository='facebook/dinov2-base', url='https://huggingface.co/facebook/dinov2-base',
        license='Apache-2.0', nonCommercial=False, gated=False, required=True,
        purpose='Identity and similarity scoring between real and generated views.'),
    'sam2.1-hiera-base-plus': dict(
        name='SAM 2.1 Hiera base+', family='segmentation', engine='diffusion', backends=['sam2'],
        repository='facebook/sam2.1-hiera-base-plus', url='https://huggingface.co/facebook/sam2.1-hiera-base-plus',
        license='Apache-2.0', nonCommercial=False, gated=False, required=True,
        purpose='Object segmentation, the faster of the two installed variants.'),
    'sam2.1-hiera-large': dict(
        name='SAM 2.1 Hiera large', family='segmentation', engine='diffusion', backends=['sam2'],
        repository='facebook/sam2.1-hiera-large', url='https://huggingface.co/facebook/sam2.1-hiera-large',
        license='Apache-2.0', nonCommercial=False, gated=False, required=False,
        purpose='Object segmentation, the more accurate of the two installed variants.'),
    'depth-anything-v2-small': dict(
        name='Depth Anything V2 Small', family='depth', engine='diffusion', backends=['depthanything'],
        repository='depth-anything/Depth-Anything-V2-Small-hf',
        url='https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf',
        license='Apache-2.0', nonCommercial=False, gated=False, required=True,
        purpose='Relative depth used to place and weight the views.'),
    'perspective-fields-paramnet-360cities': dict(
        name='PerspectiveFields ParamNet 360cities', family='camera', engine='diffusion',
        backends=['perspectivefields'], repository='jinlinyi/PerspectiveFields',
        url='https://huggingface.co/spaces/jinlinyi/PerspectiveFields',
        license='Adobe Research License (non-commercial)', nonCommercial=True, gated=False, required=False,
        purpose='Estimates the camera of each photograph (roll, pitch, field of view).'),

    'hi3dgen-trellis-normal': dict(
        name='Hi3DGen normal-to-geometry model', family='reconstruction', engine='hi3dgen',
        backends=['hi3dgen'], repository='Stable-X/trellis-normal-v0-1',
        url='https://huggingface.co/Stable-X/trellis-normal-v0-1', license='MIT',
        nonCommercial=False, gated=False, required=True,
        purpose='TRELLIS v1 retrained on normal maps: a normal map to a mesh (256 grid).'),
    'yoso-normal-v1-8-1': dict(
        name='StableNormal YOSO normal estimator', family='normals', engine='hi3dgen',
        backends=['hi3dgen'], repository='Stable-X/yoso-normal-v1-8-1',
        url='https://huggingface.co/Stable-X/yoso-normal-v1-8-1', license='Apache-2.0',
        nonCommercial=False, gated=False, required=True,
        purpose='One picture to a sharp normal map, the first stage of Hi3DGen.'),
    'dinov2-vitl14-reg': dict(
        name='DINOv2 ViT-L/14 with registers', family='features', engine='hi3dgen',
        backends=['hi3dgen'], repository='facebookresearch/dinov2',
        url='https://github.com/facebookresearch/dinov2', license='Apache-2.0',
        nonCommercial=False, gated=False, required=True,
        purpose='Image features TRELLIS v1 is conditioned on, read through the pinned checkout.'),
    'wham': dict(
        name='WHAM checkpoints and the SMPL body model', family='motion', engine='wham',
        backends=['wham'], repository='yohanshin/WHAM',
        url='https://github.com/yohanshin/WHAM#installation',
        license='CC-BY-NC-4.0 (WHAM); the SMPL body model has its own licence, accepted in person',
        nonCommercial=True, gated=True, required=True,
        purpose='Video to 3D human motion. The checkpoints and SMPL_NEUTRAL.pkl are downloaded '
                'after accepting their terms on the official pages; they are not installed here.'),

    'wonder3d-v1.0': dict(
        name='Wonder3D v1.0', family='views', engine='legacy-cu121', backends=['wonder3d'],
        repository='flamehaze1115/wonder3d-v1.0', url='https://huggingface.co/flamehaze1115/wonder3d-v1.0',
        license='AGPL-3.0 (code); weights CC-BY-NC', nonCommercial=True, gated=False, required=False,
        purpose='Alternative multi-view generator with normal maps.'),
    'syncdreamer': dict(
        name='SyncDreamer', family='views', engine='legacy-cu121', backends=['syncdreamer'],
        repository='liuyuan-pal/SyncDreamer', url='https://github.com/liuyuan-pal/SyncDreamer',
        license='MIT (code); weights under the upstream research terms',
        nonCommercial=True, gated=False, required=False,
        purpose='Alternative multi-view generator producing a consistent 16-view ring.'),
}


def receipt_revision(folder):
    """Revision and per-file hashes recorded when the weights were installed."""
    revision, hashes = None, {}
    receipt = folder / 'cytools-receipt.json'
    if receipt.is_file():
        try:
            data = json.loads(receipt.read_text('utf-8'))
            revision = data.get('revision')
            hashes = {k: v for k, v in (data.get('files') or {}).items() if v}
        except ValueError:
            pass
    for item in folder.glob('*.installed.json'):
        try:
            data = json.loads(item.read_text('utf-8'))
        except (OSError, ValueError):
            continue
        revision = revision or data.get('revision') or revision_from_url(data.get('url') or '')
        name = item.name[: -len('.installed.json')]
        if data.get('actualSha256'):
            hashes[name] = data['actualSha256']
    if revision is None:
        revision = huggingface_revision(folder)
    return revision, hashes


def revision_from_url(url):
    """A Hugging Face resolve URL pins the revision it was downloaded from."""
    parts = url.split('/resolve/')
    if len(parts) != 2:
        return None
    candidate = parts[1].split('/')[0]
    if len(candidate) == 40 and all(c in '0123456789abcdef' for c in candidate):
        return candidate
    return None


def huggingface_revision(folder):
    """Commit recorded by huggingface_hub next to a downloaded snapshot.

    ``.cache/huggingface/download/<file>.metadata`` holds the commit on its first line.
    Only a single commit shared by every recorded file is trusted; a mixed snapshot
    returns nothing rather than a revision that would describe only part of it.
    """
    commits = set()
    for meta in folder.glob('.cache/huggingface/download/**/*.metadata'):
        try:
            first = meta.read_text('utf-8').splitlines()[0].strip()
        except (OSError, IndexError, ValueError):
            continue
        if len(first) == 40 and all(c in '0123456789abcdef' for c in first):
            commits.add(first)
    return commits.pop() if len(commits) == 1 else None


def scan(folder):
    files, total = [], 0
    for base, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
        for name in names:
            path = Path(base) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            files.append((str(path.relative_to(folder)).replace('\\', '/'), size))
            total += size
    files.sort()
    return files, total


def build():
    models = []
    present = {folder.name for folder in (MODELS.iterdir() if MODELS.is_dir() else [])
               if folder.is_dir()}
    # A model that is declared but absent is listed too, with installed=false: the interface
    # has to be able to show what is missing, its licence and where to accept it, instead of
    # staying silent until a job fails.
    for name in sorted(present | set(METADATA)):
        folder = MODELS / name
        meta = METADATA.get(folder.name)
        if meta is None:
            meta = dict(name=folder.name, family='unknown', engine='', backends=[], repository='', url='',
                        license='Unknown: this folder was not part of the migration table',
                        nonCommercial=False, gated=False, required=False, purpose='')
        files, total = scan(folder) if folder.is_dir() else ([], 0)
        revision, hashes = receipt_revision(folder) if folder.is_dir() else (None, {})
        biggest = sorted(files, key=lambda item: -item[1])[:12]
        models.append({
            'id': folder.name,
            'name': meta['name'],
            'family': meta['family'],
            'engine': meta['engine'],
            'backends': meta['backends'],
            'directory': f'data/models/{folder.name}',
            'installed': bool(files),
            'sizeBytes': total,
            'fileCount': len(files),
            'revision': revision,
            'revisionKnown': revision is not None,
            'source': {'repository': meta['repository'], 'url': meta['url'], 'gated': meta['gated']},
            'license': meta['license'],
            'nonCommercial': meta['nonCommercial'],
            'required': meta['required'],
            'purpose': meta['purpose'],
            'verify': [{'path': path, 'sizeBytes': size, 'sha256': hashes.get(path)} for path, size in biggest],
        })
    catalogue = {
        'schemaVersion': 1,
        'note': 'Generated by app/scripts/build_catalog.py from the weights present in data/models. '
                'Sizes and file lists are measured; revisions come from the installation receipts of the '
                'absorbed Tools and are null when no receipt recorded one.',
        'totalBytes': sum(item['sizeBytes'] for item in models),
        'models': models,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return catalogue


if __name__ == '__main__':
    result = build()
    print(f'{len(result["models"])} models, {result["totalBytes"] / 1024 ** 3:.1f} GiB -> {OUT}')
    unknown = [m['id'] for m in result['models'] if m['family'] == 'unknown']
    missing = [m['id'] for m in result['models'] if not m['revisionKnown']]
    if unknown:
        print('Not described in METADATA:', ', '.join(unknown))
    print('Revision unknown:', ', '.join(missing) if missing else 'none')
