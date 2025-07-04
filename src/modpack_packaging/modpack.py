"""
모드팩 패키징 모듈

Config, KubeJS 등의 파일들을 모드팩 형태로 패키징합니다.
"""

import logging
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from .base import BasePackager, PackagingResult

logger = logging.getLogger(__name__)


class ModpackPackager(BasePackager):
    """Config, KubeJS 등의 파일들을 모드팩 형태로 패키징하는 클래스"""

    def __init__(
        self,
        source_lang: str = "en_us",
        target_lang: str = "ko_kr",
        include_types: List[str] = None,
    ):
        """
        Args:
            source_lang: 원본 언어 코드
            target_lang: 대상 언어 코드
            include_types: 포함할 파일 타입들 (기본값: config, kubejs, patchouli)
        """
        super().__init__(source_lang, target_lang)
        self.include_types = include_types or ["config", "kubejs", "patchouli"]

    async def package(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> PackagingResult:
        """
        번역된 모드팩 파일들을 패키징합니다.

        Args:
            translated_files: 번역된 파일들 {원본경로: 번역된경로}
            output_dir: 출력 디렉토리
            **kwargs: 추가 옵션
                - create_zip: ZIP 파일 생성 여부 (기본값: True)
                - zip_name: ZIP 파일명 (기본값: {모드팩이름}_korean_덮어쓰기.zip)
                - modpack_name: 모드팩 이름 (기본값: "Unknown")

        Returns:
            PackagingResult: 패키징 결과
        """
        logger.info("모드팩 패키징 시작")
        result = PackagingResult(success=False)

        try:
            # 모드팩 이름 기반 디렉토리명 생성
            modpack_name = kwargs.get("modpack_name", "Unknown")
            lang_name = self._get_language_name(self.target_lang)
            modpack_dirname = f"{modpack_name}_{lang_name}_덮어쓰기"
            modpack_dir = output_dir / modpack_dirname
            self._ensure_directory(modpack_dir)

            # 모드팩 파일들 분류 및 복사
            modpack_files = self._filter_modpack_files(translated_files)
            file_count = await self._copy_modpack_files(modpack_files, modpack_dir)

            if file_count > 0:
                result.success = True
                result.output_path = modpack_dir
                result.file_count = file_count

                # ZIP 파일 생성 옵션
                create_zip = kwargs.get("create_zip", True)
                if create_zip:
                    default_zip_name = f"{modpack_name}_{lang_name}_덮어쓰기.zip"
                    zip_name = kwargs.get("zip_name", default_zip_name)
                    zip_path = self.create_zip_package(modpack_dir, zip_name)
                    if zip_path:
                        result.output_path = zip_path

                logger.info(
                    f"모드팩 패키징 완료: {result.output_path} ({file_count}개 파일)"
                )
            else:
                result.errors.append("패키징할 파일이 없습니다.")
                logger.warning("모드팩에 포함된 파일이 없습니다.")

        except Exception as e:
            error_msg = f"모드팩 패키징 실패: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return result

    def _filter_modpack_files(self, translated_files: Dict[str, str]) -> Dict[str, str]:
        """모드팩 관련 파일들만 필터링합니다."""
        modpack_files = {}

        for original_path, translated_path in translated_files.items():
            file_type = self._get_file_type(original_path)
            if file_type in self.include_types:
                modpack_files[original_path] = translated_path

        logger.info(f"모드팩 파일 {len(modpack_files)}개 발견")
        return modpack_files

    def _get_file_type(self, file_path: str) -> str:
        """파일 경로에서 파일 타입을 추출합니다."""
        path_lower = file_path.lower()
        path_parts = Path(file_path).parts

        # 경로에서 타입 확인
        for part in path_parts:
            part_lower = part.lower()
            if part_lower in ["config", "kubejs", "patchouli", "patchouli_books"]:
                return part_lower.replace("patchouli_books", "patchouli")

        # 더 구체적인 패턴 확인
        if "config" in path_lower:
            return "config"
        elif "kubejs" in path_lower:
            return "kubejs"
        elif "patchouli" in path_lower:
            return "patchouli"

        return "unknown"

    async def _copy_modpack_files(
        self, modpack_files: Dict[str, str], modpack_dir: Path
    ) -> int:
        """모드팩 파일들을 복사합니다."""
        file_count = 0
        file_types = {}  # {파일타입: 개수}

        for original_path, translated_path in modpack_files.items():
            if await self._copy_modpack_file(
                original_path, translated_path, modpack_dir
            ):
                file_count += 1

                # 통계 수집
                file_type = self._get_file_type(original_path)
                file_types[file_type] = file_types.get(file_type, 0) + 1

        # 통계 로깅
        for file_type, count in file_types.items():
            logger.info(f"{file_type}: {count}개 파일")

        logger.info(f"총 {file_count}개 파일 복사 완료")
        return file_count

    async def _copy_modpack_file(
        self, original_path: str, translated_path: str, modpack_dir: Path
    ) -> bool:
        """개별 모드팩 파일을 복사합니다."""
        try:
            # 원본 파일의 상대 경로 추출
            relative_path = self._extract_relative_path(original_path)
            if not relative_path:
                logger.warning(f"상대 경로 추출 실패: {original_path}")
                return False

            # 언어 코드 변환
            converted_path = self._convert_language_path(relative_path)
            target_path = modpack_dir / converted_path

            # 파일 복사
            src_path = Path(translated_path)
            if src_path.exists():
                return self._copy_file_with_conversion(src_path, target_path)
            else:
                logger.warning(f"번역 파일이 존재하지 않음: {translated_path}")
                return False

        except Exception as e:
            logger.error(f"모드팩 파일 복사 실패 ({original_path}): {e}")
            return False

    def _extract_relative_path(self, file_path: str) -> Optional[str]:
        """파일 경로에서 모드팩 기준 상대 경로를 추출합니다."""
        path = Path(file_path)
        path_parts = list(path.parts)

        # 기준 폴더들 찾기
        base_folders = ["config", "kubejs", "patchouli_books", "patchouli"]

        for i, part in enumerate(path_parts):
            if part.lower() in [f.lower() for f in base_folders]:
                # 기준 폴더부터의 상대 경로 반환
                relative_parts = path_parts[i:]
                return str(Path(*relative_parts))

        # 모드팩 루트에서 상대 경로 추출 시도
        modpack_indicators = ["instances", "modpacks", "minecraft"]
        for i, part in enumerate(path_parts):
            if part.lower() in modpack_indicators:
                # 다음 폴더부터 찾기
                remaining_parts = path_parts[i + 1 :]
                for j, remaining_part in enumerate(remaining_parts):
                    if remaining_part.lower() in [f.lower() for f in base_folders]:
                        relative_parts = remaining_parts[j:]
                        return str(Path(*relative_parts))

        # 마지막으로 파일명만 사용
        return path.name

    def create_zip_package(
        self, modpack_dir: Path, output_name: str = None
    ) -> Optional[Path]:
        """
        모드팩 디렉토리를 ZIP 파일로 압축합니다.

        Args:
            modpack_dir: 모드팩 디렉토리
            output_name: 출력 파일명 (기본값: 디렉토리명.zip)

        Returns:
            생성된 ZIP 파일 경로 또는 None
        """
        try:
            if not output_name:
                output_name = f"{modpack_dir.name}.zip"

            zip_path = modpack_dir.parent / output_name

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in modpack_dir.rglob("*"):
                    if file_path.is_file():
                        # 상대 경로로 아카이브에 추가
                        arcname = file_path.relative_to(modpack_dir)
                        zipf.write(file_path, arcname)

            logger.info(f"모드팩 ZIP 생성: {zip_path}")
            return zip_path

        except Exception as e:
            logger.error(f"모드팩 ZIP 생성 실패: {e}")
            return None

    def get_supported_types(self) -> List[str]:
        """지원하는 파일 타입 목록을 반환합니다."""
        return self.include_types.copy()

    def add_file_type(self, file_type: str) -> None:
        """지원 파일 타입을 추가합니다."""
        if file_type not in self.include_types:
            self.include_types.append(file_type)
            logger.info(f"파일 타입 추가: {file_type}")

    def remove_file_type(self, file_type: str) -> None:
        """지원 파일 타입을 제거합니다."""
        if file_type in self.include_types:
            self.include_types.remove(file_type)
            logger.info(f"파일 타입 제거: {file_type}")

    def _get_language_name(self, lang_code: str) -> str:
        """언어 코드를 사람이 읽기 좋은 이름으로 변환합니다."""
        lang_mapping = {
            "ko_kr": "korean",
            "ja_jp": "japanese",
            "zh_cn": "chinese_simplified",
            "zh_tw": "chinese_traditional",
            "fr_fr": "french",
            "de_de": "german",
            "es_es": "spanish",
            "pt_br": "portuguese",
            "ru_ru": "russian",
            "it_it": "italian",
        }
        return lang_mapping.get(lang_code.lower(), lang_code.lower())
