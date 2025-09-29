from __future__ import annotations

import abc
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..parsers.base import BaseParser

logger = logging.getLogger(__name__)


class TranslationEntry:
    """번역 대상 항목을 나타내는 클래스"""

    def __init__(
        self,
        key: str,
        original_text: str,
        file_path: str,
        file_type: str,
        context: Optional[Dict[str, Any]] = None,
        priority: int = 0,
    ):
        """
        Args:
            key: 번역 키 (예: "item.minecraft.stone")
            original_text: 원본 텍스트
            file_path: 파일 경로
            file_type: 파일 타입 (예: "ftbquests", "kubejs")
            context: 추가 컨텍스트 정보
            priority: 번역 우선순위 (높을수록 우선)
        """
        self.key = key
        self.original_text = original_text
        self.file_path = file_path
        self.file_type = file_type
        self.context = context or {}
        self.priority = priority

    def __repr__(self) -> str:
        return f"TranslationEntry(key='{self.key}', text='{self.original_text[:50]}...', file='{Path(self.file_path).name}')"


class BaseFilter(abc.ABC):
    """번역 대상 필터링을 위한 기본 클래스"""

    # 필터 이름 (하위 클래스에서 설정)
    name: str = ""

    # 처리할 파일 패턴들 (정규표현식)
    file_patterns: List[str] = []

    # 처리할 파일 경로 패턴들 (정규표현식)
    path_patterns: List[str] = []

    # 번역 대상 키 패턴들 (정규표현식)
    key_patterns: List[str] = []

    # 번역 제외 키 패턴들 (정규표현식)
    exclude_key_patterns: List[str] = []

    # 번역 대상 키 화이트리스트 (정확한 키 매칭)
    key_whitelist: Set[str] = set()

    # 번역 제외 키 블랙리스트 (정확한 키 매칭)
    key_blacklist: Set[str] = set()

    # 지원되는 언어 코드들 (Minecraft 표준)
    LANGUAGE_CODES = {
        "en_us",
        "ko_kr",
        "ja_jp",
        "zh_cn",
        "zh_tw",
        "fr_fr",
        "de_de",
        "es_es",
        "pt_br",
        "ru_ru",
        "it_it",
        "pl_pl",
        "tr_tr",
        "nl_nl",
        "sv_se",
        "da_dk",
        "no_no",
        "fi_fi",
        "cs_cz",
        "sk_sk",
        "hu_hu",
        "ro_ro",
        "bg_bg",
        "hr_hr",
        "sl_si",
        "et_ee",
        "lv_lv",
        "lt_lt",
        "ar_sa",
        "he_il",
        "th_th",
        "vi_vn",
        "id_id",
        "ms_my",
        "tl_ph",
    }

    def __init__(self):
        """필터 초기화"""
        self._compile_patterns()
        self._compile_language_pattern()

    def _compile_patterns(self):
        """정규표현식 패턴들을 컴파일합니다."""
        self._compiled_file_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.file_patterns
        ]
        self._compiled_path_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.path_patterns
        ]
        self._compiled_key_patterns = [
            re.compile(pattern) for pattern in self.key_patterns
        ]
        self._compiled_exclude_patterns = [
            re.compile(pattern) for pattern in self.exclude_key_patterns
        ]

    def _compile_language_pattern(self):
        """언어 코드 패턴을 컴파일합니다."""
        # 언어 코드 패턴: /언어코드/ 또는 /lang/언어코드. 형태
        language_pattern = r"/(?:" + "|".join(self.LANGUAGE_CODES) + r")(?:/|\.)"
        self._compiled_language_pattern = re.compile(language_pattern, re.IGNORECASE)

    def _is_source_language_file(self, file_path: str) -> bool:
        """
        파일이 소스 언어(en_us) 파일인지 확인합니다.
        언어 코드가 경로에 포함된 경우 en_us만 허용합니다.

        Args:
            file_path: 파일 경로

        Returns:
            소스 언어 파일 여부 (언어 코드가 없거나 en_us인 경우 True)
        """
        file_path_normalized = file_path.replace("\\", "/").lower()

        # 언어 코드가 경로에 포함되어 있는지 확인
        if self._compiled_language_pattern.search(file_path_normalized):
            # 언어 코드가 있는 경우 en_us만 허용
            return (
                "/en_us/" in file_path_normalized
                or "/lang/en_us." in file_path_normalized
            )

        # 언어 코드가 없는 경우 허용
        return True

    def can_handle_file(self, file_path: str) -> bool:
        """
        파일을 이 필터가 처리할 수 있는지 확인합니다.

        Args:
            file_path: 파일 경로

        Returns:
            처리 가능 여부
        """
        # 먼저 언어 필터링 확인 (en_us가 아닌 다른 언어 파일 제외)
        if not self._is_source_language_file(file_path):
            return False

        file_path_normalized = file_path.replace("\\", "/")
        file_name = Path(file_path).name

        # 파일명 패턴 확인
        for pattern in self._compiled_file_patterns:
            if pattern.search(file_name):
                return True

        # 경로 패턴 확인
        for pattern in self._compiled_path_patterns:
            if pattern.search(file_path_normalized):
                return True

        return False

    def should_translate_key(self, key: str) -> bool:
        """
        특정 키가 번역 대상인지 확인합니다.

        Args:
            key: 확인할 키

        Returns:
            번역 대상 여부
        """
        # 블랙리스트 확인
        if key in self.key_blacklist:
            return False

        # 제외 패턴 확인
        for pattern in self._compiled_exclude_patterns:
            if pattern.search(key):
                return False

        # 화이트리스트 확인
        if key in self.key_whitelist:
            return True

        # 키 패턴 확인
        for pattern in self._compiled_key_patterns:
            if pattern.search(key):
                return True

        return False

    @abc.abstractmethod
    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """
        파일에서 번역 대상 항목들을 추출합니다.

        Args:
            file_path: 파일 경로

        Returns:
            번역 대상 항목 리스트
        """
        pass

    def get_priority(self) -> int:
        """
        필터의 처리 우선순위를 반환합니다.
        높을수록 우선 처리됩니다.

        Returns:
            우선순위 (기본값: 0)
        """
        return 0


