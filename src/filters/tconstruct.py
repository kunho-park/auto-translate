"""
Tinkers' Construct 모드용 번역 필터

TConstruct의 책 페이지들에서 번역 대상 텍스트를 추출합니다.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from ..parsers.base import BaseParser
from .base import BaseFilter, TranslationEntry

logger = logging.getLogger(__name__)


class TConstructFilter(BaseFilter):
    """TConstruct 책 파일을 위한 필터"""

    name = "tconstruct"

    # TConstruct 관련 파일들
    path_patterns = [
        r".*/tconstruct/book/.*\.json$",
    ]

    # 번역 대상 키들 (old 로더 참고)
    key_whitelist = {"text", "title"}

    def get_priority(self) -> int:
        """TConstruct는 특화 필터이므로 높은 우선순위"""
        return 9

    def should_translate_key(self, key: str) -> bool:
        """키가 번역 대상인지 확인"""
        key_parts = key.split(".")
        last_key = key_parts[-1].replace("[", "").replace("]", "").split("[")[0]
        return last_key in self.key_whitelist

    def can_handle_file(self, file_path: str) -> bool:
        """TConstruct 경로의 JSON 파일인지 확인"""
        return super().can_handle_file(file_path)

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """TConstruct 파일에서 번역 대상 추출"""
        try:
            # JSON 파서 사용
            parser_class = BaseParser.get_parser_by_extension(".json")
            if not parser_class:
                logger.warning(f"JSON 파서를 찾을 수 없음: {file_path}")
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            entries = []

            # text 배열 특별 처리 (old 로더 방식)
            if "text" in data and isinstance(data["text"], list):
                for i, text_item in enumerate(data["text"]):
                    if isinstance(text_item, dict):
                        for key, value in text_item.items():
                            if (
                                key in self.key_whitelist
                                and isinstance(value, str)
                                and value.strip()
                            ):
                                entry = TranslationEntry(
                                    key=f"text[{i}].{key}",
                                    original_text=value,
                                    file_path=file_path,
                                    file_type=self.name,
                                    context={
                                        "file_type": "tconstruct",
                                        "category": "book_text",
                                        "text_index": i,
                                        "key": key,
                                    },
                                    priority=self._get_key_priority(key),
                                )
                                entries.append(entry)

            # 일반 필드들도 처리
            self._extract_from_dict(data, entries, file_path, "")

            logger.debug(
                f"TConstruct 파일에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"TConstruct 파일 처리 실패 ({file_path}): {e}")
            return []

    def _extract_from_dict(
        self,
        data: Dict[str, Any],
        entries: List[TranslationEntry],
        file_path: str,
        key_prefix: str = "",
    ):
        """딕셔너리에서 재귀적으로 번역 대상 추출 (text 배열 제외)"""
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            # text 배열은 이미 위에서 특별 처리했으므로 제외
            if key == "text" and isinstance(value, list):
                continue

            full_key = f"{key_prefix}.{key}" if key_prefix else key

            if isinstance(value, str):
                # 문자열 값이고 번역 대상 키인 경우
                if self.should_translate_key(full_key) and value.strip():
                    entry = TranslationEntry(
                        key=full_key,
                        original_text=value,
                        file_path=file_path,
                        file_type=self.name,
                        context={
                            "file_type": "tconstruct",
                            "category": "general",
                            "key_path": full_key,
                        },
                        priority=self._get_key_priority(key),
                    )
                    entries.append(entry)

            elif isinstance(value, dict):
                # 중첩된 딕셔너리인 경우 재귀 처리
                self._extract_from_dict(value, entries, file_path, full_key)

            elif isinstance(value, list):
                # 리스트인 경우 각 항목 처리
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._extract_from_dict(
                            item, entries, file_path, f"{full_key}[{i}]"
                        )
                    elif isinstance(item, str) and self.should_translate_key(full_key):
                        entry = TranslationEntry(
                            key=f"{full_key}[{i}]",
                            original_text=item,
                            file_path=file_path,
                            file_type=self.name,
                            context={
                                "file_type": "tconstruct",
                                "category": "list_item",
                                "key_path": full_key,
                                "list_index": i,
                            },
                        )
                        entries.append(entry)

    def _get_key_priority(self, key: str) -> int:
        """키에 따른 우선순위 설정"""
        if key == "title":
            return 10  # 제목은 높은 우선순위
        elif key == "text":
            return 8  # 텍스트는 높은 우선순위
        else:
            return 3  # 기타는 낮은 우선순위
