from __future__ import annotations

import re
from typing import Any, Dict, Mapping

import aiofiles
import ftb_snbt_lib as slib

from .base import BaseParser


class SNBTParser(BaseParser):
    """SNBT 형식 파일을 처리하는 파서입니다.

    ftb_snbt_lib 라이브러리를 사용하여 SNBT 파일을 파싱하고,
    마인크래프트 컬러 코드를 적절히 처리합니다.
    """

    file_extensions = (".snbt",)

    async def parse(self) -> Mapping[str, str]:
        self._check_extension()

        # 비동기 파일 읽기
        async with aiofiles.open(self.path, encoding="utf-8", errors="replace") as f:
            content = await f.read()

        try:
            # ftb_snbt_lib를 사용한 파싱 시도
            data = slib.loads(content)
            return self._flatten_snbt(data)
        except ImportError:
            # ftb_snbt_lib가 없는 경우 대체 파싱 방법 사용
            return self._parse_snbt_fallback(content)

    async def dump(self, data: Mapping[str, str]) -> None:
        """번역된 데이터를 SNBT 형식으로 저장합니다."""
        try:
            # 원본 SNBT 구조를 복원
            async with aiofiles.open(
                self.path, encoding="utf-8", errors="replace"
            ) as f:
                original_content = await f.read()

            original_data = slib.loads(original_content)

            # 번역된 값으로 원본 구조 업데이트
            updated_data = self._unflatten_snbt(original_data, data)

            # & 문자 치환 적용
            processed_data = self._replace_ampersand(updated_data)

            # Python 데이터를 SNBT 타입으로 변환
            snbt_data = self._convert_to_snbt_type(processed_data)

            # SNBT 문자열로 저장
            snbt_content = slib.dumps(snbt_data)

            # 비동기 파일 저장
            async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
                await f.write(snbt_content)

        except ImportError:
            raise NotImplementedError(
                "SNBT 덤프 기능을 사용하려면 ftb_snbt_lib 라이브러리가 필요합니다"
            )

    def _parse_snbt_fallback(self, content: str) -> Dict[str, str]:
        """ftb_snbt_lib 없이 기본적인 SNBT 문자열 추출"""
        mapping: dict[str, str] = {}

        # 문자열 리터럴 추출
        string_re = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
        for idx, match in enumerate(string_re.finditer(content), start=1):
            mapping[str(idx)] = match.group(1)

        return mapping

    def _flatten_snbt(self, data: Any, prefix: str = "") -> Dict[str, str]:
        """SNBT 구조를 평면화하여 문자열 값들만 추출합니다."""
        result = {}

        if isinstance(data, dict):
            for key, value in data.items():
                new_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, str):
                    result[new_key] = value
                elif isinstance(value, (dict, list)):
                    result.update(self._flatten_snbt(value, new_key))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
                if isinstance(item, str):
                    result[new_key] = item
                elif isinstance(item, (dict, list)):
                    result.update(self._flatten_snbt(item, new_key))

        return result

    def _unflatten_snbt(self, original: Any, flat_data: Mapping[str, str]) -> Any:
        """평면화된 데이터를 원본 SNBT 구조에 맞게 복원합니다."""
        # 재귀적으로 원본 구조를 순회하면서 번역된 값으로 교체
        return self._update_structure_recursive(original, flat_data, "")

    def _update_structure_recursive(
        self, obj: Any, flat_data: Mapping[str, str], prefix: str
    ) -> Any:
        """재귀적으로 구조를 순회하면서 번역된 값으로 교체합니다."""
        # ftb_snbt_lib 객체 타입 체크
        try:
            from ftb_snbt_lib.tag import Compound, String
            from ftb_snbt_lib.tag import List as SNBTList

            # SNBT Compound 객체 처리
            if isinstance(obj, Compound):
                result_dict = {}
                for key, value in obj.items():
                    new_key = f"{prefix}.{key}" if prefix else key

                    # SNBT String 객체이고 번역이 있는 경우
                    if isinstance(value, String) and new_key in flat_data:
                        result_dict[key] = String(flat_data[new_key])
                    # 일반 문자열이고 번역이 있는 경우
                    elif isinstance(value, str) and new_key in flat_data:
                        result_dict[key] = flat_data[new_key]
                    # 중첩된 구조인 경우 재귀 호출
                    elif isinstance(value, (Compound, SNBTList, dict, list)):
                        result_dict[key] = self._update_structure_recursive(
                            value, flat_data, new_key
                        )
                    else:
                        # 그외의 경우 원본 값 유지
                        result_dict[key] = value
                return Compound(result_dict)

            # SNBT List 객체 처리
            elif isinstance(obj, SNBTList):
                result_list = []
                for i, item in enumerate(obj):
                    new_key = f"{prefix}[{i}]" if prefix else f"[{i}]"

                    # SNBT String 객체이고 번역이 있는 경우
                    if isinstance(item, String) and new_key in flat_data:
                        result_list.append(String(flat_data[new_key]))
                    # 일반 문자열이고 번역이 있는 경우
                    elif isinstance(item, str) and new_key in flat_data:
                        result_list.append(flat_data[new_key])
                    # 중첩된 구조인 경우 재귀 호출
                    elif isinstance(item, (Compound, SNBTList, dict, list)):
                        result_list.append(
                            self._update_structure_recursive(item, flat_data, new_key)
                        )
                    else:
                        # 그외의 경우 원본 값 유지
                        result_list.append(item)
                return SNBTList(result_list)

            # SNBT String 객체 처리
            elif isinstance(obj, String) and prefix in flat_data:
                return String(flat_data[prefix])

        except ImportError:
            # ftb_snbt_lib가 없는 경우 일반 처리
            pass

        # 일반 Python 객체 처리
        if isinstance(obj, dict):
            # 딕셔너리의 경우 각 키-값 쌍을 처리
            result = {}
            for key, value in obj.items():
                new_key = f"{prefix}.{key}" if prefix else key

                if isinstance(value, str) and new_key in flat_data:
                    # 문자열 값이고 번역이 있는 경우 교체
                    result[key] = flat_data[new_key]
                elif isinstance(value, (dict, list)):
                    # 중첩된 구조인 경우 재귀 호출
                    result[key] = self._update_structure_recursive(
                        value, flat_data, new_key
                    )
                else:
                    # 그외의 경우 원본 값 유지
                    result[key] = value
            return result

        elif isinstance(obj, list):
            # 리스트의 경우 각 항목을 처리
            result = []
            for i, item in enumerate(obj):
                new_key = f"{prefix}[{i}]" if prefix else f"[{i}]"

                if isinstance(item, str) and new_key in flat_data:
                    # 문자열 값이고 번역이 있는 경우 교체
                    result.append(flat_data[new_key])
                elif isinstance(item, (dict, list)):
                    # 중첩된 구조인 경우 재귀 호출
                    result.append(
                        self._update_structure_recursive(item, flat_data, new_key)
                    )
                else:
                    # 그외의 경우 원본 값 유지
                    result.append(item)
            return result

        else:
            # 문자열이나 다른 기본 타입인 경우
            if isinstance(obj, str) and prefix in flat_data:
                return flat_data[prefix]
            return obj

    @staticmethod
    def _replace_ampersand(obj: Any) -> Any:
        """객체 내의 & 문자를 이스케이프 처리합니다 (마인크래프트 컬러 코드 제외)."""
        if isinstance(obj, str):
            # 마크 컬러코드 형식(&0~&9, &a~&f, &k~&o, &r)은 치환하지 않고 유지
            pattern = r"&(?![0-9a-fk-or])"
            return re.sub(pattern, r"\\&", re.sub(r"\n", r"\\n", obj))
        elif isinstance(obj, dict):
            return {k: SNBTParser._replace_ampersand(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [SNBTParser._replace_ampersand(item) for item in obj]
        else:
            return obj

    @staticmethod
    def _convert_to_snbt_type(value: Any) -> Any:
        """Python 값을 해당하는 SNBT 데이터 타입으로 변환합니다."""
        try:
            from ftb_snbt_lib.tag import Bool, Compound, Double, Integer, Long, String
            from ftb_snbt_lib.tag import List as SNBTList

            if isinstance(value, bool):
                return Bool(value)
            elif isinstance(value, int):
                if -2147483648 <= value <= 2147483647:
                    return Integer(value)
                else:
                    return Long(value)
            elif isinstance(value, float):
                return Double(value)
            elif isinstance(value, str):
                return String(value)
            elif isinstance(value, list):
                converted_items = [
                    SNBTParser._convert_to_snbt_type(item) for item in value
                ]
                return SNBTList(converted_items)
            elif isinstance(value, dict):
                snbt_dict = {}
                for k, v in value.items():
                    if not isinstance(k, str):
                        k = str(k)
                    snbt_dict[k] = SNBTParser._convert_to_snbt_type(v)
                return Compound(snbt_dict)
            else:
                return String(str(value))
        except ImportError:
            return value
