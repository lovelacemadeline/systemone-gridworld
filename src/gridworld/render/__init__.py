"""Renderers: pure functions of an :class:`~gridworld.sim.Observation` (ADR-0001)."""

from .text import to_text

__all__ = ["to_image", "to_png", "to_text"]


def __getattr__(name: str):
    # Pillow is the optional `image` extra; import it only when asked for.
    if name in ("to_image", "to_png"):
        from . import image

        return getattr(image, name)
    raise AttributeError(name)
