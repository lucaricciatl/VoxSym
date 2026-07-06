"""Browser-side GUI protocol helper.

This module previously contained a Viser-native ``VoxSymGUI``.  The
renderer is now browser-based, so the Python-side GUI is intentionally a
no-op protocol emitter.  It can still be imported and passed around for
backwards compatibility, but all controls live in the browser-side npm
application under ``voxsym/web/frontend/``."""


class VoxSymGUI:
    """No-op GUI placeholder.

    Parameters
    ----------
    voxsym : VoxSym
        Simulation instance controls are applied to.
    server : WebGLServer or None
        Ignored; retained for compatibility.
    """

    def __init__(self, voxsym, server=None):
        self.voxsym = voxsym
        self.server = server
        self._opacity_value = 1.0

    def sync(self):
        """No-op: browser GUI state is sent directly over WebSocket."""
        pass

    @property
    def opacity(self) -> float:
        """Current global opacity value (0–1)."""
        return self._opacity_value

    def set_opacity(self, value: float):
        """Programmatically set the stored opacity."""
        self._opacity_value = float(value)
        # Do NOT call self.voxsym.opacity here; that would recurse into
        # this method.  The WebGL backend opacity is applied separately.
