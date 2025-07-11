"""
FTBQuests 모드용 번역 필터

FTBQuests의 chapters, quests, tasks 등에서
번역 대상 텍스트를 추출합니다.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from ..parsers.base import BaseParser
from .base import BaseFilter, TranslationEntry

logger = logging.getLogger(__name__)


class FTBQuestsFilter(BaseFilter):
    """FTBQuests 파일을 위한 기본 필터"""

    name = "ftbquests"

    # FTBQuests 관련 파일들
    path_patterns = [
        r".*/ftbquests/quests/chapters/.*\.snbt$",
        r".*/config/ftbquests/.*\.snbt$",
    ]

    # 번역 대상 키들 (old 로더 참고)
    key_whitelist = {
        "text",
        "title",
        "subtitle",
        "description",
        "name",
        "quest_desc",
        "quest_subtitle",
        "Lore",  # 아이템 Lore 처리
        "Name",  # 아이템 Name 처리
    }

    def get_priority(self) -> int:
        """FTBQuests는 특화 필터이므로 높은 우선순위"""
        return 10

    def should_translate_key(self, key: str) -> bool:
        """키가 번역 대상인지 확인 (화이트리스트 방식)"""
        # 경로를 분리해서 마지막 키만 확인
        key_parts = key.split(".")
        last_key = key_parts[-1]

        # 배열 인덱스 제거 (예: "description[0]" -> "description")
        if "[" in last_key:
            last_key = last_key.split("[")[0]

        return last_key in self.key_whitelist

    def _is_json_text(self, text: str) -> bool:
        """문자열이 JSON 형태의 텍스트인지 확인"""
        try:
            if text.startswith('{"') and text.endswith('"}'):
                json.loads(text)
                return True
        except (json.JSONDecodeError, ValueError):
            pass
        return False

    def _extract_json_text(self, json_string: str) -> str:
        """JSON 문자열에서 'text' 필드 추출"""
        try:
            json_data = json.loads(json_string)
            if isinstance(json_data, dict) and "text" in json_data:
                return json_data["text"]
        except (json.JSONDecodeError, ValueError):
            pass
        return ""

    def _reconstruct_json_text(self, json_string: str, new_text: str) -> str:
        """JSON 문자열의 'text' 필드를 새로운 텍스트로 교체"""
        try:
            json_data = json.loads(json_string)
            if isinstance(json_data, dict) and "text" in json_data:
                json_data["text"] = new_text
                return json.dumps(json_data, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pass
        return json_string

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """FTBQuests 파일에서 번역 대상 추출"""
        try:
            # SNBT 파서 사용
            parser_class = BaseParser.get_parser_by_extension(".snbt")
            if not parser_class:
                logger.warning(f"SNBT 파서를 찾을 수 없음: {file_path}")
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            entries = []

            # 재귀적으로 모든 키-값 쌍 검사 (old 로더 방식)
            self._extract_from_dict(data, entries, file_path, "")

            logger.debug(
                f"FTBQuests 파일에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"FTBQuests 파일 처리 실패 ({file_path}): {e}")
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
                    # JSON 형태의 텍스트인지 확인
                    if self._is_json_text(value):
                        # JSON에서 text 필드 추출
                        json_text = self._extract_json_text(value)
                        if json_text.strip():
                            entry = TranslationEntry(
                                key=full_key,
                                original_text=json_text,
                                file_path=file_path,
                                file_type=self.name,
                                context={
                                    "file_type": "ftbquests",
                                    "category": self._get_category_from_path(file_path),
                                    "key_path": full_key,
                                    "is_json": True,
                                    "original_json": value,
                                },
                                priority=self._get_key_priority(key),
                            )
                            entries.append(entry)
                    else:
                        # 일반 텍스트
                        entry = TranslationEntry(
                            key=full_key,
                            original_text=value,
                            file_path=file_path,
                            file_type=self.name,
                            context={
                                "file_type": "ftbquests",
                                "category": self._get_category_from_path(file_path),
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
                        # 빈 문자열("")도 번역 대상으로 포함 (리스트 구조 유지를 위해)
                        # 단, 공백만 있는 문자열은 제외
                        if item or item == "":
                            # JSON 형태의 텍스트인지 확인
                            if self._is_json_text(item):
                                # JSON에서 text 필드 추출
                                json_text = self._extract_json_text(item)
                                if json_text.strip():
                                    entry = TranslationEntry(
                                        key=f"{full_key}[{i}]",
                                        original_text=json_text,
                                        file_path=file_path,
                                        file_type=self.name,
                                        context={
                                            "file_type": "ftbquests",
                                            "category": self._get_category_from_path(
                                                file_path
                                            ),
                                            "key_path": full_key,
                                            "list_index": i,
                                            "is_json": True,
                                            "original_json": item,
                                        },
                                        priority=self._get_key_priority(key),
                                    )
                                    entries.append(entry)
                            else:
                                # 일반 텍스트
                                entry = TranslationEntry(
                                    key=f"{full_key}[{i}]",
                                    original_text=item,
                                    file_path=file_path,
                                    file_type=self.name,
                                    context={
                                        "file_type": "ftbquests",
                                        "category": self._get_category_from_path(
                                            file_path
                                        ),
                                        "key_path": full_key,
                                        "list_index": i,
                                        "is_empty_string": item == "",
                                    },
                                    priority=self._get_key_priority(key),
                                )
                                entries.append(entry)

    async def apply_translations(
        self, file_path: str, translations: Dict[str, str]
    ) -> bool:
        """번역된 텍스트를 SNBT 파일에 적용합니다."""
        try:
            # SNBT 파서 사용하여 원본 파일 읽기
            parser_class = BaseParser.get_parser_by_extension(".snbt")
            if not parser_class:
                logger.warning(f"SNBT 파서를 찾을 수 없음: {file_path}")
                return False

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            # 번역 적용
            updated = self._apply_translations_to_dict(data, translations, "")

            if updated:
                # 번역이 적용된 파일 저장
                await parser.dump(data)
                logger.debug(f"FTBQuests 번역 적용 완료: {Path(file_path).name}")
                return True
            else:
                logger.debug(f"FTBQuests 번역 적용할 내용 없음: {Path(file_path).name}")
                return False

        except Exception as e:
            logger.error(f"FTBQuests 번역 적용 실패 ({file_path}): {e}")
            return False

    def _apply_translations_to_dict(
        self, data: Dict[str, Any], translations: Dict[str, str], key_prefix: str = ""
    ) -> bool:
        """딕셔너리에 재귀적으로 번역 적용"""
        if not isinstance(data, dict):
            return False

        updated = False

        for key, value in data.items():
            full_key = f"{key_prefix}.{key}" if key_prefix else key

            if isinstance(value, str):
                # 문자열 값인 경우
                if full_key in translations:
                    # JSON 형태의 텍스트인지 확인
                    if self._is_json_text(value):
                        # JSON 문자열의 text 필드를 번역으로 교체
                        translated_json = self._reconstruct_json_text(
                            value, translations[full_key]
                        )
                        data[key] = translated_json
                    else:
                        # 일반 텍스트
                        data[key] = translations[full_key]
                    updated = True

            elif isinstance(value, dict):
                # 중첩된 딕셔너리인 경우 재귀 처리
                if self._apply_translations_to_dict(value, translations, full_key):
                    updated = True

            elif isinstance(value, list):
                # 리스트인 경우 각 항목 처리
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        if self._apply_translations_to_dict(
                            item, translations, f"{full_key}[{i}]"
                        ):
                            updated = True
                    elif isinstance(item, str):
                        # 리스트 항목의 번역 키 생성
                        list_item_key = f"{full_key}[{i}]"
                        if list_item_key in translations:
                            # JSON 형태의 텍스트인지 확인
                            if self._is_json_text(item):
                                # JSON 문자열의 text 필드를 번역으로 교체
                                translated_json = self._reconstruct_json_text(
                                    item, translations[list_item_key]
                                )
                                data[key][i] = translated_json
                            else:
                                # 일반 텍스트 (빈 문자열("")도 번역 결과로 교체)
                                data[key][i] = translations[list_item_key]
                            updated = True

        return updated

    def _get_category_from_path(self, file_path: str) -> str:
        """파일 경로에서 카테고리 추출"""
        path_lower = file_path.lower().replace("\\", "/")

        if "chapters" in path_lower:
            return "chapter"
        elif "quests" in path_lower:
            return "quest"
        elif "tasks" in path_lower:
            return "task"
        else:
            return "unknown"

    def _get_key_priority(self, key: str) -> int:
        """키에 따른 우선순위 설정"""
        if key in ["title", "name"]:
            return 10  # 제목은 높은 우선순위
        elif key in ["description", "text"]:
            return 5  # 설명은 중간 우선순위
        else:
            return 1  # 기타는 낮은 우선순위


class FTBQuestsChapterFilter(FTBQuestsFilter):
    """FTBQuests 챕터 전용 필터 (퀘스트 배열 처리)"""

    name = "ftbquests_chapter"

    path_patterns = [
        r".*/ftbquests/quests/chapters/.*\.snbt$",
    ]

    def get_priority(self) -> int:
        """챕터 전용 필터는 더 높은 우선순위"""
        return 15

    def can_handle_file(self, file_path: str) -> bool:
        """챕터 파일이고 quests 배열이 있는 파일만 처리"""
        return super().can_handle_file(file_path)

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """챕터 파일에서 모든 중첩 구조를 재귀적으로 처리"""
        try:
            parser_class = BaseParser.get_parser_by_extension(".snbt")
            if not parser_class:
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            entries = []

            # 기본 재귀 처리로 모든 중첩 구조를 처리 (quests 배열 포함)
            self._extract_from_dict(data, entries, file_path, "")

            logger.debug(
                f"FTBQuests 챕터에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"FTBQuests 챕터 파일 처리 실패 ({file_path}): {e}")
            return []


class FTBQuestsRewardTableFilter(FTBQuestsFilter):
    """FTBQuests 보상 테이블 전용 필터"""

    name = "ftbquests_reward_table"

    path_patterns = [
        r".*/ftbquests/.*reward.*\.snbt$",
        r".*/config/ftbquests/.*reward.*\.snbt$",
    ]

    def get_priority(self) -> int:
        return 12


class FTBQuestsLangFilter(BaseFilter):
    """FTBQuests 언어 파일(.snbt) 전용 필터"""

    name = "ftbquests_lang"
    path_patterns = [r".*/ftbquests/quests/lang/.*\.snbt$"]

    def get_priority(self) -> int:
        """언어 파일 전용 필터는 다른 FTBQuests 필터보다 높은 우선순위를 가집니다."""
        return 20

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """FTBQuests 언어 파일에서 번역 대상을 추출합니다."""
        try:
            parser_class = BaseParser.get_parser_by_extension(".snbt")
            if not parser_class:
                logger.warning(f"SNBT 파서를 찾을 수 없음: {file_path}")
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()
            entries = []

            if not isinstance(data, dict):
                logger.warning(
                    f"FTBQuests 언어 파일이 딕셔너리 형식이 아님: {file_path}"
                )
                return []

            for key, value in data.items():
                if isinstance(value, str) and value.strip():
                    entries.append(
                        TranslationEntry(
                            key=key,
                            original_text=value,
                            file_path=file_path,
                            file_type=self.name,
                            context={"file_type": "ftbquests_lang", "key": key},
                            priority=10,
                        )
                    )
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, str) and item.strip():
                            entries.append(
                                TranslationEntry(
                                    key=f"{key}[{i}]",
                                    original_text=item,
                                    file_path=file_path,
                                    file_type=self.name,
                                    context={
                                        "file_type": "ftbquests_lang",
                                        "key": key,
                                        "list_index": i,
                                    },
                                    priority=10,
                                )
                            )
            logger.debug(
                f"FTBQuests 언어 파일에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"FTBQuests 언어 파일 처리 실패 ({file_path}): {e}")
            return []

    async def apply_translations(
        self, file_path: str, translations: Dict[str, str]
    ) -> bool:
        """번역된 텍스트를 SNBT 언어 파일에 적용합니다."""
        try:
            parser_class = BaseParser.get_parser_by_extension(".snbt")
            if not parser_class:
                logger.warning(f"SNBT 파서를 찾을 수 없음: {file_path}")
                return False

            parser = parser_class(Path(file_path))
            flat_data = await parser.parse()

            if not isinstance(flat_data, dict):
                return False

            updated = False
            for key, translated_text in translations.items():
                if key in flat_data and flat_data[key] != translated_text:
                    flat_data[key] = translated_text
                    updated = True

            if updated:
                await parser.dump(flat_data)
                logger.debug(
                    f"FTBQuests 언어 파일 번역 적용 완료: {Path(file_path).name}"
                )
                return True

            logger.debug(
                f"FTBQuests 언어 파일에 적용할 번역 변경 사항 없음: {Path(file_path).name}"
            )
            return False

        except Exception as e:
            logger.error(f"FTBQuests 언어 파일 번역 적용 실패 ({file_path}): {e}")
            return False
