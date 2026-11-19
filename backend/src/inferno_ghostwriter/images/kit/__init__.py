"""The character kit: our own cast (ghost, dog, cat, person, robot), drawn by code from named parts.

Claude picks who is in a scene, their expression, pose, accessory and prop; the kit draws them, so characters are
whole, on-model and appealing every time. See ``docs/image-kit.md``.
"""

from inferno_ghostwriter.images.kit.face import EXPRESSION_HINTS, EXPRESSIONS
from inferno_ghostwriter.images.kit.rig import ACCESSORIES, KINDS, POSES, PROPS, Character, Drawn, draw, menu
from inferno_ghostwriter.images.kit.style import STYLES, KitStyle, kit_style

__all__ = [
    "ACCESSORIES",
    "EXPRESSIONS",
    "EXPRESSION_HINTS",
    "KINDS",
    "POSES",
    "PROPS",
    "STYLES",
    "Character",
    "Drawn",
    "KitStyle",
    "draw",
    "kit_style",
    "menu",
]
