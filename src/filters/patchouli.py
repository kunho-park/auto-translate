"""
Patchouli 책 모드용 번역 필터

Patchouli 책의 페이지들에서 번역 대상 텍스트를 추출합니다.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from ..parsers.base import BaseParser
from .base import BaseFilter, TranslationEntry

logger = logging.getLogger(__name__)


class PatchouliFilter(BaseFilter):
    """Patchouli 책 파일을 위한 필터"""

    name = "patchouli"

    # Patchouli 관련 파일들
    path_patterns = [
        r".*/patchouli_books/.*\.json$",
    ]

    # 번역 대상 키들 (old 로더 참고)
    key_whitelist = {
        "pages",
        "text",
        "title",
        "subtitle",
        "description",
        "name",
        "landing_text",
    }

    def get_priority(self) -> int:
        """Patchouli는 특화 필터이므로 높은 우선순위"""
        return 9

    def should_translate_key(self, key: str) -> bool:
        """키가 번역 대상인지 확인"""
        key_parts = key.split(".")
        last_key = key_parts[-1].replace("[", "").replace("]", "").split("[")[0]
        return last_key in self.key_whitelist

    def can_handle_file(self, file_path: str) -> bool:
        """Patchouli 경로의 JSON 파일인지 확인"""
        return super().can_handle_file(file_path)

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """Patchouli 파일에서 번역 대상 추출"""
        try:
            # JSON 파서 사용
            parser_class = BaseParser.get_parser_by_extension(".json")
            if not parser_class:
                logger.warning(f"JSON 파서를 찾을 수 없음: {file_path}")
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            entries = []

            # pages 배열 특별 처리 (old 로더 방식)
            if "pages" in data and isinstance(data["pages"], list):
                for i, page in enumerate(data["pages"]):
                    if isinstance(page, dict):
                        for key, value in page.items():
                            if (
                                key in self.key_whitelist
                                and isinstance(value, str)
                                and value.strip()
                            ):
                                entry = TranslationEntry(
                                    key=f"pages[{i}].{key}",
                                    original_text=value,
                                    file_path=file_path,
                                    file_type=self.name,
                                    context={
                                        "file_type": "patchouli",
                                        "category": "page",
                                        "page_index": i,
                                        "key": key,
                                    },
                                    priority=self._get_key_priority(key),
                                )
                                entries.append(entry)

            # 일반 필드들도 처리
            self._extract_from_dict(data, entries, file_path, "")

            logger.debug(
                f"Patchouli 파일에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"Patchouli 파일 처리 실패 ({file_path}): {e}")
            return []

    def _extract_from_dict(
        self,
        data: Dict[str, Any],
        entries: List[TranslationEntry],
        file_path: str,
        key_prefix: str = "",
    ):
        """딕셔너리에서 재귀적으로 번역 대상 추출 (pages 제외)"""
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            # pages는 이미 위에서 특별 처리했으므로 제외
            if key == "pages":
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
                            "file_type": "patchouli",
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
                                "file_type": "patchouli",
                                "category": "list_item",
                                "key_path": full_key,
                                "list_index": i,
                            },
                        )
                        entries.append(entry)

    def _get_key_priority(self, key: str) -> int:
        """키에 따른 우선순위 설정"""
        if key in ["title", "name"]:
            return 10  # 제목은 높은 우선순위
        elif key in ["text", "description"]:
            return 8  # 내용은 높은 우선순위
        elif key == "subtitle":
            return 6  # 부제목은 중간 우선순위
        else:
            return 3  # 기타는 낮은 우선순위


class PatchouliCategoryFilter(PatchouliFilter):
    """Patchouli 카테고리 전용 필터"""

    name = "patchouli_category"

    path_patterns = [
        r".*/patchouli_books/.*/categories/.*\.json$",
    ]

    def get_priority(self) -> int:
        """카테고리는 더 높은 우선순위"""
        return 11


class PatchouliEntryFilter(PatchouliFilter):
    """Patchouli 엔트리 전용 필터"""

    name = "patchouli_entry"

    path_patterns = [
        r".*/patchouli_books/.*/entries/.*\.json$",
    ]

    def get_priority(self) -> int:
        """엔트리는 높은 우선순위"""
        return 10


class PatchouliBookFilter(PatchouliFilter):
    """Patchouli 책 설정 파일 전용 필터"""

    name = "patchouli_book"

    path_patterns = [
        r".*/patchouli_books/.*/book\.json$",
        r".*/patchouli_books/book\.json$",
    ]

    def get_priority(self) -> int:
        """책 설정은 가장 높은 우선순위"""
        return 12

    def _extract_entries_from_dict(
        self, data: dict, file_path: str, key_path: str = ""
    ) -> List[TranslationEntry]:
        """딕셔너리에서 번역 가능한 항목들을 추출합니다."""
        entries = []

        # 책 설정에서 번역 가능한 키들
        translatable_keys = [
            "pages",
            "text",
            "title",
            "subtitle",
            "description",
            "name",
            "landing_text",
        ]

        for key, value in data.items():
            if key in translatable_keys and isinstance(value, str) and value.strip():
                full_key = f"{key_path}.{key}" if key_path else key
                entry = TranslationEntry(
                    key=full_key,
                    original_text=value,
                    file_path=file_path,
                    file_type=self.name,
                    context={
                        "file_type": "patchouli_book",
                        "category": "book_config",
                        "key_path": full_key,
                    },
                    priority=self._get_key_priority(key),
                )
                entries.append(entry)

        return entries

    def _get_key_priority(self, key: str) -> int:
        """키에 따른 우선순위 설정"""
        if key == "name":
            return 10  # 책 이름은 높은 우선순위
        elif key == "landing_text":
            return 8  # 소개 텍스트는 높은 우선순위
        else:
            return 3  # 기타는 낮은 우선순위
