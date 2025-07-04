"""
PuffishSkills 모드용 번역 필터

PuffishSkills의 카테고리와 스킬들에서 번역 대상 텍스트를 추출합니다.
"""

import logging
from pathlib import Path
from typing import Any, List

from ..parsers.base import BaseParser
from .base import BaseFilter, TranslationEntry

logger = logging.getLogger(__name__)


class PuffishSkillsFilter(BaseFilter):
    """PuffishSkills 파일을 위한 필터"""

    name = "puffish_skills"

    # PuffishSkills 관련 파일들
    path_patterns = [
        r".*/puffish_skills/categories/.*\.json$",
    ]

    # 번역 대상 키들 (old 로더 참고)
    key_whitelist = {"pages", "text", "title", "subtitle", "description"}

    # 처리할 파일들 (old 로더 참고)
    file_whitelist = {"definitions.json", "category.json"}

    def get_priority(self) -> int:
        """PuffishSkills는 특화 필터이므로 높은 우선순위"""
        return 9

    def should_translate_key(self, key: str) -> bool:
        """키가 번역 대상인지 확인"""
        key_parts = key.split(".")
        last_key = key_parts[-1].replace("[", "").replace("]", "").split("[")[0]
        return last_key in self.key_whitelist

    def can_handle_file(self, file_path: str) -> bool:
        """PuffishSkills 경로의 특정 JSON 파일인지 확인"""
        if not super().can_handle_file(file_path):
            return False

        # 특정 파일명만 처리 (old 로더 방식)
        file_name = Path(file_path).name
        return file_name in self.file_whitelist

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """PuffishSkills 파일에서 번역 대상 추출"""
        try:
            # JSON 파서 사용
            parser_class = BaseParser.get_parser_by_extension(".json")
            if not parser_class:
                logger.warning(f"JSON 파서를 찾을 수 없음: {file_path}")
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            entries = []

            # 재귀적으로 모든 키-값 쌍 검사 (old 로더 방식)
            self._extract_recursive(data, entries, file_path, "")

            logger.debug(
                f"PuffishSkills 파일에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"PuffishSkills 파일 처리 실패 ({file_path}): {e}")
            return []

    def _extract_recursive(
        self,
        data: Any,
        entries: List[TranslationEntry],
        file_path: str,
        key_prefix: str = "",
    ):
        """재귀적으로 번역 대상 추출 (old 로더 방식과 동일)"""

        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{key_prefix}.{key}" if key_prefix else key

                # 중첩된 값을 재귀적으로 처리
                self._extract_recursive(value, entries, file_path, full_key)

        elif isinstance(data, str) and self.should_translate_key(key_prefix):
            # 키가 화이트리스트에 있는 문자열 값인 경우
            if data.strip():
                entry = TranslationEntry(
                    key=key_prefix,
                    original_text=data,
                    file_path=file_path,
                    file_type=self.name,
                    context={
                        "file_type": "puffish_skills",
                        "category": self._get_category_from_path(file_path),
                        "key_path": key_prefix,
                        "file_name": Path(file_path).name,
                    },
                    priority=self._get_key_priority(key_prefix.split(".")[-1]),
                )
                entries.append(entry)

        elif isinstance(data, list):
            # 리스트인 경우 각 항목 처리
            for i, item in enumerate(data):
                list_key = f"{key_prefix}[{i}]"
                self._extract_recursive(item, entries, file_path, list_key)

    def _get_category_from_path(self, file_path: str) -> str:
        """파일 경로에서 카테고리 추출"""
        path_lower = file_path.lower().replace("\\", "/")

        if "/categories/" in path_lower:
            return "category"
        elif "/skills/" in path_lower:
            return "skill"
        else:
            return "unknown"

    def _get_key_priority(self, key: str) -> int:
        """키에 따른 우선순위 설정"""
        if key in ["name", "title"]:
            return 10  # 이름/제목은 높은 우선순위
        elif key in ["description", "text"]:
            return 8  # 설명은 높은 우선순위
        elif key == "subtitle":
            return 6  # 부제목은 중간 우선순위
        else:
            return 3  # 기타는 낮은 우선순위


class PuffishSkillsCategoryFilter(PuffishSkillsFilter):
    """PuffishSkills 카테고리 전용 필터"""

    name = "puffish_skills_category"

    path_patterns = [
        r".*/puffish_skills/categories/.*category\.json$",
    ]

    file_whitelist = {"category.json"}

    def get_priority(self) -> int:
        """카테고리는 더 높은 우선순위"""
        return 11


class PuffishSkillsDefinitionsFilter(PuffishSkillsFilter):
    """PuffishSkills 정의 전용 필터"""

    name = "puffish_skills_definitions"

    path_patterns = [
        r".*/puffish_skills/categories/.*definitions\.json$",
    ]

    file_whitelist = {"definitions.json"}

    def get_priority(self) -> int:
        """정의는 높은 우선순위"""
        return 10
