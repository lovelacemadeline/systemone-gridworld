"""Run provenance (stories 4.1, 4.2): power state of the machine a run was measured on.

Decisions/s on a laptop depends on power: macOS low power mode and battery
versus AC both change it, so every report carries them. Off macOS (or if
``pmset`` fails) the fields are ``None``.
"""

from __future__ import annotations

import subprocess

__all__ = ["power_state"]


def _pmset(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["pmset", *args], capture_output=True, text=True, check=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return out


def power_state() -> dict[str, str | bool | None]:
    """``{"low_power_mode": bool | None, "power_source": str | None}`` from ``pmset``."""
    low = None
    general = _pmset("-g")
    if general:
        for line in general.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "lowpowermode":
                low = parts[1] == "1"
    source = None
    batt = _pmset("-g", "batt")
    if batt:
        first = batt.splitlines()[0] if batt.splitlines() else ""
        if "'" in first:
            source = first.split("'")[1]
    return {"low_power_mode": low, "power_source": source}
