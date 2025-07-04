from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from typing import Any, Dict, Mapping

import aiofiles

from .base import BaseParser


class XMLParser(BaseParser):
    """XML 형식 파일을 처리하는 파서입니다.

    XML 구조를 평면화하여 번역 가능한 텍스트 노드들을 추출합니다.
    """

    file_extensions = (".xml",)

    async def parse(self) -> Mapping[str, str]:
        """XML 파일을 파싱하여 번역 가능한 텍스트들을 추출합니다."""
        self._check_extension()

        # 비동기 파일 읽기
        async with aiofiles.open(self.path, encoding="utf-8", errors="replace") as f:
            content = await f.read()

        data = self._load_xml_content(content)

        # XML 구조를 평면화하여 텍스트만 추출
        return self._flatten_xml(data)

    async def dump(self, data: Mapping[str, str]) -> None:
        """번역된 데이터를 XML 형식으로 저장합니다."""
        # 원본 XML 구조를 복원
        async with aiofiles.open(self.path, encoding="utf-8", errors="replace") as f:
            original_content = await f.read()

        original_data = self._load_xml_content(original_content)

        # 번역된 값으로 원본 구조 업데이트
        updated_data = self._unflatten_xml(original_data, data)

        # XML 파일로 저장
        xml_content = self._save_xml_content(updated_data)

        async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
            await f.write(xml_content)

    def _load_xml_content(self, content: str) -> Dict[str, Any]:
        """XML 문자열을 파싱하여 Python 딕셔너리로 반환합니다."""
        try:
            root = ET.fromstring(content)
            result = self._element_to_dict(root)
            # 최상위 태그를 결과의 키로 사용
            return {root.tag: result}
        except Exception as e:
            raise ValueError(f"XML 파싱 오류: {e}")

    def _save_xml_content(self, data: Dict[str, Any]) -> str:
        """Python 딕셔너리를 XML 문자열로 변환합니다."""
        if len(data) != 1:
            raise ValueError("XML 데이터는 단일 루트 요소를 가져야 합니다")

        root_tag = next(iter(data))
        root_data = data[root_tag]

        root = self._dict_to_element(root_data, root_tag)

        # XML 선언 추가 및 문자열로 변환
        tree = ET.ElementTree(root)
        output = io.BytesIO()
        tree.write(output, encoding="UTF-8", xml_declaration=True)

        return output.getvalue().decode("UTF-8")

    def _element_to_dict(self, element) -> Dict[str, Any]:
        """XML 요소를 사전으로 변환하는 재귀 함수"""
        result = {}

        # 속성 처리
        if element.attrib:
            result["@attributes"] = dict(element.attrib)

        # 텍스트 노드 처리
        if element.text and element.text.strip():
            result["#text"] = element.text.strip()

        # 자식 요소 처리
        children = {}
        for child in element:
            child_dict = self._element_to_dict(child)

            # 같은 태그 이름을 가진 자식 요소를 리스트로 처리
            if child.tag in children:
                if isinstance(children[child.tag], list):
                    children[child.tag].append(child_dict)
                else:
                    children[child.tag] = [children[child.tag], child_dict]
            else:
                children[child.tag] = child_dict

        if children:
            result.update(children)

        # 특별한 텍스트만 있는 요소는 단순화
        if len(result) == 1 and "#text" in result:
            return result["#text"]

        return result

    def _dict_to_element(self, data: Any, tag: str = "root") -> ET.Element:
        """사전을 XML 요소로 변환하는 재귀 함수"""
        if isinstance(data, str):
            element = ET.Element(tag)
            element.text = data
            return element

        element = ET.Element(tag)

        # 속성 처리
        if isinstance(data, dict) and "@attributes" in data:
            for key, value in data["@attributes"].items():
                element.set(key, str(value))
            data_without_attrs = {k: v for k, v in data.items() if k != "@attributes"}
        else:
            data_without_attrs = data if isinstance(data, dict) else {}

        # 텍스트 노드 처리
        if "#text" in data_without_attrs:
            element.text = data_without_attrs["#text"]
            data_without_attrs = {
                k: v for k, v in data_without_attrs.items() if k != "#text"
            }

        # 자식 요소 처리
        for key, value in data_without_attrs.items():
            if isinstance(value, list):
                # 같은 태그의 여러 요소
                for item in value:
                    element.append(self._dict_to_element(item, key))
            else:
                # 단일 요소
                element.append(self._dict_to_element(value, key))

        return element

    def _flatten_xml(self, data: Any, prefix: str = "") -> Dict[str, str]:
        """XML 구조를 평면화하여 텍스트 값들만 추출합니다."""
        result = {}

        if isinstance(data, dict):
            for key, value in data.items():
                if key in ("@attributes",):
                    continue  # 속성은 번역하지 않음

                new_key = f"{prefix}.{key}" if prefix else key

                if key == "#text" and isinstance(value, str):
                    # 텍스트 노드
                    result[prefix if prefix else "text"] = value
                elif isinstance(value, str):
                    result[new_key] = value
                elif isinstance(value, (dict, list)):
                    result.update(self._flatten_xml(value, new_key))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
                if isinstance(item, str):
                    result[new_key] = item
                elif isinstance(item, (dict, list)):
                    result.update(self._flatten_xml(item, new_key))

        return result

    def _unflatten_xml(
        self, original: Dict[str, Any], flat_data: Mapping[str, str]
    ) -> Dict[str, Any]:
        """평면화된 데이터를 원본 XML 구조에 맞게 복원합니다."""
        result = original.copy()

        for flat_key, value in flat_data.items():
            self._set_nested_xml_value(result, flat_key, value)

        return result

    def _set_nested_xml_value(self, data: Dict[str, Any], key: str, value: str) -> None:
        """중첩된 XML 구조에서 특정 키의 값을 설정합니다."""
        if key == "text":
            # 루트 텍스트 노드
            data["#text"] = value
            return

        parts = []
        current_part = ""
        bracket_count = 0

        # 키를 파싱
        for char in key:
            if char == "." and bracket_count == 0:
                if current_part:
                    parts.append(current_part)
                    current_part = ""
            elif char == "[":
                if current_part:
                    parts.append(current_part)
                    current_part = "["
                else:
                    current_part += char
                bracket_count += 1
            elif char == "]":
                current_part += char
                bracket_count -= 1
                if bracket_count == 0:
                    parts.append(current_part)
                    current_part = ""
            else:
                current_part += char

        if current_part:
            parts.append(current_part)

        # 중첩된 구조에서 값 설정
        current = data
        for i, part in enumerate(parts[:-1]):
            if part.startswith("[") and part.endswith("]"):
                # 배열 인덱스 처리
                index = int(part[1:-1])
                if isinstance(current, list) and len(current) > index:
                    current = current[index]
            else:
                # 객체 키 처리
                if isinstance(current, dict) and part in current:
                    current = current[part]

        # 마지막 키에 값 설정
        if parts:
            last_part = parts[-1]
            if last_part.startswith("[") and last_part.endswith("]"):
                index = int(last_part[1:-1])
                if isinstance(current, list) and len(current) > index:
                    if isinstance(current[index], dict) and "#text" in current[index]:
                        current[index]["#text"] = value
                    else:
                        current[index] = value
            else:
                if isinstance(current, dict):
                    if last_part == "#text" or (
                        isinstance(current.get(last_part), dict)
                        and "#text" in current[last_part]
                    ):
                        if last_part in current and isinstance(
                            current[last_part], dict
                        ):
                            current[last_part]["#text"] = value
                        else:
                            current[last_part] = value
                    else:
                        current[last_part] = value
