from __future__ import annotations

import abc
from pathlib import Path
from typing import Mapping, Type, Union


class BaseParser(abc.ABC):
    """원본 문자열의 매핑을 반환하는 추상 파일 파서입니다.

    파서는 *path*를 읽고 ``{key: value}`` 매핑을 반환합니다.
    여기서 *key*는 일반적으로 원본 문자열을 식별하고(예: 번역 키 또는 줄 번호),
    *value*는 번역할 텍스트입니다.
    """

    #: 지원되는 파일 이름 접미사 목록 (점 포함)
    file_extensions: tuple[str, ...] = ()

    def __init__(self, path: Path, original_path: Path = None):
        self.path = path
        self.original_path = original_path

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    @abc.abstractmethod
    async def parse(self) -> Mapping[str, str]:
        """*path*에서 추출한 문자열 매핑을 반환합니다."""

    @abc.abstractmethod
    async def dump(self, data: Mapping[str, str]) -> None:
        """*data*를 원래 구조를 유지하며 파일에 다시 씁니다."""

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------
    def _check_extension(self) -> None:
        if self.file_extensions and self.path.suffix not in self.file_extensions:
            raise ValueError(
                f"지원하지 않는 파일 형식 {self.path} for {self.__class__.__name__}"
            )

    # ------------------------------------------------------------------
    # 파서 팩토리 메서드
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
        elif extension == ".nbt":
            from .nbt import NBTParser

            return NBTParser
        else:
            return None

    @staticmethod
    def get_supported_extensions() -> list[str]:
        """
        지원하는 파일 확장자 목록을 반환합니다.

        Returns:
            List[str]: 지원하는 파일 확장자 목록
        """
        return [".json", ".lang", ".txt", ".snbt", ".xml", ".js", ".ts", ".nbt"]
