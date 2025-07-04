from __future__ import annotations

from typing import Mapping

import aiofiles

from .base import BaseParser


class JSParser(BaseParser):
    """JavaScript/TypeScript 파일 파서입니다.

    파일 전체 내용을 하나의 "content" 키로 보관하여
    안전하게 번역할 수 있도록 합니다.
    """

    file_extensions = (".js", ".ts")

    async def parse(self) -> Mapping[str, str]:
        self._check_extension()

        # 비동기 파일 읽기
        async with aiofiles.open(self.path, encoding="utf-8", errors="replace") as f:
            content = await f.read()

        return {"content": content}

    async def dump(self, data: Mapping[str, str]) -> None:
        """번역된 데이터를 JS 파일로 저장합니다."""
        # "content" 키가 있으면 해당 내용을 저장, 없으면 빈 문자열
        content = data.get("content", "")

        # 비동기 파일 저장
        async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
            await f.write(content)
