from __future__ import annotations

import os
from pathlib import Path


EC_SYS_IO = Path("/sys/kernel/debug/ec/ec0/io")


class EmbeddedControllerError(RuntimeError):
    """Raised when the Linux EC interface cannot be read."""


class EmbeddedController:
    """
    Read-only Linux Embedded Controller access.

    This backend intentionally starts with EC reads only. It uses the kernel's
    ec_sys interface instead of a third-party control utility. Keeping the
    first native backend read-only lets us validate the model-specific register
    map before enabling any EC writes.
    """

    def __init__(self, path: str | os.PathLike[str] = EC_SYS_IO) -> None:
        self.path = Path(path)

    @property
    def available(self) -> bool:
        return self.path.exists() and self.path.is_file()

    def read_u8(self, offset: int) -> int:
        if not self.available:
            raise EmbeddedControllerError(
                "Linux EC interface is unavailable. "
                f"Expected {self.path}."
            )

        if not 0 <= offset <= 0xFF:
            raise ValueError("EC offset must be between 0x00 and 0xFF.")

        try:
            with self.path.open("rb", buffering=0) as handle:
                handle.seek(offset)
                value = handle.read(1)
        except OSError as exc:
            raise EmbeddedControllerError(
                f"Unable to read EC offset 0x{offset:02X}: {exc}"
            ) from exc

        if len(value) != 1:
            raise EmbeddedControllerError(
                f"Short EC read at offset 0x{offset:02X}."
            )

        return value[0]

    def read_u16_be(self, high_offset: int, low_offset: int) -> int:
        high = self.read_u8(high_offset)
        low = self.read_u8(low_offset)
        return (high << 8) | low
