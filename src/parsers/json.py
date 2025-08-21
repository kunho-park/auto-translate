from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Mapping

import aiofiles

from .base import BaseParser

logger = logging.getLogger(__name__)


class JSONParser(BaseParser):
    """JSON 형식 파일을 처리하는 파서입니다.

    주석이 포함된 JSON도 처리할 수 있으며, 중첩된 JSON 구조를 평면화하여
    번역 가능한 문자열들을 추출합니다.
    """

    file_extensions = (".json",)

    # JSON 파일에서 주석 제거하는 정규식 패턴
    COMMENT_PATTERN = re.compile(r"^\s*//.*$|//.*$", re.MULTILINE)

    async def parse(self) -> Mapping[str, str]:
        """JSON 파일을 파싱하여 번역 가능한 문자열들을 추출합니다."""
        self._check_extension()

        # 비동기 파일 읽기
        async with aiofiles.open(self.path, encoding="utf-8", errors="replace") as f:
            content = await f.read()

        data = self._load_json_content(content)

        # JSON 구조를 평면화하여 문자열만 추출
        return self._flatten_json(data)

    async def dump(self, data: Mapping[str, str]) -> None:
        """번역된 데이터를 JSON 형식으로 저장합니다."""
        # 원본 JSON 구조를 복원
        async with aiofiles.open(self.path, encoding="utf-8", errors="replace") as f:
            original_content = await f.read()
        no_filter = False

        try:
            original_data = self._load_json_content(original_content)
        except:
            original_data = {}
            no_filter = True
        # 번역된 값으로 원본 구조 업데이트
        updated_data = self._unflatten_json(
            original_data,
            data,
            no_filter=no_filter,
        )

        # JSON 파일로 저장
        json_content = json.dumps(updated_data, ensure_ascii=False, indent=4)

        async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
            await f.write(json_content)

    def _load_json_content(self, content: str) -> Dict[str, Any]:
        """JSON 문자열을 파싱하여 Python 딕셔너리로 반환합니다."""
        try:
            # 탭을 공백으로 변환
            content = re.sub(r"\t", " ", content)
            return json.loads(content)
        except json.JSONDecodeError:
            # JSON 문법 오류 수정 시도
            try:
                logger.info("JSON 문법 오류 수정 시도")
                # 뒤에 오는 콤마 제거
                content = re.sub(r'("(?:\\?.)*?")|,\s*([]}])', r"\1\2", content)
                return json.loads(content)
            except json.JSONDecodeError:
                try:
                    # 주석 제거 후 재시도
                    cleaned_content = self.COMMENT_PATTERN.sub("", content)
                    return json.loads(cleaned_content)
                except json.JSONDecodeError as e:
                    raise ValueError(f"JSON 파싱 오류: {e}")

    def _flatten_json(self, data: Any, prefix: str = "") -> Dict[str, str]:
        """JSON 구조를 평면화하여 문자열 값들만 추출합니다."""
        result = {}

        if isinstance(data, dict):
            for key, value in data.items():
                new_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, str):
                    result[new_key] = value
                elif isinstance(value, (dict, list)):
                    result.update(self._flatten_json(value, new_key))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
                if isinstance(item, str):
                    result[new_key] = item
                elif isinstance(item, (dict, list)):
                    result.update(self._flatten_json(item, new_key))

        return result

    def _unflatten_json(
        self,
        original: Dict[str, Any],
        flat_data: Mapping[str, str],
        no_filter: bool = False,
    ) -> Dict[str, Any]:
        """평면화된 데이터를 원본 JSON 구조에 맞게 복원합니다."""
        original = json.loads(json.dumps(original))  # Deepcopy
        result = {} if isinstance(original, dict) else []
        self._update_nested_values(
            original, flat_data, result=result, no_filter=no_filter
        )
        return result

    def _update_nested_values(
        self,
        original: dict | list[dict],
        flat_data: Mapping[str, str],
        result: dict | list[dict],
        prefix: str = "",
        no_filter: bool = False,
    ) -> None:
        """재귀적으로 중첩된 구조의 값을 평면화된 데이터로 업데이트합니다."""
        if isinstance(original, dict):
            for key, value in list(original.items()):
                new_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, str):
                    if new_key in flat_data and not no_filter:
                        result[key] = flat_data[new_key]
                elif isinstance(value, (dict, list)):
                    self._update_nested_values(
                        value, flat_data, result, new_key, no_filter
                    )
        elif isinstance(original, list):
            for i, item in enumerate(original):
                new_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
                if isinstance(item, str):
                    if new_key in flat_data and not no_filter:
                        result[i] = flat_data[new_key]
                elif isinstance(item, (dict, list)):
                    self._update_nested_values(
                        item, flat_data, result, new_key, no_filter
                    )
