"""
Paxi 데이터팩/리소스팩용 번역 필터

Paxi를 통해 추가된 데이터팩과 리소스팩에서 번역 대상 텍스트를 추출합니다.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from ..parsers.base import BaseParser
from .base import BaseFilter, TranslationEntry

logger = logging.getLogger(__name__)


class PaxiFilter(BaseFilter):
    """Paxi 데이터팩/리소스팩 파일을 위한 필터"""

    name = "paxi"

    # Paxi 관련 파일들
    path_patterns = [
        r".*/paxi/datapacks/.*\.zip_extracted/.*\.json$",
        r".*/paxi/resourcepacks/.*\.zip_extracted/.*\.json$",
    ]

    # 번역 대상 키들 (old 로더 참고)
    key_whitelist = {"text", "title", "subtitle", "description"}

    def get_priority(self) -> int:
        """Paxi는 특화 필터이므로 높은 우선순위"""
        return 8

    def should_translate_key(self, key: str) -> bool:
        """키가 번역 대상인지 확인"""
        key_parts = key.split(".")
        last_key = key_parts[-1].replace("[", "").replace("]", "").split("[")[0]
        return last_key in self.key_whitelist

    def can_handle_file(self, file_path: str) -> bool:
        """Paxi 경로의 압축 해제된 JSON 파일인지 확인"""
        if not super().can_handle_file(file_path):
            return False

        # .zip_extracted 폴더 내의 파일만 처리
        return ".zip_extracted" in file_path

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """Paxi 파일에서 번역 대상 추출"""
        try:
            # JSON 파서 사용
            parser_class = BaseParser.get_parser_by_extension(".json")
            if not parser_class:
                logger.warning(f"JSON 파서를 찾을 수 없음: {file_path}")
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            entries = []

            # 재귀적으로 모든 키-값 쌍 검사
            self._extract_from_dict(data, entries, file_path, "")

            logger.debug(
                f"Paxi 파일에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"Paxi 파일 처리 실패 ({file_path}): {e}")
            return []

    def _extract_from_dict(
        self,
        data: Dict[str, Any],
        entries: List[TranslationEntry],
        file_path: str,
        key_prefix: str = "",
    ):
        """딕셔너리에서 재귀적으로 번역 대상 추출"""
        if not isinstance(data, dict):
            return

        for key, value in data.items():
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
                            "file_type": "paxi",
                            "category": self._get_category_from_path(file_path),
                            "key_path": full_key,
                            "pack_type": self._get_pack_type_from_path(file_path),
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
                                "file_type": "paxi",
                                "category": self._get_category_from_path(file_path),
                                "key_path": full_key,
                                "list_index": i,
                                "pack_type": self._get_pack_type_from_path(file_path),
                            },
                        )
                        entries.append(entry)

    def _get_category_from_path(self, file_path: str) -> str:
        """파일 경로에서 카테고리 추출"""
        path_lower = file_path.lower().replace("\\", "/")

        if "/lang/" in path_lower:
            return "lang"
        elif "/recipes/" in path_lower:
            return "recipe"
        elif "/advancements/" in path_lower:
            return "advancement"
        elif "/loot_tables/" in path_lower:
            return "loot_table"
        else:
            return "unknown"

    def _get_pack_type_from_path(self, file_path: str) -> str:
        """파일 경로에서 팩 타입 추출"""
        path_lower = file_path.lower().replace("\\", "/")

        if "/datapacks/" in path_lower:
            return "datapack"
        elif "/resourcepacks/" in path_lower:
            return "resourcepack"
        else:
            return "unknown"

    def _get_key_priority(self, key: str) -> int:
        """키에 따른 우선순위 설정"""
        if key in ["title", "name"]:
            return 10  # 제목/이름은 높은 우선순위
        elif key in ["description", "text"]:
            return 6  # 설명은 중간 우선순위
        elif key == "subtitle":
            return 4  # 부제목은 낮은 우선순위
        else:
            return 2  # 기타는 낮은 우선순위


class PaxiDatapackFilter(PaxiFilter):
    """Paxi 데이터팩 전용 필터"""

    name = "paxi_datapack"

    path_patterns = [
        r".*/paxi/datapacks/.*\.zip_extracted/.*\.json$",
    ]

    def get_priority(self) -> int:
        """데이터팩은 더 높은 우선순위"""
        return 9


class PaxiResourcepackFilter(PaxiFilter):
    """Paxi 리소스팩 전용 필터"""

    name = "paxi_resourcepack"

    path_patterns = [
        r".*/paxi/resourcepacks/.*\.zip_extracted/.*\.json$",
    ]

    def get_priority(self) -> int:
        """리소스팩은 높은 우선순위"""
        return 8
