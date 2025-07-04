from __future__ import annotations

"""Parsers extract meaningful key-value pairs from Minecraft resource files.

Each parser should inherit from :class:`~auto_translate.parsers.base.BaseParser` and
implement its asynchronous :py:meth:`parse` method.
"""

from .base import BaseParser
from .js import JSParser
from .json import JSONParser
from .lang import LangParser
from .snbt import SNBTParser
from .txt import TextParser
from .xml import XMLParser

__all__ = [
    "BaseParser",
    "JSONParser",
    "LangParser",
    "SNBTParser",
    "TextParser",
    "JSParser",
    "XMLParser",
]
