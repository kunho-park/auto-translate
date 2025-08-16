"""
패키징 관리자 모듈

전체 패키징 작업을 관리하고 조정합니다.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Tuple

from .base import PackagingResult
from .jar_modifier import JarModifierPackager
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

        self.jar_modifier = JarModifierPackager(
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
                - create_jar_mods: JAR 파일 수정 여부 (기본값: True)
                - create_zips: ZIP 파일 생성 여부 (기본값: True)
                - parallel: 병렬 처리 여부 (기본값: True)
                - mods_path: 모드 JAR 파일들이 위치한 경로

        Returns:
            Dict[패키징 타입, 결과]: 패키징 결과들
        """
        logger.info("전체 패키징 작업 시작")

        create_resourcepack = kwargs.get("create_resourcepack", True)
        create_modpack = kwargs.get("create_modpack", True)
        create_jar_mods = kwargs.get("create_jar_mods", True)
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

            if create_jar_mods and stats.get("data_files", 0) > 0:
                tasks.append(
                    self._package_jar_mods(translated_files, output_dir, **kwargs)
                )

            if tasks:
                task_results = await asyncio.gather(*tasks, return_exceptions=True)

                # 결과 처리
                for result in task_results:
                    if isinstance(result, Exception):
                        # 예외 발생 시 처리. 어떤 태스크에서 발생했는지 특정하기 어려움.
                        # 필요하다면 태스크 식별자를 결과에 포함시켜야 함.
                        logger.error(f"패키징 작업 중 예외 발생: {result}")
                        # 모든 태스크가 실패했다고 가정하거나, 별도의 오류 처리가 필요.
                    elif isinstance(result, tuple) and len(result) == 2:
                        name, package_result = result
                        results[name] = package_result
                    else:
                        logger.error(f"알 수 없는 결과 타입: {result}")
        else:
            # 순차 처리
            if create_resourcepack and stats.get("mod_files", 0) > 0:
                _, results["resourcepack"] = await self._package_resourcepack(
                    translated_files, output_dir, **kwargs
                )

            if create_modpack and stats.get("modpack_files", 0) > 0:
                _, results["modpack"] = await self._package_modpack(
                    translated_files, output_dir, **kwargs
                )

            if create_jar_mods and stats.get("data_files", 0) > 0:
                _, results["jar_mods"] = await self._package_jar_mods(
                    translated_files, output_dir, **kwargs
                )

        # 결과 요약
        self._log_packaging_summary(results)

        return results

    async def _package_resourcepack(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> tuple[str, PackagingResult]:
        """리소스팩 패키징 작업"""
        logger.info("리소스팩 패키징 시작")

        # ZIP 생성 옵션 전달
        create_zip = kwargs.get("create_zips", True)

        result = await self.resourcepack_builder.package(
            translated_files, output_dir, **kwargs
        )
        return "resourcepack", result

    async def _package_modpack(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> tuple[str, PackagingResult]:
        """모드팩 패키징 작업"""
        logger.info("모드팩 패키징 시작")

        # ZIP 생성 옵션 전달
        create_zip = kwargs.get("create_zips", True)

        result = await self.modpack_packager.package(
            translated_files, output_dir, **kwargs
        )
        return "modpack", result

    async def _package_jar_mods(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> tuple[str, PackagingResult]:
        """JAR 파일 수정 패키징 작업"""
        logger.info("JAR 파일 수정 패키징 시작")

        result = await self.jar_modifier.package(
            translated_files, output_dir, **kwargs
        )
        return "jar_mods", result

    def _analyze_translated_files(
        self, translated_files: Dict[str, str]
    ) -> Dict[str, int]:
        """번역 파일들을 분석하여 통계를 반환합니다."""
        stats = {
            "total_files": len(translated_files),
            "mod_files": 0,
            "modpack_files": 0,
            "data_files": 0,
            "config_files": 0,
            "kubejs_files": 0,
            "patchouli_files": 0,
            "other_files": 0,
        }

        for original_path in translated_files.keys():
            path_lower = original_path.lower()

            # /data 폴더 파일 확인
            if self.jar_modifier._is_data_file(original_path):
                stats["data_files"] += 1

            # 모드 파일 확인
            elif self.resourcepack_builder._is_mod_file(original_path):
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
        logger.info("=== 패키징 결과 ===")

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

        if "jar_mods" in results and results["jar_mods"].success:
            content.extend(
                [
                    f"### 수정된 모드 JAR 파일들 ({modpack_name}_{lang_name}_덮어쓰기/)",
                    "- /data 폴더의 번역된 파일들이 포함된 수정된 모드 JAR 파일들",
                    "- `mods/` 폴더에 번역된 JAR 파일들이 있습니다",
                    "- 원본 모드 JAR 파일들을 번역된 JAR 파일로 교체하세요",
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
                "### 수정된 모드 JAR 파일 설치",
                "1. 모드팩 인스턴스의 `mods/` 폴더를 찾습니다",
                "2. 기존 모드 JAR 파일들을 안전한 곳에 백업합니다 (권장)",
                f"3. `{modpack_name}_{lang_name}_덮어쓰기/mods/` 폴더에서 `*_korean_modified.jar` 파일들을 `mods/` 폴더로 복사합니다",
                "4. 게임을 재시작합니다",
                "",
                "## 주의사항",
                "",
                "- 설치 전 반드시 백업하세요",
                "- 모드팩 업데이트 시 번역 파일들이 덮어쓰여질 수 있습니다",
                "- 수정된 JAR 파일은 모드 업데이트 시 원본으로 교체됩니다",
                "- 번역에 오류가 있다면 백업해둔 원본 파일로 복원하세요",
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
