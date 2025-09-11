"""
FTBQuests 챕터 파일을 번역키로 변환하고 리소스팩 JSON을 생성하는 모듈

특정 폴더의 FTBQuests 챕터들을 스캔하여:
1. 번역 가능한 텍스트를 {autotranslate.key.path} 형태의 번역키로 변환
2. 원본 텍스트와 번역키를 매핑하는 리소스팩 JSON 파일 생성
3. Java 번역 시스템의 % 문자 이스케이프 처리
"""

import logging
from pathlib import Path
from typing import Dict, Set

from ..filters.ftbquests import FTBQuestsFilter
from ..parsers.snbt import SNBTParser

logger = logging.getLogger(__name__)


class FTBQuestsConverter:
    """FTBQuests 챕터를 번역키로 변환하는 클래스"""

    def __init__(self, chapters_folder: Path):
        """
        Args:
            chapters_folder: FTBQuests 챕터 폴더 경로
        """
        self.chapters_folder = Path(chapters_folder)
        self.filter = FTBQuestsFilter()
        self.translation_keys: Dict[str, str] = {}  # 번역키 -> 원본 텍스트
        self.used_keys: Set[str] = set()  # 중복 방지용

    def _is_already_translation_key(self, text: str) -> bool:
        """
        텍스트가 이미 번역키 형태인지 확인합니다.

        Args:
            text: 확인할 텍스트

        Returns:
            bool: 이미 번역키 형태이면 True
        """
        if not isinstance(text, str):
            return False

        text = text.strip()
        return (text.startswith("{") and text.endswith("}")) or (
            text.startswith("[") and text.endswith("]")
        )

    def _escape_percent_characters(self, text: str) -> str:
        """
        Java 번역 시스템에서 % 문자를 이스케이프 처리합니다.

        Java의 번역 처리에서 '%' 문자는 특별한 의미를 가지므로 (예: %s는 문자열 매개변수 대체)
        리터럴 '%'는 '%%'로 이스케이프해야 합니다.

        Args:
            text: 처리할 텍스트

        Returns:
            % 문자가 이스케이프된 텍스트
        """
        if not isinstance(text, str):
            return text

        # 이미 이스케이프된 %% 는 임시로 플레이스홀더로 변경
        placeholder = "___ESCAPED_PERCENT___"
        text = text.replace("%%", placeholder)

        # 홀로 있는 % 를 %% 로 변경
        text = text.replace("%", "%%")

        # 플레이스홀더를 다시 %% 로 복원
        text = text.replace(placeholder, "%%")

        return text

    async def convert_all_chapters(self, save=True) -> bool:
        """모든 챕터 파일을 변환합니다"""
        try:
            # 챕터 폴더 확인
            if not self.chapters_folder.exists():
                logger.error(f"챕터 폴더가 존재하지 않습니다: {self.chapters_folder}")
                return False

            # SNBT 파일들 찾기
            snbt_files = list(self.chapters_folder.glob("*.snbt"))
            if not snbt_files:
                logger.warning(
                    f"챕터 폴더에 SNBT 파일이 없습니다: {self.chapters_folder}"
                )
                return False

            logger.info(f"{len(snbt_files)}개의 챕터 파일을 처리합니다")

            # 각 챕터 파일 처리
            for snbt_file in snbt_files:
                await self._convert_chapter_file(snbt_file, save)

            return await self._generate_resourcepack_json()

        except Exception as e:
            logger.error(f"챕터 변환 중 오류 발생: {e}")
            return False

    async def check_translation_key_coverage(self, threshold: float = 0.5) -> bool:
        """
        FTBQuests 챕터들이 번역키로 변환되어있는지 확인합니다.

        Args:
            threshold: 번역키 변환 기준 (기본값: 0.5 = 50%)

        Returns:
            bool: 지정된 비율 이상 번역키로 변환되어있으면 True
        """
        try:
            # 챕터 폴더 확인
            if not self.chapters_folder.exists():
                logger.error(f"챕터 폴더가 존재하지 않습니다: {self.chapters_folder}")
                return False

            # SNBT 파일들 찾기
            snbt_files = list(self.chapters_folder.glob("*.snbt"))
            if not snbt_files:
                logger.warning(
                    f"챕터 폴더에 SNBT 파일이 없습니다: {self.chapters_folder}"
                )
                return False

            total_texts = 0
            translated_texts = 0

            # 각 챕터 파일의 번역키 변환 상태 확인
            for snbt_file in snbt_files:
                try:
                    # 파일 파싱
                    parser = SNBTParser(snbt_file)
                    data = await parser.parse()

                    if not isinstance(data, dict):
                        logger.warning(f"파일이 딕셔너리 형식이 아닙니다: {snbt_file}")
                        continue

                    # 재귀적으로 텍스트 확인
                    file_total, file_translated = (
                        self._count_translation_keys_recursive(data)
                    )
                    total_texts += file_total
                    translated_texts += file_translated

                except Exception as e:
                    logger.error(f"챕터 파일 확인 실패 ({snbt_file}): {e}")
                    continue

            # 변환 비율 계산
            if total_texts == 0:
                logger.warning("번역 대상 텍스트가 없습니다.")
                return False

            coverage_ratio = translated_texts / total_texts
            logger.info(
                f"번역키 변환 상태: {translated_texts}/{total_texts} ({coverage_ratio:.2%})"
            )

            return coverage_ratio >= threshold

        except Exception as e:
            logger.error(f"번역키 변환 상태 확인 중 오류 발생: {e}")
            return False

    def _count_translation_keys_recursive(self, data) -> tuple[int, int]:
        """
        재귀적으로 데이터를 순회하며 번역키 변환 상태를 확인합니다.

        Args:
            data: 분석할 데이터

        Returns:
            tuple[int, int]: (전체 텍스트 수, 번역키로 변환된 텍스트 수)
        """
        total_texts = 0
        translated_texts = 0

        if isinstance(data, dict):
            for key, value in data.items():
                # 번역 대상 필드인지 확인
                if self.filter.should_translate_key(key):
                    if isinstance(value, str) and value.strip():
                        total_texts += 1
                        # 번역키 형태인지 확인 ({autotranslate.~~~} 패턴)
                        if self._is_already_translation_key(value):
                            translated_texts += 1
                # 재귀적으로 하위 데이터 확인
                elif isinstance(value, (dict, list)):
                    sub_total, sub_translated = self._count_translation_keys_recursive(
                        value
                    )
                    total_texts += sub_total
                    translated_texts += sub_translated

        elif isinstance(data, list):
            for item in data:
                sub_total, sub_translated = self._count_translation_keys_recursive(item)
                total_texts += sub_total
                translated_texts += sub_translated

        return total_texts, translated_texts

    def _process_data_recursive(
        self, data: Dict, chapter_name: str, key_prefix: str = ""
    ) -> Dict:
        """재귀적으로 데이터를 처리하여 번역키로 변환"""
        if not isinstance(data, dict):
            return data

        result = {}

        for key, value in data.items():
            full_key = f"{key_prefix}.{key}" if key_prefix else key

            if isinstance(value, str):
                # 문자열이고 번역 대상인 경우
                if self.filter.should_translate_key(full_key) and value.strip():
                    # 이미 번역키 형태인 경우 그대로 유지
                    if self._is_already_translation_key(value):
                        result[key] = value
                    # JSON 형태 텍스트 처리
                    elif self.filter._is_json_text(value):
                        json_text = self.filter._extract_json_text(value)
                        if json_text.strip():
                            # JSON 텍스트가 이미 번역키 형태인지 확인
                            if self._is_already_translation_key(json_text):
                                result[key] = value
                            else:
                                # % 문자 이스케이프 처리
                                escaped_text = self._escape_percent_characters(
                                    json_text
                                )
                                translation_key = self._generate_translation_key(
                                    chapter_name, full_key
                                )
                                self.translation_keys[translation_key] = escaped_text
                                # JSON에서 text 필드를 번역키로 교체
                                translated_json = self.filter._reconstruct_json_text(
                                    value, f"{{{translation_key}}}"
                                )
                                result[key] = translated_json
                        else:
                            result[key] = value
                    else:
                        # 일반 텍스트 - % 문자 이스케이프 처리
                        escaped_text = self._escape_percent_characters(value)
                        translation_key = self._generate_translation_key(
                            chapter_name, full_key
                        )
                        self.translation_keys[translation_key] = escaped_text
                        result[key] = f"{{{translation_key}}}"
                else:
                    result[key] = value

            elif isinstance(value, dict):
                # 중첩된 딕셔너리 재귀 처리
                result[key] = self._process_data_recursive(
                    value, chapter_name, full_key
                )

            elif isinstance(value, list):
                # 리스트 처리
                result_list = []
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        result_list.append(
                            self._process_data_recursive(
                                item, chapter_name, f"{full_key}[{i}]"
                            )
                        )
                    elif isinstance(item, str) and self.filter.should_translate_key(
                        full_key
                    ):
                        if item.strip():
                            # 이미 번역키 형태인 경우 그대로 유지
                            if self._is_already_translation_key(item):
                                result_list.append(item)
                            # JSON 형태 텍스트 처리
                            elif self.filter._is_json_text(item):
                                json_text = self.filter._extract_json_text(item)
                                if json_text.strip():
                                    # JSON 텍스트가 이미 번역키 형태인지 확인
                                    if self._is_already_translation_key(json_text):
                                        result_list.append(item)
                                    else:
                                        # % 문자 이스케이프 처리
                                        escaped_text = self._escape_percent_characters(
                                            json_text
                                        )
                                        translation_key = (
                                            self._generate_translation_key(
                                                chapter_name, f"{full_key}[{i}]"
                                            )
                                        )
                                        self.translation_keys[translation_key] = (
                                            escaped_text
                                        )
                                        translated_json = (
                                            self.filter._reconstruct_json_text(
                                                item, f"{{{translation_key}}}"
                                            )
                                        )
                                        result_list.append(translated_json)
                                else:
                                    result_list.append(item)
                            else:
                                # 일반 텍스트 - % 문자 이스케이프 처리
                                escaped_text = self._escape_percent_characters(item)
                                translation_key = self._generate_translation_key(
                                    chapter_name, f"{full_key}[{i}]"
                                )
                                self.translation_keys[translation_key] = escaped_text
                                result_list.append(f"{{{translation_key}}}")
                        else:
                            result_list.append(item)
                    else:
                        result_list.append(item)
                result[key] = result_list

            else:
                result[key] = value

        return result

    async def _convert_chapter_file(self, file_path: Path, save=True) -> None:
        """개별 챕터 파일을 변환합니다"""
        try:
            logger.debug(f"챕터 파일 처리 중: {file_path.name}")

            # 파일 파싱
            parser = SNBTParser(file_path)
            data = await parser.parse()

            if not isinstance(data, dict):
                logger.warning(f"파일이 딕셔너리 형식이 아닙니다: {file_path}")
                return

            # 번역 대상 텍스트 추출 및 변환
            updated_data = self._process_data_recursive(data, file_path.stem, "")

            # 변경사항이 있으면 파일 저장
            if updated_data != data:
                if save:
                    await parser.dump(updated_data)
                logger.debug(f"챕터 파일 업데이트 완료: {file_path.name}")

        except Exception as e:
            logger.error(f"챕터 파일 처리 실패 ({file_path}): {e}")

    def _generate_translation_key(self, chapter_name: str, key_path: str) -> str:
        """번역키를 생성합니다"""
        # 챕터명과 키 경로를 조합하여 번역키 생성
        base_key = f"autotranslate.ftbquests.{chapter_name}.{key_path}"

        # 특수문자 정리
        translation_key = (
            base_key.replace("[", "_").replace("]", "").replace("-", "_").lower()
        )

        # 중복 방지
        original_key = translation_key
        counter = 1
        while translation_key in self.used_keys:
            translation_key = f"{original_key}_{counter}"
            counter += 1

        self.used_keys.add(translation_key)
        return translation_key

    async def _generate_resourcepack_json(self) -> Dict[str, str]:
        """리소스팩 JSON을 생성합니다"""
        try:
            # 번역 데이터 정리
            translation_data = {
                key: original_text
                for key, original_text in self.translation_keys.items()
            }

            return translation_data
        except Exception as e:
            logger.error(f"리소스팩 JSON 생성 실패: {e}")
            return {}


async def convert_ftbquests_chapters(chapters_folder: str | Path, save=True) -> bool:
    """
    FTBQuests 챕터들을 번역키로 변환하는 메인 함수

    Args:
        chapters_folder: FTBQuests 챕터 폴더 경로

    Returns:
        변환 성공 여부
    """
    converter = FTBQuestsConverter(Path(chapters_folder))
    return await converter.convert_all_chapters(save)


async def check_ftbquests_translation_key_coverage(chapters_folder: str | Path) -> bool:
    """
    FTBQuests 챕터들이 번역키로 변환되어있는지 확인합니다.
    """
    converter = FTBQuestsConverter(Path(chapters_folder))
    return await converter.check_translation_key_coverage()
