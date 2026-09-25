"""Deterministic proxy-mesh construction engine (NumPy / OpenCV / SciPy only).

Object frame used everywhere: +X front, +Y up, +Z right (right-handed).
Azimuth 0 looks at the front, +90 at the right side; elevation is positive above.
No AI model is imported here: models only supply masks, depth and camera cues.
"""
ENGINE_VERSION = '0.1.0'
