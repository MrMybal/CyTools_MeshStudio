"""Contract every generation backend implements."""


class BackendUnavailable(Exception):
    """Raised with a CyTools error code when a backend cannot run."""

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class MultiViewBackend:
    """One interchangeable multi-view generator.

    ``sample`` returns the poses the engine can reach from a single reference view,
    expressed as ``(relative_azimuth, absolute_elevation)`` pairs in degrees, or
    ``(relative_azimuth, relative_elevation)`` when ``elevation_absolute`` is False.
    ``generate`` renders that complete set in one pass; individual arbitrary poses are
    not requested from an engine that cannot produce them.
    """

    id = ''
    #: (relative azimuth, elevation) offsets the engine produces, in degrees.
    offsets = ()
    #: True when ``offsets`` carry absolute elevations rather than relative ones.
    elevation_absolute = True
    #: Field of view of the generated views in degrees, or None when unspecified.
    fov = None
    #: Native pixel size of one generated view.
    resolution = 0
    #: Parameters the engine actually honours; anything else is refused upstream.
    parameters = ()
    #: True when the engine also produces view-space normal maps.
    supports_normals = False
    #: True when more than one real view conditions the generation.
    supports_multi_reference = False

    def describe(self):
        return {'id': self.id, 'offsets': [list(x) for x in self.offsets],
                'elevationAbsolute': self.elevation_absolute, 'fov': self.fov,
                'resolution': self.resolution, 'parameters': list(self.parameters),
                'supportsNormals': self.supports_normals,
                'supportsMultiReference': self.supports_multi_reference,
                'modelVersion': self.model_version()}

    def model_version(self):
        return ''

    def generate(self, condition, parameters, *, progress=None, cancel=None):
        raise NotImplementedError

    def release(self):
        pass
