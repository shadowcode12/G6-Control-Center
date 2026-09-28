from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyboardResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class KeyboardController:
    """
    Placeholder for the native EC keyboard backend.

    gigactl is intentionally not used anymore. RGB EC writes will be enabled
    in a later hardware-validated step after the read-only EC path is stable.
    """

    available = False
    reason = (
        "Native RGB EC backend is not enabled yet. "
        "gigactl has been removed from the hardware control path."
    )

    def _unsupported(self) -> KeyboardResult:
        return KeyboardResult(False, stderr=self.reason, returncode=95)

    def keyboard_status(self) -> KeyboardResult:
        return self._unsupported()

    def keyboard_color(self, color: str) -> KeyboardResult:
        return self._unsupported()

    def keyboard_brightness(self, percent: int) -> KeyboardResult:
        return self._unsupported()

    def keyboard_on(self) -> KeyboardResult:
        return self._unsupported()

    def keyboard_off(self) -> KeyboardResult:
        return self._unsupported()
