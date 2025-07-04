from __future__ import annotations

from typing import Mapping

import aiofiles

from .base import BaseParser


class TextParser(BaseParser):
    """Parse .txt files by splitting into chunks to handle large files efficiently.

    Splits content into chunks of maximum 2000 characters per line breaks
    to make translation more manageable.
    """

    file_extensions = (".txt",)

    async def parse(self) -> Mapping[str, str]:
        self._check_extension()

        # 비동기 파일 읽기
        async with aiofiles.open(self.path, encoding="utf-8", errors="replace") as f:
            content = await f.read()

        result = {}
        lines = content.splitlines()
        chunk_idx = 0
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line)

            # 청크가 비어있지 않고, 현재 줄을 추가하면 2000자를 초과할 경우 새 청크 시작
            if current_chunk and current_length + line_length > 2000:
                result[f"chunk_{chunk_idx}"] = "\n".join(current_chunk)
                chunk_idx += 1
                current_chunk = []
                current_length = 0

            current_chunk.append(line)
            current_length += line_length

        # 마지막 청크 저장
        if current_chunk:
            result[f"chunk_{chunk_idx}"] = "\n".join(current_chunk)

        return result

    async def dump(self, data: Mapping[str, str]) -> None:
        """Write chunks back to .txt format in proper order."""
        # chunk_0, chunk_1 같은 키를 순서대로 정렬
        sorted_keys = sorted(
            data.keys(),
            key=lambda k: int(k.split("_")[1])
            if k.startswith("chunk_") and k.split("_")[1].isdigit()
            else 999999,
        )

        # 이전 형식(line_X)과의 호환성 유지
        if not any(k.startswith("chunk_") for k in data.keys()) and any(
            k.startswith("line_") for k in data.keys()
        ):
            sorted_keys = sorted(
                data.keys(),
                key=lambda k: int(k.split("_")[1])
                if k.startswith("line_") and k.split("_")[1].isdigit()
                else 999999,
            )

        result = []
        for key in sorted_keys:
            result.append(str(data[key]))

        # 비동기 파일 저장
        async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
            await f.write("\n".join(result))
