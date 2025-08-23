"""
리소스팩 생성 모듈

모드들의 번역 파일들을 마인크래프트 리소스팩 형태로 패키징합니다.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from ..parsers.base import BaseParser
from .base import BasePackager, PackagingResult

logger = logging.getLogger(__name__)


class ResourcePackBuilder(BasePackager):
    """모드 번역 파일들을 리소스팩으로 패키징하는 클래스"""

    def __init__(
        self,
        source_lang: str = "en_us",
        target_lang: str = "ko_kr",
        pack_format: int = 15,  # MC 1.20.1 기준
        pack_name: str = "Korean Translation Pack",
        pack_description: str = "Modpack Korean Translation",
    ):
        """
        Args:
            source_lang: 원본 언어 코드
            target_lang: 대상 언어 코드
            pack_format: 리소스팩 포맷 버전
            pack_name: 리소스팩 이름
            pack_description: 리소스팩 설명
        """
        super().__init__(source_lang, target_lang)
        self.pack_format = pack_format
        self.pack_name = pack_name
        self.pack_description = pack_description

    async def package(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> PackagingResult:
        """
        번역된 모드 파일들을 리소스팩으로 패키징합니다.

        Args:
            translated_files: 번역된 파일들 {원본경로: 번역된경로}
            output_dir: 출력 디렉토리
            **kwargs: 추가 옵션
                - modpack_name: 모드팩 이름 (기본값: "Unknown")

        Returns:
            PackagingResult: 패키징 결과
        """
        logger.info("리소스팩 생성 시작")
        result = PackagingResult(success=False)

        try:
            # 모드팩 이름 기반 디렉토리명 생성
            modpack_name = kwargs.get("modpack_name", "Unknown")
            lang_name = self._get_language_name(self.target_lang)
            resourcepack_dirname = f"{modpack_name}_{lang_name}_리소스팩"
            resourcepack_dir = output_dir / resourcepack_dirname
            self._ensure_directory(resourcepack_dir)

            # pack.mcmeta 생성
            await self._create_pack_mcmeta(resourcepack_dir)

            # 모드 파일들 분류 및 복사
            mod_files = self._filter_mod_files(translated_files)
            file_count = await self._copy_mod_files(mod_files, resourcepack_dir)

            create_zip = kwargs.get("create_zips", True)
            if create_zip:
                zip_path = self.create_zip_package(resourcepack_dir)
                if zip_path:
                    result.output_path = zip_path
                else:
                    # ZIP 생성 실패 시 디렉토리 경로로 대체
                    result.output_path = resourcepack_dir
                    result.errors.append("ZIP 파일 생성에 실패했습니다.")
            else:
                result.output_path = resourcepack_dir

            result.success = True
            result.file_count = file_count
            logger.info(
                f"리소스팩 생성 완료: {result.output_path} ({file_count}개 파일)"
            )

        except Exception as e:
            error_msg = f"리소스팩 생성 실패: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return result

    def _filter_mod_files(self, translated_files: Dict[str, str]) -> Dict[str, str]:
        """모드 관련 파일들만 필터링합니다."""
        mod_files = {}

        for original_path, translated_path in translated_files.items():
            # 모드 파일인지 확인 (JAR에서 추출된 파일들)
            if self._is_mod_file(original_path):
                mod_files[original_path] = translated_path

        logger.info(f"모드 파일 {len(mod_files)}개 발견")
        return mod_files

    def _is_mod_file(self, file_path: str) -> bool:
        """파일이 모드에서 추출된 파일인지 확인합니다."""
        path_lower = file_path.lower()

        # mods/extracted 경로에 있는 파일들
        if "mods/extracted" in path_lower or "mods\\extracted" in path_lower:
            return True

        # JAR 파일에서 추출된 assets 파일들
        if "assets" in path_lower and "lang" in path_lower:
            return True

        return False

    async def _create_pack_mcmeta(self, resourcepack_dir: Path) -> None:
        """pack.mcmeta 파일을 생성합니다."""
        pack_mcmeta = {
            "pack": {
                "description": self.pack_description,
                "pack_format": self.pack_format,
            }
        }

        mcmeta_path = resourcepack_dir / "pack.mcmeta"
        with open(mcmeta_path, "w", encoding="utf-8") as f:
            json.dump(pack_mcmeta, f, indent=2, ensure_ascii=False)

        logger.debug(f"pack.mcmeta 생성: {mcmeta_path}")

    async def _copy_mod_files(
        self, mod_files: Dict[str, str], resourcepack_dir: Path
    ) -> int:
        """모드 파일들을 리소스팩 구조로 복사합니다."""
        file_count = 0
        mod_assets = {}  # {mod_id: [파일들]}

        # 모드별로 파일들 그룹화
        for original_path, translated_path in mod_files.items():
            mod_id = self._extract_mod_id_from_path(original_path)
            if not mod_id:
                logger.warning(f"모드 ID 추출 실패: {original_path}")
                continue

            if mod_id not in mod_assets:
                mod_assets[mod_id] = []

            mod_assets[mod_id].append((original_path, translated_path))

        # 각 모드별로 assets 구조 생성
        for mod_id, file_list in mod_assets.items():
            logger.info(f"모드 '{mod_id}' 처리 중... ({len(file_list)}개 파일)")

            # 같은 모드 ID의 파일들을 합치기
            merged_content, file_extension, src_path = await self._merge_mod_files(
                file_list
            )
            if merged_content and await self._save_merged_mod_file(
                mod_id, merged_content, resourcepack_dir, file_extension, src_path
            ):
                file_count += 1

        logger.info(f"총 {len(mod_assets)}개 모드, {file_count}개 파일 처리 완료")
        return file_count

    async def _merge_mod_files(self, file_list: list) -> tuple[Optional[Dict], str]:
        """같은 모드 ID의 여러 파일들을 하나로 합칩니다."""
        merged_content = {}

        for original_path, translated_path in file_list:
            try:
                src_path = Path(translated_path)
                if not src_path.exists():
                    logger.warning(f"번역 파일이 존재하지 않음: {translated_path}")
                    continue

                # 파서를 사용하여 파일 읽기
                file_extension = src_path.suffix.lower()
                parser_class = BaseParser.get_parser_by_extension(file_extension)

                if not parser_class:
                    logger.warning(f"지원하지 않는 파일 형식: {file_extension}")
                    continue

                parser = parser_class(src_path)
                file_content = await parser.parse()

                # 내용 병합 (중복 키가 있으면 나중 파일이 우선)
                if isinstance(file_content, dict):
                    merged_content.update(file_content)
                    logger.debug(
                        f"파일 병합: {translated_path} ({len(file_content)}개 키)"
                    )
                else:
                    logger.warning(f"JSON 객체가 아닌 파일 건너뜀: {translated_path}")

            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 실패 ({translated_path}): {e}")
            except Exception as e:
                logger.error(f"파일 읽기 실패 ({translated_path}): {e}")

        if merged_content:
            logger.info(f"병합 완료: 총 {len(merged_content)}개 번역 키")
            return merged_content, file_extension, src_path
        else:
            logger.warning("병합할 유효한 내용이 없습니다")
            return None, None, None

    async def _save_merged_mod_file(
        self,
        mod_id: str,
        merged_content: Dict,
        resourcepack_dir: Path,
        file_extension: str,
        src_path: Path,
    ) -> bool:
        """병합된 모드 파일을 리소스팩 구조로 저장합니다."""
        try:
            assets_dir = resourcepack_dir / "assets" / mod_id / "lang"
            self._ensure_directory(assets_dir)
            # 언어 파일명 변환 (파서 확장자 기반)
            # .lang 파일의 경우 언어 코드 형식을 ko_KR, en_US 형태로 변환
            if file_extension == ".lang":
                lang_parts = self.target_lang.split("_")
                if len(lang_parts) == 2:
                    formatted_lang = f"{lang_parts[0]}_{lang_parts[1].upper()}"
                else:
                    formatted_lang = self.target_lang
                target_filename = f"{formatted_lang}{file_extension}"
            else:
                target_filename = f"{self.target_lang}{file_extension}"
            target_path = assets_dir / target_filename

            # 파서를 사용하여 병합된 내용을 파일로 저장
            parser_class = BaseParser.get_parser_by_extension(file_extension)
            if parser_class:
                # 파일이 존재하지 않을 경우 빈 파일 생성
                if not target_path.exists():
                    target_path.touch()

                parser = parser_class(target_path, original_path=src_path)
                await parser.dump(merged_content)

            logger.info(
                f"병합된 모드 파일 저장: {target_path} ({len(merged_content)}개 키)"
            )
            return True

        except Exception as e:
            logger.error(f"병합된 모드 파일 저장 실패 ({mod_id}): {e}")
            return False

    async def _copy_mod_file(
        self,
        original_path: str,
        translated_path: str,
        mod_id: str,
        resourcepack_dir: Path,
    ) -> bool:
        """개별 모드 파일을 리소스팩 구조로 복사합니다."""
        try:
            # 대상 경로 생성: assets/mod_id/lang/ko_kr.json
            assets_dir = resourcepack_dir / "assets" / mod_id / "lang"
            self._ensure_directory(assets_dir)

            # 언어 파일명 변환
            target_filename = f"{self.target_lang}.json"
            target_path = assets_dir / target_filename

            # 파일 복사
            src_path = Path(translated_path)
            if src_path.exists():
                return self._copy_file_with_conversion(src_path, target_path)
            else:
                logger.warning(f"번역 파일이 존재하지 않음: {translated_path}")
                return False

        except Exception as e:
            logger.error(f"모드 파일 복사 실패 ({original_path}): {e}")
            return False

    def create_zip_package(
        self, resourcepack_dir: Path, output_name: str = None
    ) -> Optional[Path]:
        """
        리소스팩 디렉토리를 ZIP 파일로 압축합니다.

        Args:
            resourcepack_dir: 리소스팩 디렉토리
            output_name: 출력 파일명 (기본값: 디렉토리명.zip)

        Returns:
            생성된 ZIP 파일 경로 또는 None
        """
        try:
            import zipfile

            if not output_name:
                output_name = f"{resourcepack_dir.name}.zip"

            zip_path = resourcepack_dir.parent / output_name

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in resourcepack_dir.rglob("*"):
                    if file_path.is_file():
                        # 상대 경로로 아카이브에 추가
                        arcname = file_path.relative_to(resourcepack_dir)
                        zipf.write(file_path, arcname)

            logger.info(f"리소스팩 ZIP 생성: {zip_path}")
            return zip_path

        except Exception as e:
            logger.error(f"리소스팩 ZIP 생성 실패: {e}")
            return None

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
