"""
패키징 기본 클래스들
"""

import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PackagingResult:
    """패키징 결과를 담는 데이터 클래스"""

    success: bool
    output_path: Optional[Path] = None
    file_count: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class BasePackager(ABC):
    """패키징 작업의 기본 클래스"""

    def __init__(self, source_lang: str = "en_us", target_lang: str = "ko_kr"):
        """
        Args:
            source_lang: 원본 언어 코드
            target_lang: 대상 언어 코드
        """
        self.source_lang = source_lang
        self.target_lang = target_lang

    @abstractmethod
    async def package(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> PackagingResult:
        """
        번역된 파일들을 패키징합니다.

        Args:
            translated_files: 번역된 파일들 {원본경로: 번역된경로}
            output_dir: 출력 디렉토리
            **kwargs: 추가 옵션들

        Returns:
            PackagingResult: 패키징 결과
        """
        pass

    def _convert_language_path(self, file_path: str) -> str:
        """
        파일 경로에서 언어 코드를 변환합니다.
        en_us.json → ko_kr.json
        lang/en_us.json → lang/ko_kr.json
        """
        path = Path(file_path)

        # 파일명이 언어 코드인 경우
        if path.stem == self.source_lang:
            return str(path.with_stem(self.target_lang))

        # 경로에 lang 폴더가 있는 경우
        parts = list(path.parts)
        for i, part in enumerate(parts):
            if part == f"{self.source_lang}.json":
                parts[i] = f"{self.target_lang}.json"
                break
            elif part == self.source_lang:
                parts[i] = self.target_lang
                break

        return str(Path(*parts))

    def _ensure_directory(self, path: Path) -> None:
        """디렉토리가 존재하지 않으면 생성합니다."""
        path.mkdir(parents=True, exist_ok=True)

    def _copy_file_with_conversion(self, src: Path, dst: Path) -> bool:
        """
        파일을 복사하면서 언어 코드를 변환합니다.

        Args:
            src: 원본 파일 경로
            dst: 대상 파일 경로 (언어 코드 변환됨)

        Returns:
            bool: 성공 여부
        """
        try:
            # 대상 디렉토리 생성
            self._ensure_directory(dst.parent)

            # 파일 복사
            shutil.copy2(src, dst)
            logger.debug(f"파일 복사: {src} → {dst}")
            return True

        except Exception as e:
            logger.error(f"파일 복사 실패 ({src} → {dst}): {e}")
            return False

    def _get_relative_path(
        self, file_path: str, base_paths: List[str]
    ) -> Optional[str]:
        """
        파일 경로에서 기준 경로들 중 하나를 제거하여 상대 경로를 반환합니다.

        Args:
            file_path: 전체 파일 경로
            base_paths: 제거할 기준 경로들

        Returns:
            상대 경로 또는 None
        """
        file_path = Path(file_path)

        for base_path in base_paths:
            try:
                # 경로를 정규화해서 비교
                base = Path(base_path).resolve()
                full = file_path.resolve()

                if str(full).startswith(str(base)):
                    return str(full.relative_to(base))

            except (ValueError, OSError):
                continue

        return None

    def _extract_mod_id_from_path(self, file_path: str) -> Optional[str]:
        """
        파일 경로에서 모드 ID를 추출합니다.

        Args:
            file_path: 파일 경로

        Returns:
            모드 ID 또는 None
        """
        path_parts = Path(file_path).parts

        # assets/modid/lang 패턴 찾기
        for i, part in enumerate(path_parts):
            if part == "assets" and i + 2 < len(path_parts):
                if path_parts[i + 2] == "lang":
                    return path_parts[i + 1]

        # JAR 파일명에서 모드 ID 추출 시도
        for part in path_parts:
            if part.endswith(".jar"):
                # 버전 정보 제거
                mod_name = part.replace(".jar", "")
                # 일반적인 버전 패턴 제거 (예: -1.20.1-1.0.0)
                import re

                mod_name = re.sub(r"-\d+\.\d+.*$", "", mod_name)
                return mod_name

        return None
