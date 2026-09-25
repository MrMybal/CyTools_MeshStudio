"""Limits and derivation constants of the PBR bake, from CyTools_Trellis2Texture.

These values are part of the contract: changing one changes every baked map, so they are
kept here verbatim and reported by ``diagnose`` and in every bake report.
"""
import os
from pathlib import Path

WORKERS = Path(__file__).resolve().parent
APP = WORKERS.parent
ROOT = APP.parent
DATA = ROOT / 'data'

MESH_SUFFIXES = ('.glb', '.gltf', '.obj', '.ply', '.stl', '.off')
MAX_MESH_BYTES = 512 * 1024 ** 2
MAX_FACES = 2_000_000
# xatlas is native code that can abort on some inputs, so it runs in its own short-lived process.
UNWRAP_TIMEOUT_SECONDS = 900

# Documented, reproducible derivation constants. Changing them changes every output.
DETAIL_GAIN = 0.40
LUMINANCE_GAIN = 0.20
DETAIL_SCALE = 0.15
DETAIL_RADIUS = 2
CAVITY_GAIN = 0.60
METAL_SATURATION_HIGH = 0.30
METAL_SATURATION_LOW = 0.08
METAL_LUMINANCE_LOW = 0.40
METAL_LUMINANCE_HIGH = 0.70

ROUGHNESS_FORMULA = ('roughness = clip(roughness_value + 0.40*detail + 0.20*(0.5 - luminance), 0, 1) '
                     'with detail = clip(stddev(luminance, 5x5 texels)/0.15, 0, 1)')
METALLIC_FORMULA = ('metallic = clip(max(metallic_value, smoothstep(0.30->0.08, saturation) '
                    '* smoothstep(0.40->0.70, luminance)), 0, 1)')
CAVITY_FORMULA = ('base_color *= 1 + cavity_delight * 0.60 * clip(cavity, 0, 1) with cavity = mean over the '
                  '1-ring of dot(vertex_normal, normalized edge direction)')


def mesh_root():
    return Path(os.environ.get('MESHSTUDIO_INPUTS', str(DATA / 'inputs'))).resolve()
