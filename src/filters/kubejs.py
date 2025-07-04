"""
KubeJS 스크립트용 번역 필터

KubeJS JavaScript 파일에서 displayName, addTooltip 등의
번역 대상 메서드 호출을 찾아 추출합니다.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List

from ..parsers.base import BaseParser
from .base import BaseFilter, TranslationEntry

logger = logging.getLogger(__name__)


class KubeJSFilter(BaseFilter):
    """KubeJS JavaScript 파일을 위한 필터"""

    name = "kubejs"

    # KubeJS 관련 파일들
    path_patterns = [
        r".*/kubejs/.*\.js$",
        r".*/kubejs/.*\.js\.converted$",
    ]

    file_patterns = [r".*\.js$", r".*\.js\.converted$"]

    # 번역 대상 메서드들 (old 로더 참고)
    DISPLAY_METHODS = [
        "displayName",
        "formattedDisplayName",
    ]

    # 색상 메서드들
    COLOR_NAMES = [
        "black",
        "darkBlue",
        "darkGreen",
        "darkAqua",
        "darkRed",
        "darkPurple",
        "gold",
        "gray",
        "darkGray",
        "blue",
        "green",
        "aqua",
        "red",
        "lightPurple",
        "yellow",
        "white",
        "of",
    ]

    # 두 번째 인수를 번역하는 함수들
    SECOND_ARG_TRANSLATE_FUNCS = [
        "addTooltip",
    ]

    def __init__(self):
        super().__init__()
        self._compile_js_patterns()

    def _compile_js_patterns(self):
        """JavaScript 번역 패턴들을 컴파일합니다."""
        # 패턴 1: .displayName( "..." ) 형태 (선행 dot 포함)
        self._display_pattern = re.compile(
            rf"\.({'|'.join(self.DISPLAY_METHODS)})\s*\(\s*([\'\"`])((?:[^\\\n]|\\.)*?)\2\s*\)",
            re.MULTILINE,
        )

        # 패턴 2: Text.yellow("...") / Component.blue(`...`) 등 모든 Text/Component 메서드
        self._text_component_pattern = re.compile(
            rf"((?:Text|Component)\.({'|'.join(self.COLOR_NAMES)}))\s*\(\s*([\'\"`])((?:[^\\\n]|\\.)*?)\3\s*\)",
            re.MULTILINE,
        )

        # 패턴 3: addTooltip('id', 'text', ...)
        self._second_arg_pattern = re.compile(
            rf"({'|'.join(self.SECOND_ARG_TRANSLATE_FUNCS)})\s*\(([^,]+?),\s*([\'\"`])((?:[^\\]|\\.)*?)\3(\s*(?:,[^)]*)?)\)",
            re.DOTALL,
        )

        # 모든 패턴 리스트
        self.patterns = [
            self._display_pattern,
            self._text_component_pattern,
            self._second_arg_pattern,
        ]

    def get_priority(self) -> int:
        """KubeJS는 특화 필터이므로 높은 우선순위"""
        return 12

    def can_handle_file(self, file_path: str) -> bool:
        """KubeJS 경로의 JavaScript 파일인지 확인"""
        if not super().can_handle_file(file_path):
            return False

        # .js.converted 파일은 이 로더가 처리 (다른 로더가 주석 등을 번역하지 못하도록)
        return True

    async def extract_translations(self, file_path: str) -> List[TranslationEntry]:
        """KubeJS JavaScript 파일에서 번역 대상 추출"""
        try:
            # JS 파서 사용
            parser_class = BaseParser.get_parser_by_extension(".js")
            if not parser_class:
                logger.warning(f"JS 파서를 찾을 수 없음: {file_path}")
                return []

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            entries = []

            # 각 청크/라인별로 처리
            for key, content in data.items():
                if isinstance(content, str):
                    # 패턴이 하나도 없으면 스킵 (주석 등이 번역되지 않도록)
                    if not any(pattern.search(content) for pattern in self.patterns):
                        continue

                    # JavaScript 패턴들 찾기
                    line_entries = self._extract_js_patterns(content, file_path, key)
                    entries.extend(line_entries)

            logger.debug(
                f"KubeJS 파일에서 {len(entries)}개 번역 항목 발견: {Path(file_path).name}"
            )
            return entries

        except Exception as e:
            logger.error(f"KubeJS 파일 처리 실패 ({file_path}): {e}")
            return []

    def _extract_js_patterns(
        self, content: str, file_path: str, chunk_key: str
    ) -> List[TranslationEntry]:
        """JavaScript 내용에서 번역 패턴들 추출"""
        entries = []

        # 패턴 1: .displayName("...")
        for match in self._display_pattern.finditer(content):
            method_name = match.group(1)
            quote_char = match.group(2)
            text_content = match.group(3)

            if text_content.strip():
                entry = TranslationEntry(
                    key=f"{chunk_key}.{method_name}_{match.start()}",
                    original_text=text_content,
                    file_path=file_path,
                    file_type=self.name,
                    context={
                        "method": method_name,
                        "quote_char": quote_char,
                        "pattern_type": "display_method",
                        "chunk_key": chunk_key,
                        "match_start": match.start(),
                        "match_end": match.end(),
                    },
                    priority=self._get_method_priority(method_name),
                )
                entries.append(entry)

        # 패턴 2: Text.color("...")
        for match in self._text_component_pattern.finditer(content):
            full_method = match.group(1)
            color_name = match.group(2)
            quote_char = match.group(3)
            text_content = match.group(4)

            if text_content.strip():
                entry = TranslationEntry(
                    key=f"{chunk_key}.{full_method}_{match.start()}",
                    original_text=text_content,
                    file_path=file_path,
                    file_type=self.name,
                    context={
                        "method": full_method,
                        "color": color_name,
                        "quote_char": quote_char,
                        "pattern_type": "text_component",
                        "chunk_key": chunk_key,
                        "match_start": match.start(),
                        "match_end": match.end(),
                    },
                    priority=8,
                )
                entries.append(entry)

        # 패턴 3: addTooltip('id', 'text', ...)
        for match in self._second_arg_pattern.finditer(content):
            func_name = match.group(1)
            first_arg = match.group(2)
            quote_char = match.group(3)
            text_content = match.group(4)

            if text_content.strip():
                # 첫 번째 인자에서 따옴표 제거하고 정리하여 고유 키 생성
                first_arg_clean = first_arg.strip().strip("'\"")
                unique_key = (
                    f"{chunk_key}.{func_name}_{first_arg_clean}_arg2_{match.start()}"
                )

                entry = TranslationEntry(
                    key=unique_key,
                    original_text=text_content,
                    file_path=file_path,
                    file_type=self.name,
                    context={
                        "method": func_name,
                        "first_arg": first_arg.strip(),
                        "quote_char": quote_char,
                        "pattern_type": "second_arg",
                        "chunk_key": chunk_key,
                        "match_start": match.start(),
                        "match_end": match.end(),
                    },
                    priority=7,
                )
                entries.append(entry)

        return entries

    async def apply_translations(
        self, file_path: str, translations: Dict[str, str]
    ) -> bool:
        """번역된 텍스트를 JS 파일에 적용합니다."""
        try:
            # JS 파서 사용하여 원본 파일 읽기
            parser_class = BaseParser.get_parser_by_extension(".js")
            if not parser_class:
                logger.warning(f"JS 파서를 찾을 수 없음: {file_path}")
                return False

            parser = parser_class(Path(file_path))
            data = await parser.parse()

            # 각 청크별로 번역 적용
            updated = False
            for key, content in data.items():
                if isinstance(content, str):
                    # 이 청크에서 번역 적용
                    new_content = self._apply_translations_to_content(
                        content, translations, key
                    )
                    if new_content != content:
                        data[key] = new_content
                        updated = True

            if updated:
                # 번역이 적용된 파일 저장
                await parser.dump(data)
                logger.debug(f"번역 적용 완료: {Path(file_path).name}")
                return True
            else:
                logger.debug(f"번역 적용할 내용 없음: {Path(file_path).name}")
                return False

        except Exception as e:
            logger.error(f"번역 적용 실패 ({file_path}): {e}")
            return False

    def _apply_translations_to_content(
        self, content: str, translations: Dict[str, str], chunk_key: str
    ) -> str:
        """컨텐츠에 번역을 적용합니다."""
        updated_content = content

        # 패턴 1: .displayName("...")
        def replace_display_method(match):
            method_name = match.group(1)
            quote_char = match.group(2)
            original_text = match.group(3)

            # 번역된 텍스트 찾기 (위치 정보 포함)
            translation_key = f"{chunk_key}.{method_name}_{match.start()}"
            if translation_key in translations:
                translated_text = translations[translation_key]
                return f".{method_name}({quote_char}{translated_text}{quote_char})"
            return match.group(0)  # 번역이 없으면 원본 반환

        updated_content = self._display_pattern.sub(
            replace_display_method, updated_content
        )

        # 패턴 2: Text.color("...")
        def replace_text_component(match):
            full_method = match.group(1)
            color_name = match.group(2)
            quote_char = match.group(3)
            original_text = match.group(4)

            # 번역된 텍스트 찾기 (위치 정보 포함)
            translation_key = f"{chunk_key}.{full_method}_{match.start()}"
            if translation_key in translations:
                translated_text = translations[translation_key]
                return f"{full_method}({quote_char}{translated_text}{quote_char})"
            return match.group(0)  # 번역이 없으면 원본 반환

        updated_content = self._text_component_pattern.sub(
            replace_text_component, updated_content
        )

        # 패턴 3: addTooltip('id', 'text', ...)
        def replace_second_arg(match):
            func_name = match.group(1)
            first_arg = match.group(2)
            quote_char = match.group(3)
            original_text = match.group(4)
            remaining_args = match.group(5) if match.group(5) else ""

            # 첫 번째 인자에서 따옴표 제거하고 정리하여 고유 키 생성 (위치 정보 포함)
            first_arg_clean = first_arg.strip().strip("'\"")
            translation_key = (
                f"{chunk_key}.{func_name}_{first_arg_clean}_arg2_{match.start()}"
            )

            if translation_key in translations:
                translated_text = translations[translation_key]
                return f"{func_name}({first_arg}, {quote_char}{translated_text}{quote_char}{remaining_args})"
            return match.group(0)  # 번역이 없으면 원본 반환

        updated_content = self._second_arg_pattern.sub(
            replace_second_arg, updated_content
        )

        return updated_content

    def _get_method_priority(self, method_name: str) -> int:
        """메서드별 우선순위 설정"""
        if method_name in ["displayName", "formattedDisplayName"]:
            return 10  # 표시 이름은 높은 우선순위
        elif method_name in self.SECOND_ARG_TRANSLATE_FUNCS:
            return 7  # 툴팁 등은 중간 우선순위
        else:
            return 5  # 기타는 낮은 우선순위


class KubeJSClientFilter(KubeJSFilter):
    """KubeJS 클라이언트 스크립트 전용 필터"""

    name = "kubejs_client"

    path_patterns = [
        r".*/kubejs/client_scripts/.*\.js$",
        r".*/kubejs/client/.*\.js$",
    ]

    def get_priority(self) -> int:
        """클라이언트 스크립트는 더 높은 우선순위"""
        return 13


class KubeJSStartupFilter(KubeJSFilter):
    """KubeJS 스타트업 스크립트 전용 필터"""

    name = "kubejs_startup"

    path_patterns = [
        r".*/kubejs/startup_scripts/.*\.js$",
        r".*/kubejs/startup/.*\.js$",
    ]

    def get_priority(self) -> int:
        """스타트업 스크립트는 높은 우선순위"""
        return 13


class KubeJSServerFilter(KubeJSFilter):
    """KubeJS 서버 스크립트 전용 필터"""

    name = "kubejs_server"

    path_patterns = [
        r".*/kubejs/server_scripts/.*\.js$",
        r".*/kubejs/server/.*\.js$",
    ]

    def get_priority(self) -> int:
        """서버 스크립트는 일반 우선순위"""
        return 11
