from __future__ import annotations

import gzip
import struct
from typing import Any, Dict, Mapping

import aiofiles

from .base import BaseParser


class NBTParser(BaseParser):
    """NBT 형식 파일을 처리하는 파서입니다.

    바이너리 NBT 파일을 파싱하고 문자열 값들을 추출합니다.
    """

    file_extensions = (".nbt", ".dat")

    async def parse(self) -> Mapping[str, str]:
        self._check_extension()

        # 비동기 파일 읽기 (바이너리 모드)
        async with aiofiles.open(self.path, "rb") as f:
            content = await f.read()

        try:
            # NBT 파싱 (압축 해제 시도)
            try:
                # GZip 압축 해제 시도
                decompressed = gzip.decompress(content)
                data = self._parse_nbt(decompressed)
            except (gzip.BadGzipFile, OSError):
                # 압축되지 않은 NBT 파일 처리
                data = self._parse_nbt(content)

            return self._flatten_nbt(data)
        except Exception:
            # NBT 파싱 실패 시 빈 딕셔너리 반환
            return {}

    async def dump(self, data: Mapping[str, str]) -> None:
        """번역된 데이터를 NBT 형식으로 저장합니다."""
        # 원본 NBT 구조를 복원
        async with aiofiles.open(
            self.original_path if self.original_path else self.path, "rb"
        ) as f:
            original_content = await f.read()

        try:
            # 압축 해제 시도
            try:
                decompressed = gzip.decompress(original_content)
                original_data = self._parse_nbt(decompressed)
                was_compressed = True
            except (gzip.BadGzipFile, OSError):
                original_data = self._parse_nbt(original_content)
                was_compressed = False
        except Exception:
            return

        # 번역된 값으로 원본 구조 업데이트
        updated_data = self._unflatten_nbt(original_data, flat_data=data)

        # NBT 바이너리로 변환
        nbt_content = self._serialize_nbt(updated_data)

        # 원본이 압축되어 있었다면 압축하여 저장
        if was_compressed:
            nbt_content = gzip.compress(nbt_content)

        # 비동기 파일 저장 (바이너리 모드)
        async with aiofiles.open(self.path, "wb") as f:
            await f.write(nbt_content)

    def _parse_nbt(self, data: bytes) -> Dict[str, Any]:
        """NBT 바이너리 데이터를 파싱합니다."""
        if not data:
            return {}

        try:
            # NBT 파일은 일반적으로 TAG_Compound로 시작
            offset = 0
            tag_type = data[offset]
            offset += 1

            if tag_type != 10:  # TAG_Compound
                return {}

            # 루트 태그 이름 읽기
            name_length = struct.unpack(">H", data[offset : offset + 2])[0]
            offset += 2
            root_name = data[offset : offset + name_length].decode(
                "utf-8", errors="replace"
            )
            offset += name_length

            # 컴파운드 데이터 파싱
            compound_data, _ = self._parse_compound(data, offset)
            return {root_name: compound_data}

        except Exception:
            return {}

    def _parse_compound(self, data: bytes, offset: int) -> tuple[Dict[str, Any], int]:
        """TAG_Compound를 파싱합니다."""
        result = {}

        while offset < len(data):
            # 태그 타입 읽기
            tag_type = data[offset]
            offset += 1

            if tag_type == 0:  # TAG_End
                break

            # 태그 이름 읽기
            name_length = struct.unpack(">H", data[offset : offset + 2])[0]
            offset += 2
            tag_name = data[offset : offset + name_length].decode(
                "utf-8", errors="replace"
            )
            offset += name_length

            # 태그 값 파싱
            value, offset = self._parse_tag(data, offset, tag_type)
            result[tag_name] = value

        return result, offset

    def _parse_tag(self, data: bytes, offset: int, tag_type: int) -> tuple[Any, int]:
        """태그 타입에 따라 값을 파싱합니다."""
        if tag_type == 1:  # TAG_Byte
            return struct.unpack(">b", data[offset : offset + 1])[0], offset + 1
        elif tag_type == 2:  # TAG_Short
            return struct.unpack(">h", data[offset : offset + 2])[0], offset + 2
        elif tag_type == 3:  # TAG_Int
            return struct.unpack(">i", data[offset : offset + 4])[0], offset + 4
        elif tag_type == 4:  # TAG_Long
            return struct.unpack(">q", data[offset : offset + 8])[0], offset + 8
        elif tag_type == 5:  # TAG_Float
            return struct.unpack(">f", data[offset : offset + 4])[0], offset + 4
        elif tag_type == 6:  # TAG_Double
            return struct.unpack(">d", data[offset : offset + 8])[0], offset + 8
        elif tag_type == 7:  # TAG_Byte_Array
            length = struct.unpack(">i", data[offset : offset + 4])[0]
            offset += 4
            return list(data[offset : offset + length]), offset + length
        elif tag_type == 8:  # TAG_String
            length = struct.unpack(">H", data[offset : offset + 2])[0]
            offset += 2
            return data[offset : offset + length].decode(
                "utf-8", errors="replace"
            ), offset + length
        elif tag_type == 9:  # TAG_List
            list_type = data[offset]
            offset += 1
            length = struct.unpack(">i", data[offset : offset + 4])[0]
            offset += 4
            result = []
            for _ in range(length):
                value, offset = self._parse_tag(data, offset, list_type)
                result.append(value)
            return result, offset
        elif tag_type == 10:  # TAG_Compound
            return self._parse_compound(data, offset)
        elif tag_type == 11:  # TAG_Int_Array
            length = struct.unpack(">i", data[offset : offset + 4])[0]
            offset += 4
            result = []
            for _ in range(length):
                value = struct.unpack(">i", data[offset : offset + 4])[0]
                result.append(value)
                offset += 4
            return result, offset
        elif tag_type == 12:  # TAG_Long_Array
            length = struct.unpack(">i", data[offset : offset + 4])[0]
            offset += 4
            result = []
            for _ in range(length):
                value = struct.unpack(">q", data[offset : offset + 8])[0]
                result.append(value)
                offset += 8
            return result, offset
        else:
            # 알 수 없는 태그 타입
            return None, offset

    def _flatten_nbt(self, data: Any, prefix: str = "") -> Dict[str, str]:
        """NBT 구조를 평면화하여 문자열 값들만 추출합니다."""
        result = {}

        if isinstance(data, dict):
            for key, value in data.items():
                new_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, str):
                    result[new_key] = value
                elif isinstance(value, (dict, list)):
                    result.update(self._flatten_nbt(value, new_key))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
                if isinstance(item, str):
                    result[new_key] = item
                elif isinstance(item, (dict, list)):
                    result.update(self._flatten_nbt(item, new_key))

        return result

    def _unflatten_nbt(self, original: Any, flat_data: Mapping[str, str]) -> Any:
        """평면화된 데이터를 원본 NBT 구조에 맞게 복원합니다."""
        return self._update_structure_recursive(original, flat_data, "")

    def _update_structure_recursive(
        self, obj: Any, flat_data: Mapping[str, str], prefix: str
    ) -> Any:
        """재귀적으로 구조를 순회하면서 번역된 값으로 교체합니다."""
        if isinstance(obj, dict):
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

    def _serialize_nbt(self, data: Dict[str, Any]) -> bytes:
        """NBT 데이터를 바이너리로 직렬화합니다."""
        result = b""

        # 루트 태그는 일반적으로 TAG_Compound
        for root_name, root_data in data.items():
            result += struct.pack("B", 10)  # TAG_Compound
            result += struct.pack(">H", len(root_name.encode("utf-8")))
            result += root_name.encode("utf-8")
            result += self._serialize_compound(root_data)
            break  # 첫 번째 루트만 처리

        return result

    def _serialize_compound(self, data: Dict[str, Any]) -> bytes:
        """TAG_Compound를 직렬화합니다."""
        result = b""

        for key, value in data.items():
            tag_type = self._get_tag_type(value)
            result += struct.pack("B", tag_type)
            result += struct.pack(">H", len(key.encode("utf-8")))
            result += key.encode("utf-8")
            result += self._serialize_value(value, tag_type)

        result += struct.pack("B", 0)  # TAG_End
        return result

    def _get_tag_type(self, value: Any) -> int:
        """값의 타입에 따라 NBT 태그 타입을 반환합니다."""
        if isinstance(value, bool):
            return 1  # TAG_Byte
        elif isinstance(value, int):
            if -128 <= value <= 127:
                return 1  # TAG_Byte
            elif -32768 <= value <= 32767:
                return 2  # TAG_Short
            elif -2147483648 <= value <= 2147483647:
                return 3  # TAG_Int
            else:
                return 4  # TAG_Long
        elif isinstance(value, float):
            return 6  # TAG_Double
        elif isinstance(value, str):
            return 8  # TAG_String
        elif isinstance(value, list):
            return 9  # TAG_List
        elif isinstance(value, dict):
            return 10  # TAG_Compound
        else:
            return 8  # 기본적으로 문자열로 처리

    def _serialize_value(self, value: Any, tag_type: int) -> bytes:
        """값을 NBT 바이너리 형식으로 직렬화합니다."""
        if tag_type == 1:  # TAG_Byte
            byte_value = int(value) if isinstance(value, bool) else value
            # byte 타입은 -128 ~ 127 범위여야 함
            if byte_value < -128 or byte_value > 127:
                # 범위를 벗어나면 값을 클램핑
                byte_value = max(-128, min(127, byte_value))
            return struct.pack(">b", byte_value)
        elif tag_type == 2:  # TAG_Short
            return struct.pack(">h", value)
        elif tag_type == 3:  # TAG_Int
            return struct.pack(">i", value)
        elif tag_type == 4:  # TAG_Long
            return struct.pack(">q", value)
        elif tag_type == 5:  # TAG_Float
            return struct.pack(">f", value)
        elif tag_type == 6:  # TAG_Double
            return struct.pack(">d", value)
        elif tag_type == 8:  # TAG_String
            encoded = str(value).encode("utf-8")
            return struct.pack(">H", len(encoded)) + encoded
        elif tag_type == 9:  # TAG_List
            if not value:
                return struct.pack("B", 0) + struct.pack(">i", 0)  # 빈 리스트

            list_type = self._get_tag_type(value[0])
            result = struct.pack("B", list_type)
            result += struct.pack(">i", len(value))
            for item in value:
                result += self._serialize_value(item, list_type)
            return result
        elif tag_type == 10:  # TAG_Compound
            return self._serialize_compound(value)
        else:
            # 기본적으로 문자열로 처리
            encoded = str(value).encode("utf-8")
            return struct.pack(">H", len(encoded)) + encoded
