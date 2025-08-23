"""
JAR 파일 수정 패키저 모듈

/data 폴더에 포함되는 파일들을 처리하기 위해 모드 JAR 파일을 직접 수정합니다.
"""

import logging
import shutil
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set

from .base import BasePackager, PackagingResult

logger = logging.getLogger(__name__)


class JarModifierPackager(BasePackager):
    """/data 폴더 파일들을 처리하기 위해 모드 JAR 파일을 직접 수정하는 클래스"""

    def __init__(
        self,
        source_lang: str = "en_us",
        target_lang: str = "ko_kr",
        mods_path: Optional[Path] = None,
    ):
        """
        Args:
            source_lang: 원본 언어 코드
            target_lang: 대상 언어 코드
            mods_path: 모드 JAR 파일들이 위치한 경로
        """
        super().__init__(source_lang, target_lang)
        self.mods_path = mods_path
        self._mod_id_cache: Dict[str, Path] = {}  # mod_id -> jar_path 매핑
        self._mod_id_retry_count: Dict[str, int] = {}  # mod_id -> retry count
        self._max_retry_attempts = 1  # 최대 재시도 횟수

        # 초기화 시 모드 경로가 주어지면 스캔
        if mods_path:
            self._scan_mod_jars()

    async def package(
        self, translated_files: Dict[str, str], output_dir: Path, **kwargs
    ) -> PackagingResult:
        """
        번역된 /data 폴더 파일들을 모드 JAR에 직접 삽입하여 패키징합니다.

        Args:
            translated_files: 번역된 파일들 {원본경로: 번역된경로}
            output_dir: 출력 디렉토리
            **kwargs: 추가 옵션
                - mods_path: 모드 JAR 파일들이 위치한 경로

        Returns:
            PackagingResult: 패키징 결과
        """
        logger.info("JAR 수정 패키징 시작")
        result = PackagingResult(success=False)

        try:
            # 모드 경로 설정
            mods_path = kwargs.get("mods_path", self.mods_path)
            if not mods_path:
                result.errors.append("모드 JAR 파일 경로가 지정되지 않았습니다.")
                return result

            mods_path = Path(mods_path)
            if not mods_path.exists():
                result.errors.append(f"모드 경로가 존재하지 않습니다: {mods_path}")
                return result

            # 모드 경로가 변경되었으면 재스캔
            if self.mods_path != mods_path:
                self.set_mods_path(mods_path)

            # /data 폴더 파일들 필터링
            data_files = self._filter_data_files(translated_files)
            if not data_files:
                result.errors.append("/data 폴더에 번역할 파일이 없습니다.")
                return result

            logger.info(f"/data 폴더 파일 {len(data_files)}개 발견")

            # 출력 디렉토리 생성
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # 모드별로 파일들 그룹화
            mod_groups = self._group_files_by_mod(data_files, mods_path)

            # 각 모드의 JAR 파일 수정
            modified_jars = []

            for mod_id, files in mod_groups.items():
                # kwargs에서 중복 매개변수 제거 (중복 방지)
                filtered_kwargs = {
                    k: v for k, v in kwargs.items() if k not in ["mods_path"]
                }

                jar_path = await self._modify_mod_jar(
                    mod_id,
                    files,
                    mods_path,
                    output_dir,
                    **filtered_kwargs,
                )
                if jar_path:
                    modified_jars.append(jar_path)
                    logger.info(f"모드 JAR 수정 완료: {jar_path}")

            if modified_jars:
                result.success = True
                result.file_count = len(data_files)
                # 첫 번째 수정된 JAR의 부모 디렉토리 (모드팩 폴더)를 반환
                first_jar_path = Path(modified_jars[0])
                modpack_dir = first_jar_path.parent.parent  # translated -> modpack_name
                result.output_path = modpack_dir
                logger.info(
                    f"JAR 수정 패키징 완료: {len(modified_jars)}개 JAR 파일 수정"
                )
            else:
                result.errors.append("수정된 JAR 파일이 없습니다.")

        except Exception as e:
            error_msg = f"JAR 수정 패키징 실패: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return result

    def _filter_data_files(self, translated_files: Dict[str, str]) -> Dict[str, str]:
        """./data 폴더에 포함된 파일들만 필터링합니다."""
        data_files = {}

        for original_path, translated_path in translated_files.items():
            if self._is_data_file(original_path):
                data_files[original_path] = translated_path

        return data_files

    def _is_data_file(self, file_path: str) -> bool:
        """파일이 /data 폴더에 포함되는지 확인합니다."""
        path_parts = Path(file_path).parts
        path_parts_lower = [part.lower() for part in path_parts]

        # kubejs가 경로에 없는 경우에만 data 폴더 확인
        if "kubejs" not in path_parts_lower:
            return "data" in path_parts_lower
        return False

    def _group_files_by_mod(
        self, data_files: Dict[str, str], mods_path: Path
    ) -> Dict[str, List[tuple]]:
        """파일들을 모드별로 그룹화합니다."""
        mod_groups = {}

        for original_path, translated_path in data_files.items():
            mod_id = self._extract_mod_id_from_data_path(original_path)
            if mod_id:
                # 해당 모드의 JAR 파일이 존재하는지 확인
                jar_file = self._find_mod_jar(mod_id, mods_path)
                if jar_file:
                    if mod_id not in mod_groups:
                        mod_groups[mod_id] = []
                    mod_groups[mod_id].append((original_path, translated_path))
                else:
                    logger.warning(f"모드 JAR 파일을 찾을 수 없음: {mod_id}")
            else:
                logger.warning(f"파일에서 모드 ID를 추출할 수 없음: {original_path}")

        return mod_groups

    def _scan_mod_jars(self) -> None:
        """모드 경로의 모든 JAR 파일을 스캔하여 모드 ID 매핑을 생성합니다."""
        if not self.mods_path or not self.mods_path.exists():
            logger.warning("모드 경로가 존재하지 않음")
            return

        logger.info(f"모드 JAR 파일 스캔 시작: {self.mods_path}")
        scanned_count = 0
        success_count = 0

        for jar_file in self.mods_path.glob("*.jar"):
            scanned_count += 1
            mod_ids = self._extract_mod_ids_from_jar(jar_file)

            if mod_ids:
                for mod_id in mod_ids:
                    self._mod_id_cache[mod_id] = jar_file
                    logger.debug(f"모드 ID 매핑: {mod_id} -> {jar_file.name}")
                success_count += 1
            else:
                logger.warning(f"모드 ID를 찾을 수 없음: {jar_file.name}")

        logger.info(
            f"모드 스캔 완료: {success_count}/{scanned_count}개 JAR 파일에서 모드 ID 추출"
        )

    def _extract_mod_ids_from_jar(self, jar_path: Path) -> List[str]:
        """JAR 파일에서 mods.toml을 읽어 모드 ID들을 추출합니다."""
        if tomllib is None:
            logger.warning("TOML 파서가 없어서 파일명 기반 추측 사용")
            return [self._guess_mod_id_from_filename(jar_path)]

        try:
            with zipfile.ZipFile(jar_path, "r") as jar:
                # META-INF/mods.toml 파일 찾기
                mods_toml_path = None
                for file_info in jar.infolist():
                    if file_info.filename.endswith("mods.toml"):
                        mods_toml_path = file_info.filename
                        break

                if not mods_toml_path:
                    logger.debug(f"mods.toml을 찾을 수 없음: {jar_path.name}")
                    return [self._guess_mod_id_from_filename(jar_path)]

                # mods.toml 내용 읽기
                with jar.open(mods_toml_path) as toml_file:
                    toml_content = toml_file.read().decode("utf-8")

                # TOML 파싱
                toml_data = tomllib.loads(toml_content)

                # 모드 ID들 추출
                mod_ids = []
                if "mods" in toml_data:
                    for mod in toml_data["mods"]:
                        if "modId" in mod:
                            mod_ids.append(mod["modId"])

                if mod_ids:
                    logger.debug(
                        f"{jar_path.name}에서 모드 ID 발견: {', '.join(mod_ids)}"
                    )
                    return mod_ids
                else:
                    logger.debug(
                        f"mods.toml에서 모드 ID를 찾을 수 없음: {jar_path.name}"
                    )
                    return [self._guess_mod_id_from_filename(jar_path)]

        except Exception as e:
            logger.warning(f"JAR 파일 분석 실패 ({jar_path.name}): {e}")
            return [self._guess_mod_id_from_filename(jar_path)]

    def _guess_mod_id_from_filename(self, jar_path: Path) -> str:
        """파일명에서 모드 ID를 추측합니다. (fallback)"""
        jar_name = jar_path.stem.lower()

        # 일반적인 버전 패턴 제거 (예: -1.20.1-1.0.0)
        import re

        mod_name = re.sub(r"-\d+\.\d+.*$", "", jar_name)
        mod_name = re.sub(r"_\d+\.\d+.*$", "", mod_name)

        return mod_name

    def _extract_mod_id_from_data_path(self, file_path: str) -> Optional[str]:
        """
        /data 폴더 경로에서 모드 ID를 추출합니다.
        예: /path/to/data/modid/recipes/recipe.json -> modid
        """
        path_parts = Path(file_path).parts

        # data 폴더 다음의 첫 번째 폴더가 모드 ID
        for i, part in enumerate(path_parts):
            if part.lower() == "data" and i + 1 < len(path_parts):
                return path_parts[i + 1]

        return None

    def _find_mod_jar(self, mod_id: str, mods_path: Path) -> Optional[Path]:
        """모드 ID에 해당하는 JAR 파일을 찾습니다."""
        # 재시도 횟수 확인 (무한 시도 방지)
        retry_count = self._mod_id_retry_count.get(mod_id, 0)
        if retry_count >= self._max_retry_attempts:
            logger.warning(
                f"모드 ID 찾기 최대 재시도 횟수 초과: {mod_id} (시도횟수: {retry_count})"
            )
            return None

        # 캐시된 모드 ID 매핑 사용
        if mod_id in self._mod_id_cache:
            jar_path = self._mod_id_cache[mod_id]
            if jar_path.exists():
                return jar_path
            else:
                logger.warning(f"캐시된 JAR 파일이 더 이상 존재하지 않음: {jar_path}")
                del self._mod_id_cache[mod_id]

        # 첫 번째 시도가 아니라면 재스캔하지 않음 (재시도 제한)
        if retry_count == 0:
            # 재시도 횟수 증가
            self._mod_id_retry_count[mod_id] = retry_count + 1

            # 캐시에 없으면 재스캔 후 다시 시도
            self._scan_mod_jars()

            if mod_id in self._mod_id_cache:
                return self._mod_id_cache[mod_id]

        # 여전히 찾을 수 없으면 fallback으로 파일명 기반 매칭 시도
        logger.warning(
            f"mods.toml에서 모드 ID를 찾을 수 없어서 파일명 기반 매칭 시도: {mod_id} (시도횟수: {retry_count + 1})"
        )

        for jar_file in mods_path.glob("*.jar"):
            jar_name = jar_file.stem.lower()

            # 모드 ID가 파일명에 포함되는지 확인
            if mod_id.lower() in jar_name:
                logger.info(f"파일명 기반 매칭 성공: {mod_id} -> {jar_file.name}")
                # 성공하면 캐시에 저장하고 재시도 카운터 초기화
                self._mod_id_cache[mod_id] = jar_file
                self._mod_id_retry_count.pop(mod_id, None)
                return jar_file

            # 언더스코어를 하이픈으로 변환해서 시도
            if mod_id.lower().replace("_", "-") in jar_name:
                logger.info(
                    f"파일명 기반 매칭 성공 (변환): {mod_id} -> {jar_file.name}"
                )
                # 성공하면 캐시에 저장하고 재시도 카운터 초기화
                self._mod_id_cache[mod_id] = jar_file
                self._mod_id_retry_count.pop(mod_id, None)
                return jar_file

            # 하이픈을 언더스코어로 변환해서 시도
            if mod_id.lower().replace("-", "_") in jar_name:
                logger.info(
                    f"파일명 기반 매칭 성공 (변환): {mod_id} -> {jar_file.name}"
                )
                # 성공하면 캐시에 저장하고 재시도 카운터 초기화
                self._mod_id_cache[mod_id] = jar_file
                self._mod_id_retry_count.pop(mod_id, None)
                return jar_file

        # 실패한 경우 재시도 카운터 증가
        self._mod_id_retry_count[mod_id] = retry_count + 1
        logger.warning(
            f"모드 JAR 파일을 찾을 수 없음: {mod_id} (시도횟수: {retry_count + 1})"
        )
        return None

    async def _modify_mod_jar(
        self,
        mod_id: str,
        files: List[tuple],
        mods_path: Path,
        output_dir: Path,
        **kwargs,
    ) -> Optional[Path]:
        """모드 JAR 파일을 수정합니다."""
        try:
            # 원본 JAR 파일 찾기
            original_jar = self._find_mod_jar(mod_id, mods_path)
            if not original_jar:
                logger.error(f"모드 JAR 파일을 찾을 수 없음: {mod_id}")
                return None

            # 모드팩 이름과 언어 기반 폴더 구조 생성
            modpack_name = kwargs.get("modpack_name", "Unknown_Modpack")
            lang_name = self._get_language_name(self.target_lang)
            overwrite_folder_name = f"{modpack_name}_{lang_name}_덮어쓰기"
            overwrite_dir = output_dir / overwrite_folder_name

            # mods 폴더 생성 (덮어쓰기 폴더 안에)
            mods_dir = overwrite_dir / "mods"
            mods_dir.mkdir(parents=True, exist_ok=True)

            # 출력 JAR 파일 경로 (mods 폴더에)
            output_jar = mods_dir / f"{original_jar.stem}_korean_modified.jar"

            # 임시 디렉토리에서 JAR 파일 수정
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # 원본 JAR 파일을 임시 디렉토리에 복사
                temp_jar = temp_path / "temp.jar"
                shutil.copy2(original_jar, temp_jar)

                # JAR 파일 수정
                modified = await self._inject_files_to_jar(temp_jar, files)

                if modified:
                    # 수정된 JAR 파일을 출력 위치로 이동
                    shutil.move(temp_jar, output_jar)
                    logger.info(f"수정된 JAR 생성: {output_jar}")
                    return output_jar
                else:
                    logger.error(f"JAR 파일 수정 실패: {mod_id}")
                    return None

        except Exception as e:
            logger.error(f"모드 JAR 수정 중 오류 발생 ({mod_id}): {e}")
            return None

    async def _inject_files_to_jar(self, jar_path: Path, files: List[tuple]) -> bool:
        """JAR 파일에 번역된 파일들을 주입합니다."""
        try:
            # 새로운 임시 JAR 파일 생성
            temp_jar = jar_path.with_suffix(".temp.jar")

            # 번역될 파일들의 JAR 내부 경로 미리 계산
            translation_paths = set()
            for original_path, _ in files:
                jar_internal_path = self._get_jar_internal_path(original_path)
                if jar_internal_path:
                    translation_paths.add(jar_internal_path)

            with zipfile.ZipFile(jar_path, "r") as source_jar:
                with zipfile.ZipFile(temp_jar, "w", zipfile.ZIP_DEFLATED) as target_jar:
                    # 1단계: 번역된 파일들 먼저 추가
                    for original_path, translated_path in files:
                        jar_internal_path = self._get_jar_internal_path(original_path)
                        if jar_internal_path:
                            try:
                                # 번역된 파일을 JAR에 먼저 추가
                                with open(translated_path, "rb") as f:
                                    translated_data = f.read()
                                target_jar.writestr(jar_internal_path, translated_data)
                                logger.debug(
                                    f"JAR에 번역 파일 추가: {jar_internal_path}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"번역 파일 추가 실패 ({jar_internal_path}): {e}"
                                )

                    # 2단계: 기존 JAR 내용 복사 (이미 추가된 번역 파일은 제외)
                    for item in source_jar.infolist():
                        # 디렉토리는 건너뛰기
                        if item.filename.endswith("/"):
                            continue

                        # 이미 번역된 파일이 추가되었으면 건너뛰기 (중복 방지)
                        if item.filename in translation_paths:
                            logger.debug(
                                f"번역 파일로 이미 교체됨, 원본 건너뛰기: {item.filename}"
                            )
                            continue

                        try:
                            data = source_jar.read(item.filename)
                            target_jar.writestr(item.filename, data)
                        except Exception as e:
                            logger.warning(f"파일 복사 실패 ({item.filename}): {e}")

            # 임시 파일을 원본으로 교체
            temp_jar.replace(jar_path)
            return True

        except Exception as e:
            logger.error(f"JAR 파일 주입 실패: {e}")
            if temp_jar.exists():
                temp_jar.unlink()
            return False

    def _get_jar_internal_path(self, original_path: str) -> Optional[str]:
        """
        원본 파일 경로를 JAR 내부 경로로 변환합니다.
        예: /path/to/data/modid/recipes/recipe.json -> data/modid/recipes/recipe.json
        """
        path_parts = Path(original_path).parts

        # data 폴더부터 시작하는 상대 경로 생성
        for i, part in enumerate(path_parts):
            if part.lower() == "data":
                # data 폴더부터의 경로를 반환
                internal_parts = path_parts[i:]
                # 언어 코드 변환 적용
                internal_path = str(Path(*internal_parts))
                return self._convert_language_path(internal_path)

        return None

    def get_supported_file_patterns(self) -> List[str]:
        """지원하는 파일 패턴 목록을 반환합니다."""
        return [
            "*/data/*/lang/*.json",
            "*/data/*/recipes/*.json",
            "*/data/*/advancements/*.json",
            "*/data/*/loot_tables/*.json",
            "*/data/*/tags/*.json",
        ]

    def set_mods_path(self, mods_path: Path) -> None:
        """모드 JAR 파일 경로를 설정합니다."""
        self.mods_path = Path(mods_path)
        logger.info(f"모드 경로 설정: {self.mods_path}")

        # 경로가 변경되면 캐시 및 재시도 카운터 초기화 후 재스캔
        self._mod_id_cache.clear()
        self._mod_id_retry_count.clear()
        if self.mods_path.exists():
            self._scan_mod_jars()
        else:
            logger.warning(f"설정된 모드 경로가 존재하지 않음: {self.mods_path}")

    def list_modifiable_mods(self, translated_files: Dict[str, str]) -> Set[str]:
        """수정 가능한 모드 목록을 반환합니다."""
        data_files = self._filter_data_files(translated_files)
        mod_ids = set()

        for original_path in data_files.keys():
            mod_id = self._extract_mod_id_from_data_path(original_path)
            if mod_id and self.mods_path:
                jar_file = self._find_mod_jar(mod_id, self.mods_path)
                if jar_file:
                    mod_ids.add(mod_id)

        return mod_ids

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
