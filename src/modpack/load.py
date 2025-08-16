import logging
import os
import zipfile
from glob import escape as glob_escape
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..parsers.base import BaseParser

logger = logging.getLogger(__name__)


class ModpackLoader:
    """모드팩 폴더에서 번역 대상 파일들을 찾아 추출하는 클래스"""

    # 번역 대상 디렉토리 화이트리스트
    DIR_FILTER_WHITELIST = [
        "lang/",
        "assets/",
        "data/",
        "kubejs/",
        "config/",
        "patchouli_books/",
    ]

    SOURCE_WHITELIST = [
        "/ftbquests/quests/chapters/",
        "/ftbquests/quests/reward_tables/",
        "/ftbquests/quests/lang/",
        "/paxi/datapacks/",
        "/paxi/resourcepacks/",
        "/puffish_skills/categories/",
        "/kubejs/server_scripts/",
        "/kubejs/startup_scripts/",
        "/kubejs/client_scripts/",
        "/powers/",
        "/origins/",
        "/patchouli_books/",
    ]

    def __init__(
        self,
        modpack_path: str,
        source_lang: str = "en_us",
        target_lang: Optional[str] = None,
        translate_config: bool = True,
        translate_kubejs: bool = True,
        translate_mods: bool = True,
        translate_resourcepacks: bool = True,
        translate_patchouli_books: bool = True,
        translate_ftbquests: bool = True,
        progress_callback: callable = None,
    ):
        """
        ModpackLoader 초기화

        Args:
            modpack_path: 모드팩 폴더 경로
            source_lang: 소스 언어 코드 (기본값: en_us)
            target_lang: 타겟 언어 코드 (기본값: None, 지정시 기존 번역 파일도 수집)
            translate_config: config 폴더 번역 여부
            translate_kubejs: kubejs 폴더 번역 여부
            translate_mods: mods 폴더 번역 여부
            translate_resourcepacks: 리소스팩 번역 여부
            translate_patchouli_books: patchouli 책 번역 여부
            translate_ftbquests: FTB Quests 번역 여부
            progress_callback: 진행률 업데이트 콜백 함수
        """
        self.modpack_path = Path(modpack_path)
        self.source_lang = source_lang.lower()
        self.target_lang = target_lang.lower() if target_lang else None
        self.translate_config = translate_config
        self.translate_kubejs = translate_kubejs
        self.translate_mods = translate_mods
        self.translate_resourcepacks = translate_resourcepacks
        self.translate_patchouli_books = translate_patchouli_books
        self.translate_ftbquests = translate_ftbquests
        self.progress_callback = progress_callback

        # 지원하는 파일 확장자
        self.supported_extensions = BaseParser.get_supported_extensions()

        # 추출된 파일 저장용
        self.translation_files: List[Dict[str, str]] = []
        self.jar_files: List[str] = []
        self.fingerprints: Dict[str, str] = {}

        # 기존 번역 데이터 저장용 (소스 언어와 타겟 언어가 매핑된 데이터)
        self.existing_translations: Dict[
            str, Dict[str, str]
        ] = {}  # file_path -> {source_text: target_text}

    def load_translation_files(
        self,
    ) -> Tuple[List[Dict[str, str]], List[str], Dict[str, str]]:
        """
        모드팩에서 번역 대상 파일들을 찾아 로드합니다.

        Returns:
            Tuple[번역 파일 목록, JAR 파일 목록, 파일 핑거프린트]
        """
        logger.info(f"모드팩 로딩 시작: {self.modpack_path}")

        if self.progress_callback:
            self.progress_callback(
                "모드팩 스캔 시작", 0, 0, "번역 대상 파일들을 검색하고 있습니다..."
            )

        # ZIP 파일들 먼저 추출
        try:
            if self.progress_callback:
                self.progress_callback(
                    "ZIP 파일 추출 중", 0, 0, "압축 파일들을 추출하고 있습니다..."
                )
            self._extract_all_zip_files()
        except Exception as e:
            logger.error(f"ZIP 파일 추출 실패: {e}")

        # 전체 단계 수 계산
        total_steps = 0
        if self.translate_config:
            total_steps += 1
        if self.translate_ftbquests:
            total_steps += 1
        if self.translate_kubejs:
            total_steps += 1
        if self.translate_patchouli_books:
            total_steps += 1
        if self.translate_resourcepacks:
            total_steps += 1
        if self.translate_mods:
            total_steps += 1

        current_step = 0

        # 각 폴더별로 파일 수집
        if self.translate_config:
            current_step += 1
            if self.progress_callback:
                self.progress_callback(
                    "Config 파일 스캔",
                    current_step,
                    total_steps,
                    "config 폴더를 스캔하고 있습니다...",
                )
            self._load_config_files()

        if self.translate_ftbquests:
            current_step += 1
            if self.progress_callback:
                self.progress_callback(
                    "FTB Quests 파일 스캔",
                    current_step,
                    total_steps,
                    "FTB Quests 파일을 스캔하고 있습니다...",
                )
            self._load_ftbquests_files()

        if self.translate_kubejs:
            current_step += 1
            if self.progress_callback:
                self.progress_callback(
                    "KubeJS 파일 스캔",
                    current_step,
                    total_steps,
                    "kubejs 폴더를 스캔하고 있습니다...",
                )
            self._load_kubejs_files()

        if self.translate_patchouli_books:
            current_step += 1
            if self.progress_callback:
                self.progress_callback(
                    "Patchouli 파일 스캔",
                    current_step,
                    total_steps,
                    "patchouli 폴더를 스캔하고 있습니다...",
                )
            self._load_patchouli_files()

        if self.translate_resourcepacks:
            current_step += 1
            if self.progress_callback:
                self.progress_callback(
                    "리소스팩 파일 스캔",
                    current_step,
                    total_steps,
                    "리소스팩/데이터팩을 스캔하고 있습니다...",
                )
            self._load_resourcepack_files()

        if self.translate_mods:
            current_step += 1
            if self.progress_callback:
                self.progress_callback(
                    "JAR 파일 처리 시작",
                    current_step,
                    total_steps,
                    "JAR 파일들을 처리하고 있습니다...",
                )
            self._load_mod_files()

        logger.info(f"총 {len(self.translation_files)}개의 번역 파일을 찾았습니다.")
        logger.info(f"총 {len(self.jar_files)}개의 JAR 파일을 찾았습니다.")

        # 기존 번역 데이터 분석
        self.analyze_existing_translations()

        if self.progress_callback:
            self.progress_callback(
                "파일 스캔 완료",
                total_steps,
                total_steps,
                f"총 {len(self.translation_files)}개 번역 파일, {len(self.jar_files)}개 JAR 파일 발견",
            )

        return self.translation_files, self.jar_files, self.fingerprints

    def _load_config_files(self):
        """config 폴더에서 번역 대상 파일들을 찾습니다. (ftbquests 제외)"""
        pattern = self._normalize_glob_path(self.modpack_path / "config" / "**" / "*.*")
        files = glob(str(pattern), recursive=True)

        for file_path in files:
            # ftbquests 폴더는 제외
            if "ftbquests" in file_path.lower():
                continue

            if self._is_translation_file(file_path):
                lang_type = self._get_file_language_type(file_path)
                self.translation_files.append(
                    {
                        "input": file_path,
                        "type": "config",
                        "lang_type": lang_type,
                    }
                )

        logger.info(
            f"config 폴더에서 {len([f for f in self.translation_files if f.get('type') == 'config'])}개 파일 발견"
        )

    def _load_ftbquests_files(self):
        """config/ftbquests 및 ftbquests 폴더에서 번역 대상 파일들을 찾습니다."""
        found_files_count = 0
        search_paths = [
            self.modpack_path / "config" / "ftbquests",
        ]

        for path in search_paths:
            if path.is_dir():
                pattern = self._normalize_glob_path(path / "**" / "*.*")
                files = glob(str(pattern), recursive=True)
                for file_path in files:
                    if self._is_translation_file(file_path):
                        found_files_count += 1
                        lang_type = self._get_file_language_type(file_path)
                        self.translation_files.append(
                            {
                                "input": file_path,
                                "type": "ftbquests",
                                "lang_type": lang_type,
                            }
                        )

        logger.info(f"ftbquests 폴더에서 {found_files_count}개 파일 발견")

    def _load_kubejs_files(self):
        """kubejs 폴더에서 번역 대상 파일들을 찾습니다."""
        pattern = self._normalize_glob_path(self.modpack_path / "kubejs" / "**" / "*.*")
        files = glob(str(pattern), recursive=True)

        for file_path in files:
            if self._is_translation_file(file_path):
                lang_type = self._get_file_language_type(file_path)
                self.translation_files.append(
                    {
                        "input": file_path,
                        "type": "kubejs",
                        "lang_type": lang_type,
                    }
                )

        logger.info(
            f"kubejs 폴더에서 {len([f for f in self.translation_files if f.get('type') == 'kubejs'])}개 파일 발견"
        )

    def _load_patchouli_files(self):
        """patchouli_books 폴더에서 번역 대상 파일들을 찾습니다."""
        pattern = self._normalize_glob_path(
            self.modpack_path / "patchouli_books" / "**" / "*.*"
        )
        files = glob(str(pattern), recursive=True)

        for file_path in files:
            if self._is_translation_file(file_path):
                lang_type = self._get_file_language_type(file_path)
                self.translation_files.append(
                    {
                        "input": file_path,
                        "type": "patchouli",
                        "lang_type": lang_type,
                    }
                )

        logger.info(
            f"patchouli 폴더에서 {len([f for f in self.translation_files if f.get('type') == 'patchouli'])}개 파일 발견"
        )

    def _load_resourcepack_files(self):
        """리소스팩 폴더에서 번역 대상 파일들을 찾습니다."""
        # resourcepacks, datapacks 폴더들 검색
        for folder in ["resourcepacks", "datapacks"]:
            pattern = self._normalize_glob_path(
                self.modpack_path / folder / "**" / "*.*"
            )
            files = glob(str(pattern), recursive=True)

            for file_path in files:
                if self._is_translation_file(file_path):
                    lang_type = self._get_file_language_type(file_path)
                    self.translation_files.append(
                        {
                            "input": file_path,
                            "type": folder,
                            "lang_type": lang_type,
                        }
                    )

        resourcepack_count = len(
            [
                f
                for f in self.translation_files
                if f.get("type") in ["resourcepacks", "datapacks"]
            ]
        )
        logger.info(f"리소스팩/데이터팩에서 {resourcepack_count}개 파일 발견")

    def _load_mod_files(self):
        """mods 폴더의 JAR 파일들을 처리합니다."""
        pattern = self._normalize_glob_path(self.modpack_path / "mods" / "*.jar")
        jar_files = glob(str(pattern))

        total_jars = len(jar_files)
        if self.progress_callback and total_jars > 0:
            self.progress_callback(
                "JAR 파일 처리 시작",
                0,
                total_jars,
                f"총 {total_jars}개 JAR 파일 처리 시작",
            )

        for i, jar_path in enumerate(jar_files):
            try:
                jar_name = Path(jar_path).name
                if self.progress_callback:
                    self.progress_callback(
                        "JAR 파일 처리 중", i, total_jars, f"처리 중: {jar_name}"
                    )

                self._process_jar_file(jar_path)

                if self.progress_callback:
                    self.progress_callback(
                        "JAR 파일 처리 중", i + 1, total_jars, f"완료: {jar_name}"
                    )

            except Exception as e:
                logger.error(f"JAR 파일 처리 실패 ({jar_path}): {e}")

        logger.info(f"mods 폴더에서 {len(jar_files)}개 JAR 파일 처리 완료")

        if self.progress_callback and total_jars > 0:
            self.progress_callback(
                "JAR 파일 처리 완료",
                total_jars,
                total_jars,
                f"{total_jars}개 JAR 파일 처리 완료",
            )

    def _process_jar_file(self, jar_path: str):
        """개별 JAR 파일을 처리하여 번역 대상 파일들을 추출합니다."""
        jar_name = os.path.basename(jar_path)

        # 핑거프린트 생성 (간단한 파일 크기 기반)
        self.fingerprints[jar_name] = str(os.path.getsize(jar_path))

        with zipfile.ZipFile(jar_path, "r") as zf:
            logger.info(f"JAR 파일 처리 중: {jar_name}")

            extract_dir = self.modpack_path / "mods" / "extracted" / jar_name
            extract_dir.mkdir(parents=True, exist_ok=True)

            extracted_any = False

            for entry in zf.namelist():
                # 번역 관련 파일만 추출
                if self._should_extract_from_jar(entry):
                    try:
                        zf.extract(entry, extract_dir)
                        extracted_any = True

                        # 추출된 파일을 번역 목록에 추가
                        extracted_path = extract_dir / entry
                        if extracted_path.is_file() and self._is_translation_file(
                            str(extracted_path)
                        ):
                            lang_type = self._get_file_language_type(
                                str(extracted_path)
                            )
                            self.translation_files.append(
                                {
                                    "input": str(extracted_path),
                                    "type": "mod",
                                    "jar_name": jar_name,
                                    "lang_type": lang_type,
                                }
                            )

                    except Exception as e:
                        logger.error(f"JAR에서 파일 추출 실패 ({entry}): {e}")

            if extracted_any:
                self.jar_files.append(jar_path)

    def _should_extract_from_jar(self, entry_path: str) -> bool:
        """JAR 파일 내 항목이 추출 대상인지 판단합니다."""
        entry_lower = entry_path.lower()
        ext = os.path.splitext(entry_path)[1].lower()

        # 지원하는 확장자인지 확인
        if ext not in [ext.lower() for ext in self.supported_extensions]:
            return False

        # 번역 관련 디렉토리에 있는지 확인
        return any(
            dir_filter in entry_lower
            for dir_filter in [d.lower() for d in self.DIR_FILTER_WHITELIST]
        )

    def _is_translation_file(self, file_path: str) -> bool:
        """파일이 번역 대상인지 판단합니다."""
        file_path_normalized = file_path.replace("\\", "/").lower()
        ext = os.path.splitext(file_path)[1].lower()

        # 지원하는 확장자인지 확인
        if ext not in [ext.lower() for ext in self.supported_extensions]:
            return False

        # 번역 대상 디렉토리에 있는지 먼저 확인
        if not any(
            dir_filter.lower() in file_path_normalized
            for dir_filter in self.DIR_FILTER_WHITELIST
        ):
            return False

        # lang 폴더 내 파일이거나, 파일 이름에 언어 코드가 포함된 경우
        # 소스 또는 타겟 언어 파일인지 확인
        is_source = self.source_lang in file_path_normalized
        is_target = self.target_lang and self.target_lang in file_path_normalized

        # lang 폴더 밖의 파일들은 보통 en_us.json 처럼 언어 코드가 파일명에 포함됨
        # 따라서 소스 또는 타겟 언어 코드를 포함하면 번역 파일로 간주
        if "lang/" in file_path_normalized:
            return is_source or is_target
        else:
            # lang 폴더 밖의 파일들은 언어 코드 체크 없이 대상으로 간주
            return True

    def _get_file_language_type(self, file_path: str) -> str:
        """파일의 언어 타입을 반환합니다 (source, target, other)"""
        file_path_normalized = file_path.replace("\\", "/").lower()

        if "lang/" in file_path_normalized:
            if self.source_lang in file_path_normalized:
                return "source"
            elif self.target_lang and self.target_lang in file_path_normalized:
                return "target"
        elif any(
            dir_filter.lower() in file_path_normalized
            for dir_filter in self.SOURCE_WHITELIST
        ):
            return "source"

        return "other"

    def _extract_all_zip_files(self):
        """모드팩 내 모든 ZIP 파일들을 추출합니다."""
        pattern = self._normalize_glob_path(self.modpack_path / "**" / "*.zip")
        zip_files = glob(str(pattern), recursive=True)

        for zip_path in zip_files:
            try:
                self._extract_zip_file(zip_path)
            except Exception as e:
                logger.error(f"ZIP 파일 추출 실패 ({zip_path}): {e}")

    def _extract_zip_file(self, zip_path: str):
        """개별 ZIP 파일을 추출합니다."""
        zip_path_lower = zip_path.lower()

        # paxi나 openloader 관련 ZIP 파일만 처리
        if not ("paxi" in zip_path_lower or "openloader" in zip_path_lower):
            return

        extract_dir = zip_path + ".zip_extracted"

        # 이미 추출된 경우 스킵
        if os.path.exists(extract_dir):
            logger.info(f"이미 추출된 파일: {zip_path}")
            return

        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            logger.info(f"ZIP 파일 추출 중: {zip_path}")
            zf.extractall(extract_dir)

    @staticmethod
    def _normalize_glob_path(path: Path) -> str:
        """glob 패턴에서 사용할 경로를 정규화합니다."""
        path_str = str(path).replace("\\", "/")
        parts = []

        for part in path_str.split("/"):
            if part.startswith("**") or part.startswith("*"):
                parts.append(part)
            else:
                parts.append(glob_escape(part))

        return "/".join(parts)

    def _get_category_from_file_info(self, file_info: Dict[str, str]) -> str:
        """파일 정보에서 카테고리를 결정합니다."""
        file_type = file_info.get("type", "unknown")

        if file_type == "mod":
            jar_name = file_info.get("jar_name", "Unknown Mod")
            # .jar 확장자 및 버전 정보 제거
            mod_name = Path(jar_name).stem.split("-")[0].replace("_", " ").title()
            return f"Mod: {mod_name}"
        elif file_type == "kubejs":
            return "KubeJS"
        elif file_type == "ftbquests":
            return "FTB Quests"
        elif file_type == "patchouli":
            return "Patchouli Books"
        elif file_type == "config":
            return "Configuration"
        elif file_type in ["resourcepacks", "datapacks"]:
            return "Resource/Data Packs"
        else:
            return "Other"

    def scan_translatable_files(self) -> List[Dict[str, Any]]:
        """
        번역 선택 페이지에 표시할 번역 가능한 소스 파일 목록을 스캔합니다.
        이 메서드는 UI에 필요한 형식으로 데이터를 반환합니다.
        """
        logger.info("UI용 번역 가능 파일 스캔 시작...")

        # 기존 파일 로딩 로직을 실행하여 모든 파일 정보를 수집합니다.
        # 이전에 스캔한 결과가 있으면 재사용합니다.
        if not self.translation_files:
            self.load_translation_files()

        selectable_files = []
        for file_info in self.translation_files:
            # 소스 언어 파일만 선택 가능하도록 필터링합니다.
            if file_info.get("lang_type") == "source":
                file_path = Path(file_info["input"])
                try:
                    relative_path = file_path.relative_to(self.modpack_path)
                except ValueError:
                    relative_path = file_path  # 모드팩 외부에 있는 경우 전체 경로 사용

                selectable_files.append(
                    {
                        "file_name": file_path.name,
                        "relative_path": str(relative_path),
                        "full_path": str(file_path),
                        "category": self._get_category_from_file_info(file_info),
                        "selected": True,  # 기본적으로 선택 상태로 설정
                    }
                )

        logger.info(f"UI용으로 {len(selectable_files)}개의 선택 가능한 파일 스캔 완료.")
        return selectable_files

    def get_translation_stats(self) -> Dict[str, int]:
        """번역 파일 통계를 반환합니다."""
        stats = {}
        for file_info in self.translation_files:
            file_type = file_info.get("type", "unknown")
            stats[file_type] = stats.get(file_type, 0) + 1

        stats["total_files"] = len(self.translation_files)
        stats["total_jars"] = len(self.jar_files)

        return stats

    def clear_extracted_files(self):
        """추출된 파일들을 정리합니다."""
        extracted_dirs = []

        # mods/extracted 폴더
        mods_extracted = self.modpack_path / "mods" / "extracted"
        if mods_extracted.exists():
            extracted_dirs.append(mods_extracted)

        # .zip_extracted 폴더들
        pattern = self._normalize_glob_path(
            self.modpack_path / "**" / "*.zip_extracted"
        )
        extracted_dirs.extend(glob(str(pattern), recursive=True))

        for dir_path in extracted_dirs:
            try:
                import shutil

                shutil.rmtree(dir_path)
                logger.info(f"추출된 폴더 정리: {dir_path}")
            except Exception as e:
                logger.error(f"폴더 정리 실패 ({dir_path}): {e}")

    def analyze_existing_translations(self) -> Dict[str, Dict[str, str]]:
        """기존 번역 데이터를 분석하여 번역 매핑을 추출합니다."""
        if not self.target_lang:
            logger.info("타겟 언어가 지정되지 않아 기존 번역 분석을 건너뜁니다.")
            return {}

        # 소스와 타겟 파일을 그룹화
        source_files = {}  # 기본 경로 -> 파일 정보
        target_files = {}  # 기본 경로 -> 파일 정보

        for file_info in self.translation_files:
            lang_type = file_info.get("lang_type", "other")
            file_path = file_info["input"]

            # 언어별로 기본 경로 추출 (언어 코드 부분 제거)
            base_path = self._get_base_path_without_lang(file_path)

            if lang_type == "source":
                source_files[base_path] = file_info
            elif lang_type == "target":
                target_files[base_path] = file_info

        logger.info(
            f"소스 파일: {len(source_files)}개, 타겟 파일: {len(target_files)}개 발견"
        )

        # 매칭되는 파일 쌍 찾기
        matched_pairs = []
        for base_path in source_files:
            if base_path in target_files:
                matched_pairs.append((source_files[base_path], target_files[base_path]))

        logger.info(f"매칭되는 파일 쌍: {len(matched_pairs)}개 발견")

        if not matched_pairs:
            return {}

        # 각 파일 쌍에서 번역 매핑 추출
        all_translations = {}

        for source_info, target_info in matched_pairs:
            try:
                source_path = source_info["input"]
                target_path = target_info["input"]

                logger.info(
                    f"기존 번역 분석 중: {Path(source_path).name} -> {Path(target_path).name}"
                )

                # 파일 파싱
                source_data = self._parse_file_safely(source_path)
                target_data = self._parse_file_safely(target_path)

                if source_data and target_data:
                    # 번역 매핑 추출
                    mapping = self._extract_translation_mapping(
                        source_data, target_data
                    )
                    if mapping:
                        all_translations[source_path] = mapping
                        logger.info(f"  추출된 번역 쌍: {len(mapping)}개")

            except Exception as e:
                logger.warning(f"기존 번역 분석 실패 ({source_path}): {e}")

        # 전체 통계
        total_pairs = sum(len(mapping) for mapping in all_translations.values())
        logger.info(f"총 {total_pairs}개의 기존 번역 쌍을 추출했습니다.")

        self.existing_translations = all_translations
        return all_translations

    def _get_base_path_without_lang(self, file_path: str) -> str:
        """파일 경로에서 언어 코드 부분을 제거한 기본 경로를 반환합니다."""
        # 언어 코드를 일반적인 패턴으로 대체
        path_normalized = file_path.replace("\\", "/")

        # 일반적인 언어 코드 패턴들 (xx_xx 형식)
        import re

        lang_pattern = r"/[a-z]{2}_[a-z]{2}\.([a-zA-Z]+)$"

        # 언어 코드를 제거하고 기본 경로 생성
        base_path = re.sub(lang_pattern, r"/LANG.\1", path_normalized)
        return base_path

    def _parse_file_safely(self, file_path: str) -> Optional[Dict[str, Any]]:
        """파일을 안전하게 파싱합니다."""
        try:
            import asyncio
            import os

            from ..parsers.base import BaseParser

            # 파일 확장자 확인
            _, ext = os.path.splitext(file_path)
            parser_class = BaseParser.get_parser_by_extension(ext)

            if parser_class:
                # 파서 인스턴스 생성
                parser = parser_class(Path(file_path))

                # 비동기 파싱을 동기적으로 실행
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 이미 이벤트 루프가 실행 중인 경우 새 스레드에서 실행
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, parser.parse())
                            result = future.result(timeout=30)  # 30초 타임아웃
                    else:
                        result = loop.run_until_complete(parser.parse())
                except RuntimeError:
                    # 이벤트 루프가 없는 경우 새로 생성
                    result = asyncio.run(parser.parse())

                return result
        except Exception as e:
            logger.debug(f"파일 파싱 실패 ({file_path}): {e}")
        return None

    def _extract_translation_mapping(
        self, source_data: Dict[str, Any], target_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """소스와 타겟 데이터에서 번역 매핑을 추출합니다."""
        mapping = {}

        def extract_from_dict(src_dict, tgt_dict, path=""):
            if not isinstance(src_dict, dict) or not isinstance(tgt_dict, dict):
                return

            for key in src_dict:
                if key in tgt_dict:
                    src_value = src_dict[key]
                    tgt_value = tgt_dict[key]

                    if isinstance(src_value, str) and isinstance(tgt_value, str):
                        # 문자열 값이고 서로 다르면 번역 쌍으로 간주
                        src_clean = src_value.strip()
                        tgt_clean = tgt_value.strip()

                        if (
                            src_clean
                            and tgt_clean
                            and src_clean != tgt_clean
                            and len(src_clean) > 1
                            and len(tgt_clean) > 1
                        ):
                            mapping[src_clean] = tgt_clean

                    elif isinstance(src_value, dict) and isinstance(tgt_value, dict):
                        # 재귀적으로 중첩된 딕셔너리 처리
                        extract_from_dict(
                            src_value, tgt_value, f"{path}.{key}" if path else key
                        )

        extract_from_dict(source_data, target_data)
        return mapping

    def get_all_existing_translations(self) -> Dict[str, str]:
        """
        모든 기존 번역 데이터를 하나의 '번역 캐시' 딕셔너리로 통합하여 반환합니다.
        키는 원본 영어 텍스트, 값은 한국어 번역입니다.
        """
        if not self.existing_translations:
            self.analyze_existing_translations()

        # 번역 캐시: { "English Text": "한국어 번역" }
        translation_cache = {}
        for file_mapping in self.existing_translations.values():
            for source_text, target_text in file_mapping.items():
                # 이미 캐시에 있지만 다른 번역이 있는 경우, 일단 덮어씁니다.
                # (나중에 더 정교한 로직 추가 가능, 예: 가장 긴 번역 선택)
                translation_cache[source_text] = target_text

        logger.info(f"통합된 번역 캐시 생성 완료: {len(translation_cache)}개 항목")
        return translation_cache