class GenericJSONFilter(BaseFilter):
    """모드팩 언어 파일(en_us.json)을 위한 필터"""

    name = "generic_json"

    path_patterns = [
        r".*/lang/en_us\.json$",
        r".*/en_us\.json$",
        r".*/lang/en_US\.lang$",
        r".*/en_US\.lang$",
    ]

    def __init__(
        self,
        key_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        path_patterns: Optional[List[str]] = None,
    ):
        """
        Args:
            key_patterns: 번역 대상 키 패턴들
            exclude_patterns: 제외할 키 패턴들
            path_patterns: 처리할 경로 패턴들
        """
        if key_patterns:
            self.key_patterns = key_patterns
        if exclude_patterns:
            self.exclude_key_patterns = exclude_patterns
        if path_patterns:
            self.path_patterns = path_patterns

        super().__init__()

    def get_priority(self) -> int:
        """GenericJSON 필터는 가장 낮은 우선순위 (fallback)"""
        return 0  # 모든 특화 필터들이 처리된 후 마지막에 적용

    def should_translate_key(self, key: str) -> bool:
        """언어 파일의 모든 키를 번역 대상으로 처리"""
        # 언어 파일은 기본적으로 모든 키가 번역 대상
        # 단, 명시적으로 제외된 키는 제외

        # 부모 클래스에서 제외 패턴 확인
        for pattern in self._compiled_exclude_patterns:
            if pattern.search(key):
                return False

        # 블랙리스트 확인
        if key in self.key_blacklist:
            return False

        # 기본적으로 모든 키 허용 (언어 파일이므로)
        return True

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """JSON 파일에서 번역 대상 추출"""
        try:
            # 파서를 통해 데이터 로드
            file_extension = Path(file_path).suffix
            parser_class = BaseParser.get_parser_by_extension(file_extension)
            if not parser_class:
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            entries = []
            self._extract_from_dict(data, entries, file_path, "")

            logger.debug(
                f"GenericJSON 필터에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"JSON 파일 처리 실패 ({file_path}): {e}")
            return []

    def _extract_from_dict(
        self,
        data: Any,
        entries: List[TranslationEntry],
        file_path: str,
        key_prefix: str = "",
    ):
        """언어 파일에서 재귀적으로 번역 대상 추출"""
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{key_prefix}.{key}" if key_prefix else key

                if isinstance(value, str):
                    # 언어 파일의 문자열 값은 모두 번역 대상
                    if value.strip():  # 빈 문자열이 아닌 경우만
                        entry = TranslationEntry(
                            key=full_key,
                            original_text=value,
                            file_path=file_path,
                            file_type=self.name,
                            context={
                                "file_type": "language_json",
                                "key_path": full_key,
                                "is_lang_file": True,
                            },
                            priority=self.get_priority(),
                        )
                        entries.append(entry)

                elif isinstance(value, (dict, list)):
                    # 중첩된 구조인 경우 재귀 처리
                    self._extract_from_dict(value, entries, file_path, full_key)

        elif isinstance(data, list):
            # 리스트인 경우 각 항목 처리
            for i, item in enumerate(data):
                list_key = f"{key_prefix}[{i}]"
                if isinstance(item, str) and item.strip():
                    entry = TranslationEntry(
                        key=list_key,
                        original_text=item,
                        file_path=file_path,
                        file_type=self.name,
                        context={
                            "file_type": "language_json",
                            "list_index": i,
                            "key_path": key_prefix,
                            "is_lang_file": True,
                        },
                        priority=self.get_priority(),
                    )
                    entries.append(entry)
                elif isinstance(item, (dict, list)):
                    self._extract_from_dict(item, entries, file_path, list_key)


class FilterManager:
    """번역 필터들을 관리하는 클래스"""

    def __init__(self):
        """필터 매니저 초기화"""
        self._filters: List[BaseFilter] = []
        self.register_default_filters()

    def register_filter(self, filter_instance: BaseFilter):
        """
        필터를 등록합니다.

        Args:
            filter_instance: 등록할 필터 인스턴스
        """
        self._filters.append(filter_instance)
        # 우선순위 순으로 정렬
        self._filters.sort(key=lambda f: f.get_priority(), reverse=True)
        logger.info(f"필터 등록됨: {filter_instance.name}")

    def register_default_filters(self):
        """기본 필터들을 등록합니다."""
        # 모드별 필터들을 등록하도록 하위 클래스에서 구현하거나
        # 별도로 필터를 등록할 수 있도록 기본만 등록
        # 일반 JSON 필터 등록
        generic_filter = GenericJSONFilter()
        self.register_filter(generic_filter)

    def get_applicable_filters(self, file_path: str) -> List[BaseFilter]:
        """
        파일에 적용 가능한 필터들을 반환합니다.

        Args:
            file_path: 파일 경로

        Returns:
            적용 가능한 필터 리스트
        """
        applicable_filters = []
        for filter_instance in self._filters:
            if filter_instance.can_handle_file(file_path):
                applicable_filters.append(filter_instance)

        return applicable_filters

    async def extract_translations_from_file(
        self, file_path: str
    ) -> List[TranslationEntry]:
        """
        파일에서 번역 대상들을 추출합니다.

        Args:
            file_path: 파일 경로

        Returns:
            번역 대상 항목 리스트
        """
        applicable_filters = self.get_applicable_filters(file_path)

        if not applicable_filters:
            logger.debug(f"적용 가능한 필터가 없음: {file_path}")
            return []

        all_entries = []
        for filter_instance in applicable_filters:
            try:
                entries = await filter_instance.extract_translations(file_path)
                all_entries.extend(entries)
                logger.debug(
                    f"{filter_instance.name} 필터로 {len(entries)}개 항목 추출: {Path(file_path).name}"
                )
            except Exception as e:
                logger.error(
                    f"필터 실행 실패 ({filter_instance.name}, {file_path}): {e}"
                )

        return all_entries

    async def extract_translations_from_files(
        self, file_list: List[Dict[str, str]]
    ) -> List[TranslationEntry]:
        """
        여러 파일에서 번역 대상들을 추출합니다.

        Args:
            file_list: 파일 정보 리스트 (ModpackLoader에서 반환된 형태)

        Returns:
            모든 번역 대상 항목 리스트
        """
        all_entries = []

        for file_info in file_list:
            file_path = file_info.get("input", "")
            if not file_path:
                continue

            entries = await self.extract_translations_from_file(file_path)
            all_entries.extend(entries)

        logger.info(
            f"총 {len(file_list)}개 파일에서 {len(all_entries)}개 번역 항목 추출"
        )
        return all_entries

    def get_registered_filters(self) -> List[str]:
        """등록된 필터 이름들을 반환합니다."""
        return [f.name for f in self._filters]

    def get_filter_by_name(self, name: str) -> Optional[BaseFilter]:
        """이름으로 필터를 찾아 반환합니다."""
        for filter_instance in self._filters:
            if filter_instance.name == name:
                return filter_instance
        return None


class ExtendedFilterManager(FilterManager):
    """모든 모드 필터들을 자동으로 등록하는 확장된 필터 매니저"""

    def register_default_filters(self):
        """기본 필터와 모든 모드 필터들을 등록합니다."""
        # 기본 JSON 필터 등록
        super().register_default_filters()

        # 모드별 필터들을 등록
        try:
            self._register_mod_filters()
        except ImportError as e:
            logger.warning(f"일부 모드 필터를 로드할 수 없음: {e}")

    def _register_mod_filters(self):
        """모든 모드 필터들을 등록합니다."""
        # FTBQuests 필터들
        try:
            from .ftbquests import (
                FTBQuestsChapterFilter,
                FTBQuestsEnUsFilter,
                FTBQuestsFilter,
                FTBQuestsNBTFilter,
                FTBQuestsRewardTableFilter,
            )

            self.register_filter(FTBQuestsFilter())
            self.register_filter(FTBQuestsChapterFilter())
            self.register_filter(FTBQuestsRewardTableFilter())
            self.register_filter(FTBQuestsEnUsFilter())
            self.register_filter(FTBQuestsNBTFilter())
        except ImportError:
            logger.warning("FTBQuests 필터를 로드할 수 없습니다.")

        # KubeJS 필터들
        try:
            from .kubejs import (
                KubeJSClientFilter,
                KubeJSFilter,
                KubeJSServerFilter,
                KubeJSStartupFilter,
            )

            self.register_filter(KubeJSFilter())
            self.register_filter(KubeJSClientFilter())
            self.register_filter(KubeJSStartupFilter())
            self.register_filter(KubeJSServerFilter())
        except ImportError:
            logger.warning("KubeJS 필터를 로드할 수 없습니다.")

        # Origins 필터들
        try:
            from .origins import GlobalPacksOriginFilter, OriginsFilter

            self.register_filter(OriginsFilter())
            self.register_filter(GlobalPacksOriginFilter())
        except ImportError:
            logger.warning("Origins 필터를 로드할 수 없습니다.")

        # Patchouli 필터들
        try:
            from .patchouli import (
                PatchouliCategoryFilter,
                PatchouliEntryFilter,
                PatchouliFilter,
            )

            self.register_filter(PatchouliFilter())
            self.register_filter(PatchouliCategoryFilter())
            self.register_filter(PatchouliEntryFilter())
        except ImportError:
            logger.warning("Patchouli 필터를 로드할 수 없습니다.")

        # TConstruct 필터들
        try:
            from .tconstruct import TConstructFilter

            self.register_filter(TConstructFilter())
        except ImportError:
            logger.warning("TConstruct 필터를 로드할 수 없습니다.")

        # PuffishSkills 필터들
        try:
            from .puffish_skills import (
                PuffishSkillsCategoryFilter,
                PuffishSkillsDefinitionsFilter,
                PuffishSkillsFilter,
            )

            self.register_filter(PuffishSkillsFilter())
            self.register_filter(PuffishSkillsCategoryFilter())
            self.register_filter(PuffishSkillsDefinitionsFilter())
        except ImportError:
            logger.warning("PuffishSkills 필터를 로드할 수 없습니다.")

        # Paxi 필터들
        try:
            from .paxi import PaxiDatapackFilter, PaxiFilter, PaxiResourcepackFilter

            self.register_filter(PaxiFilter())
            self.register_filter(PaxiDatapackFilter())
            self.register_filter(PaxiResourcepackFilter())
        except ImportError:
            logger.warning("Paxi 필터를 로드할 수 없습니다.")

    def get_filter_summary(self) -> Dict[str, List[str]]:
        """등록된 필터들의 요약 정보를 반환합니다."""
        summary = {}

        for filter_instance in self._filters:
            mod_name = filter_instance.name.split("_")[
                0
            ]  # 첫 번째 부분을 모드명으로 사용

            if mod_name not in summary:
                summary[mod_name] = []

            summary[mod_name].append(
                {
                    "name": filter_instance.name,
                    "priority": filter_instance.get_priority(),
                    "patterns": len(filter_instance.path_patterns)
                    + len(filter_instance.file_patterns),
                }
            )

        return summary
