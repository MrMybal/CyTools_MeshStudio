"""Interchangeable multi-view generation backends.

A backend is a module exposing ``DESCRIPTOR`` and a ``Backend`` class implementing
:class:`viewengine.backends.base.MultiViewBackend`. ``load`` returns an instance only for
backends that are implemented and whose components are installed; anything else raises
so the caller can report the real reason instead of silently substituting another engine.
"""
from . import base

MODULES = {
    'zero123plus': 'viewengine.backends.zero123plus',
    'mirror': 'viewengine.backends.mirror',
}


def descriptor(backend_id):
    import importlib
    if backend_id not in MODULES:
        return {'id': backend_id, 'implemented': False,
                'reason': 'No adapter is implemented for this backend in this version.'}
    return importlib.import_module(MODULES[backend_id]).DESCRIPTOR


def load(backend_id, **options):
    import importlib
    if backend_id not in MODULES:
        raise base.BackendUnavailable(
            'MissingBackend',
            'No adapter is implemented for backend "%s" in this version. '
            'See app/Docs/CapabilityCoverage.md for the backends that are.' % backend_id)
    return importlib.import_module(MODULES[backend_id]).Backend(**options)
