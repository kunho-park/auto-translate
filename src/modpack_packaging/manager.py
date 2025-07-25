"""
패키징 관리자 모듈

전체 패키징 작업을 관리하고 조정합니다.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict

from .base import PackagingResult
from .modpack import ModpackPackager
from .resourcepack import ResourcePackBuilder

logger = logging.getLogger(__name__)


class PackageManager:
    """전체 패키징 작업을 관리하는 클래스"""

    def __init__(
        self,
        source_lang: str = "en_us",
        target_lang: str = "ko_kr",
        pack_format: int = 15,
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
        self.source_lang = source_lang
        self.target_lang = target_lang

        # 패키징 클래스들 초기화
        self.resourcepack_builder = ResourcePackBuilder(
            source_lang=source_lang,
            target_lang=target_lang,
            pack_format=pack_format,
            pack_name=pack_name,
            pack_description=pack_description,
        )

        self.modpack_packager = ModpackPackager(
            source_lang=source_lang, target_lang=target_lang
        )

    async def package_all(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> Dict[str, PackagingResult]:
        """
        모든 번역 파일들을 패키징합니다.

        Args:
            translated_files: 번역된 파일들 {원본경로: 번역된경로}
            output_dir: 출력 디렉토리
            **kwargs: 추가 옵션들
                - create_resourcepack: 리소스팩 생성 여부 (기본값: True)
                - create_modpack: 모드팩 생성 여부 (기본값: True)
                - create_zips: ZIP 파일 생성 여부 (기본값: True)
                - parallel: 병렬 처리 여부 (기본값: True)

        Returns:
            Dict[패키징 타입, 결과]: 패키징 결과들
        """
        logger.info("전체 패키징 작업 시작")

        create_resourcepack = kwargs.get("create_resourcepack", True)
        create_modpack = kwargs.get("create_modpack", True)
        parallel = kwargs.get("parallel", True)

        results = {}

        # 출력 디렉토리 생성
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 번역 파일 분석
        stats = self._analyze_translated_files(translated_files)
        logger.info(f"번역 파일 분석 결과: {stats}")

        # 패키징 작업 실행
        if parallel:
            # 병렬 처리
            tasks = []

            if create_resourcepack and stats.get("mod_files", 0) > 0:
                tasks.append(
                    self._package_resourcepack(translated_files, output_dir, **kwargs)
                )

            if create_modpack and stats.get("modpack_files", 0) > 0:
                tasks.append(
                    self._package_modpack(translated_files, output_dir, **kwargs)
                )

            if tasks:
                task_results = await asyncio.gather(*tasks, return_exceptions=True)

                # 결과 처리
                task_names = []
                if create_resourcepack and stats.get("mod_files", 0) > 0:
                    task_names.append("resourcepack")
                if create_modpack and stats.get("modpack_files", 0) > 0:
                    task_names.append("modpack")

                for name, result in zip(task_names, task_results):
                    if isinstance(result, Exception):
                        logger.error(f"{name} 패키징 실패: {result}")
                        results[name] = PackagingResult(
                            success=False, errors=[str(result)]
                        )
                    else:
                        results[name] = result
        else:
            # 순차 처리
            if create_resourcepack and stats.get("mod_files", 0) > 0:
                results["resourcepack"] = await self._package_resourcepack(
                    translated_files, output_dir, **kwargs
                )

            if create_modpack and stats.get("modpack_files", 0) > 0:
                results["modpack"] = await self._package_modpack(
                    translated_files, output_dir, **kwargs
                )

        # 결과 요약
        self._log_packaging_summary(results)

        return results

    async def _package_resourcepack(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> PackagingResult:
        """리소스팩 패키징 작업"""
        logger.info("리소스팩 패키징 시작")

        # ZIP 생성 옵션 전달
        create_zip = kwargs.get("create_zips", True)

        result = await self.resourcepack_builder.package(
            translated_files, output_dir, **kwargs
        )

        # ZIP 파일 생성
        if result.success and create_zip and result.output_path:
            modpack_name = kwargs.get("modpack_name", "Unknown")
            lang_name = self._get_language_name(self.target_lang)
            zip_name = f"{modpack_name}_{lang_name}_리소스팩.zip"
            zip_path = self.resourcepack_builder.create_zip_package(
                result.output_path, zip_name
            )
            if zip_path:
                result.output_path = zip_path

        return result

    async def _package_modpack(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> PackagingResult:
        """모드팩 패키징 작업"""
        logger.info("모드팩 패키징 시작")

        # ZIP 생성 옵션 전달
        kwargs["create_zip"] = kwargs.get("create_zips", True)

        return await self.modpack_packager.package(
            translated_files, output_dir, **kwargs
        )

    def _analyze_translated_files(
        self, translated_files: Dict[str, str]
    ) -> Dict[str, int]:
        """번역 파일들을 분석하여 통계를 반환합니다."""
        stats = {
            "total_files": len(translated_files),
            "mod_files": 0,
            "modpack_files": 0,
            "config_files": 0,
            "kubejs_files": 0,
            "patchouli_files": 0,
            "other_files": 0,
        }

        for original_path in translated_files.keys():
            path_lower = original_path.lower()

            # 모드 파일 확인
            if self.resourcepack_builder._is_mod_file(original_path):
                stats["mod_files"] += 1

            # 모드팩 파일 확인
            elif "config" in path_lower:
                stats["config_files"] += 1
                stats["modpack_files"] += 1
            elif "kubejs" in path_lower:
                stats["kubejs_files"] += 1
                stats["modpack_files"] += 1
            elif "patchouli" in path_lower:
                stats["patchouli_files"] += 1
                stats["modpack_files"] += 1
            else:
                stats["other_files"] += 1

        return stats

    def _log_packaging_summary(self, results: Dict[str, PackagingResult]) -> None:
        """패키징 결과 요약을 로그에 출력합니다."""
        logger.info("=== 패키징 작업 완료 ===")

        total_files = 0
        successful_packages = 0

        for package_type, result in results.items():
            if result.success:
                successful_packages += 1
                total_files += result.file_count
                logger.info(
                    f"✅ {package_type}: {result.file_count}개 파일 → {result.output_path}"
                )
            else:
                logger.error(f"❌ {package_type}: 실패 ({', '.join(result.errors)})")

        logger.info(
            f"총 {successful_packages}/{len(results)}개 패키지 생성, {total_files}개 파일 처리"
        )

    def create_readme(
        self, output_dir: Path, results: Dict[str, PackagingResult]
    ) -> None:
        """사용법을 설명하는 README 파일을 생성합니다."""
        try:
            readme_content = self._generate_readme_content(results)
            readme_path = output_dir / "README.md"

            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(readme_content)

            logger.info(f"README 파일 생성: {readme_path}")

        except Exception as e:
            logger.error(f"README 파일 생성 실패: {e}")

    def _generate_readme_content(self, results: Dict[str, PackagingResult]) -> str:
        """README 파일 내용을 생성합니다."""
        content = [
            "# 한국어 번역 패키지",
            "",
            "이 폴더는 모드팩 자동 번역 시스템으로 생성된 한국어 번역 패키지입니다.",
            "",
            "## 패키지 구성",
            "",
        ]

        # 모드팩 이름과 언어 추출 (결과 경로에서)
        modpack_name = "Unknown"
        lang_name = self._get_language_name(self.target_lang)
        for result in results.values():
            if result.success and result.output_path:
                path_name = str(result.output_path)
                if f"_{lang_name}_" in path_name:
                    # 파일명에서 모드팩 이름 추출
                    filename = Path(path_name).stem
                    if f"_{lang_name}_리소스팩" in filename:
                        modpack_name = filename.replace(f"_{lang_name}_리소스팩", "")
                    elif f"_{lang_name}_덮어쓰기" in filename:
                        modpack_name = filename.replace(f"_{lang_name}_덮어쓰기", "")
                    break

        if "resourcepack" in results and results["resourcepack"].success:
            content.extend(
                [
                    f"### 리소스팩 ({modpack_name}_{lang_name}_리소스팩.zip)",
                    "- 모드들의 번역된 언어 파일들이 포함된 리소스팩",
                    "- 게임 내 리소스팩 폴더에 넣고 활성화하세요",
                    "- 파일 위치: `.minecraft/resourcepacks/`",
                    "",
                ]
            )

        if "modpack" in results and results["modpack"].success:
            content.extend(
                [
                    f"### 모드팩 파일 ({modpack_name}_{lang_name}_덮어쓰기.zip)",
                    "- Config, KubeJS, Patchouli 등의 번역된 파일들",
                    "- 모드팩 인스턴스 폴더에 압축 해제하세요",
                    "- 기존 파일들을 백업한 후 덮어쓰기하세요",
                    "",
                ]
            )

        content.extend(
            [
                "## 설치 방법",
                "",
                "### 리소스팩 설치",
                f"1. `{modpack_name}_{lang_name}_리소스팩.zip` 파일을 `.minecraft/resourcepacks/` 폴더에 복사",
                "2. 게임 실행 후 옵션 → 리소스팩에서 활성화",
                "",
                "### 모드팩 파일 설치",
                "1. 모드팩 인스턴스 폴더를 찾습니다",
                "2. 기존 파일들을 백업합니다",
                f"3. `{modpack_name}_{lang_name}_덮어쓰기.zip` 파일을 압축 해제합니다",
                "4. 게임을 재시작합니다",
                "",
                "## 주의사항",
                "",
                "- 설치 전 반드시 백업하세요",
                "- 모드팩 업데이트 시 번역 파일들이 덮어쓰여질 수 있습니다",
                "- 번역에 오류가 있다면 원본 파일로 복원하세요",
                "",
                f"번역 언어: {self.source_lang} → {self.target_lang}",
                "",
            ]
        )

        return "\n".join(content)

    def get_package_statistics(
        self, results: Dict[str, PackagingResult]
    ) -> Dict[str, any]:
        """패키징 결과 통계를 반환합니다."""
        stats = {
            "total_packages": len(results),
            "successful_packages": sum(1 for r in results.values() if r.success),
            "failed_packages": sum(1 for r in results.values() if not r.success),
            "total_files": sum(r.file_count for r in results.values() if r.success),
            "package_details": {},
        }

        for package_type, result in results.items():
            stats["package_details"][package_type] = {
                "success": result.success,
                "file_count": result.file_count,
                "output_path": str(result.output_path) if result.output_path else None,
                "errors": result.errors,
            }

        return stats

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
