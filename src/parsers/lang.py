from __future__ import annotations

import json
from typing import Mapping

import aiofiles

from .base import BaseParser


class LangParser(BaseParser):
    """Parse Minecraft 1.12- style *.lang* files (key=value per line).

    Handles JSON escape sequences for special characters properly.
    """

    file_extensions = (".lang",)

    async def parse(self) -> Mapping[str, str]:
        self._check_extension()
        mapping: dict[str, str] = {}

        # 비동기 파일 읽기
        async with aiofiles.open(self.path, encoding="utf-8", errors="replace") as f:
            text = await f.read()

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # JSON 이스케이프 처리를 통해 특수 문자 처리
            try:
                parsed_value = json.loads(f'"{value}"')
            except json.JSONDecodeError:
                parsed_value = value

            mapping[key] = parsed_value

        return mapping

    async def dump(self, data: Mapping[str, str]) -> None:
        """Write mapping back to *.lang* format, sorted by key with proper escaping."""
        lines = []
        for key, value in sorted(data.items()):
            # JSON 이스케이프 처리를 통해 특수 문자 처리
            if isinstance(value, str):
                escaped_value = json.dumps(value, ensure_ascii=False)[
                    1:-1
                ]  # 따옴표 제거
            else:
                escaped_value = str(value)
            lines.append(f"{key}={escaped_value}")

        # 비동기 파일 저장
        async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
            await f.write("\n".join(lines))
