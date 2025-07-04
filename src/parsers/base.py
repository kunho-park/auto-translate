from __future__ import annotations

import abc
from pathlib import Path
from typing import Mapping, Type, Union


class BaseParser(abc.ABC):
    """Abstract file parser returning mapping of original strings.

    A parser reads *path* and returns a mapping ``{key: value}`` where *key*
    typically identifies the original string (e.g. translation key or line
    number) and *value* is the text to be translated.
    """

    #: list of supported filename suffixes (including dot)
    file_extensions: tuple[str, ...] = ()

    def __init__(self, path: Path):
        self.path = path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @abc.abstractmethod
    async def parse(self) -> Mapping[str, str]:
        """Return mapping of strings extracted from *path*."""

    @abc.abstractmethod
    async def dump(self, data: Mapping[str, str]) -> None:
        """Write *data* back to file, preserving original structure."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_extension(self) -> None:
        if self.file_extensions and self.path.suffix not in self.file_extensions:
            raise ValueError(
                f"Unsupported file type {self.path} for {self.__class__.__name__}"
            )

    # ------------------------------------------------------------------
    # Parser Factory Methods
    # ------------------------------------------------------------------
    @staticmethod
    def get_parser_by_extension(extension: str) -> Union[Type["BaseParser"], None]:
        """
        파일 확장자에 따라 적절한 파서를 반환합니다.

        Args:
            extension (str): 파일 확장자 (.json, .lang, .txt, .snbt, .xml 등)

        Returns:
            BaseParser: 해당 확장자에 맞는 파서 클래스
        """
        extension = extension.lower()

        # 동적으로 임포트하여 순환 참조 해결
        if extension == ".json":
            from .json import JSONParser
            return JSONParser
        elif extension == ".lang":
            from .lang import LangParser
            return LangParser
        elif extension == ".txt":
            from .txt import TextParser
            return TextParser
        elif extension == ".snbt":
            from .snbt import SNBTParser
            return SNBTParser
        elif extension == ".xml":
            from .xml import XMLParser
            return XMLParser
        elif extension in (".js", ".ts"):
            from .js import JSParser
            return JSParser
        else:
            return None

    @staticmethod
    def get_supported_extensions() -> list[str]:
        """
        지원하는 파일 확장자 목록을 반환합니다.

        Returns:
            List[str]: 지원하는 파일 확장자 목록
        """
        return [".json", ".lang", ".txt", ".snbt", ".xml", ".js", ".ts"]
