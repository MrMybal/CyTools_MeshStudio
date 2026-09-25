"""Mirror backend: a horizontal flip of an existing view, not an AI generation.

For an object with strong bilateral symmetry the view at ``-azimuth`` is the mirror of
the view at ``+azimuth``. This costs milliseconds and no model, but it is only valid
under that assumption, so the produced views are always labelled ``method='mirror'``
and carry the measured symmetry score that justified them.
"""
import numpy as np

from .. import pose
from . import base

DESCRIPTOR = {
    'id': 'mirror',
    'name': 'Mirrored existing view (geometric, no model)',
    'implemented': True,
    'source': '',
    'weights': '',
    'codeLicense': 'Part of this Tool',
    'weightsLicense': 'No weights',
}
#: Below this silhouette symmetry score a mirrored view is refused unless forced.
SYMMETRY_THRESHOLD = 0.82


class Backend(base.MultiViewBackend):
    id = 'mirror'
    offsets = ()
    elevation_absolute = False
    fov = None
    resolution = 0
    parameters = ('symmetry', 'symmetry_threshold')
    supports_normals = False
    supports_multi_reference = False

    def __init__(self, **options):
        self.threshold = float(options.get('symmetry_threshold', SYMMETRY_THRESHOLD))

    def model_version(self):
        return 'geometric-mirror-1'

    @staticmethod
    def symmetry(mask):
        return pose.symmetry_score(mask)[0]

    def mirror(self, rgb, mask, *, symmetry_mode='auto', threshold=None):
        """Flip one view horizontally; returns the arrays and the evidence used."""
        threshold = self.threshold if threshold is None else float(threshold)
        score = self.symmetry(mask)
        if symmetry_mode == 'off':
            raise base.BackendUnavailable('SymmetryDisabled',
                                          'Mirroring was requested with symmetry set to off.')
        if symmetry_mode == 'auto' and score < threshold:
            raise base.BackendUnavailable(
                'WeakSymmetry',
                'The silhouette symmetry score is %.3f, below the %.2f threshold, so a '
                'mirrored view would not be a faithful opposite view. Use symmetry=force to '
                'produce it anyway, or generate the view with a model backend.' % (score, threshold))
        return {'rgb': np.ascontiguousarray(rgb[:, ::-1]),
                'mask': np.ascontiguousarray(mask[:, ::-1]),
                'symmetry': round(float(score), 4), 'threshold': threshold,
                'forced': symmetry_mode == 'force' and score < threshold}

    def generate(self, condition, parameters, *, progress=None, cancel=None):
        raise base.BackendUnavailable(
            'UnsupportedOperation',
            'The mirror backend produces one opposite view at a time; use the mirror_view '
            'operation or select it for a target whose opposite view already exists.')
