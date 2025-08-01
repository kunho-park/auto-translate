"""
모드팩 통합 번역 모듈

모드팩 전체의 번역 파일들을 수집, 통합, 번역하고 패키징하는 고수준 번역기입니다.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles

from ..filters import ExtendedFilterManager
from ..modpack.load import ModpackLoader
from ..parsers.base import BaseParser
from .json_translator import JSONTranslator

logger = logging.getLogger(__name__)


class ModpackTranslator:
    """모드팩 전체를 통합 번역하는 클래스"""

    def __init__(
        self,
        modpack_path: str,
        glossary_path: str = "./glossary.json",
        source_lang: str = "en_us",
        target_language: str = "한국어",
        max_concurrent_requests: int = 3,
        delay_between_requests_ms: int = 500,
        progress_callback: Optional[callable] = None,
        translate_config: bool = True,
        translate_kubejs: bool = True,
        translate_mods: bool = True,
        translate_resourcepacks: bool = True,
        translate_patchouli_books: bool = True,
        translate_ftbquests: bool = True,
    ):
        self.modpack_path = modpack_path
        self.glossary_path = glossary_path
        self.source_lang = source_lang
        self.target_language = target_language
        self.max_concurrent_requests = max_concurrent_requests
        self.delay_between_requests_ms = delay_between_requests_ms
        self.progress_callback = progress_callback

        # 타겟 언어 코드 변환
        target_lang_code = self._convert_language_to_code(target_language)

        # 컴포넌트 초기화 (타겟 언어 추가)
        self.loader = ModpackLoader(
            modpack_path,
            source_lang=source_lang,
            target_lang=target_lang_code,  # 타겟 언어 추가
            progress_callback=progress_callback,
            translate_mods=translate_mods,
            translate_config=translate_config,
            translate_kubejs=translate_kubejs,
            translate_resourcepacks=translate_resourcepacks,
            translate_patchouli_books=translate_patchouli_books,
            translate_ftbquests=translate_ftbquests,
        )
        self.filter_manager = ExtendedFilterManager()
        self.translator = JSONTranslator(glossary_path=glossary_path)

        # 통합 번역 데이터
        self.integrated_data: Dict[str, str] = {}
        self.translation_map: Dict[str, List[Dict]] = {}  # 키별 원본 위치 추적
        self.existing_translations: Dict[str, str] = {}  # 기존 번역 데이터

        logger.info(
            f"ModpackTranslator 초기화 - 동시 요청: {max_concurrent_requests}, 요청 간 지연: {delay_between_requests_ms}ms"
        )
        logger.info(f"타겟 언어: {target_language} ({target_lang_code})")

    async def collect_all_translations(
        self,
        selected_files: Optional[List[str]] = None,
        selected_glossary_files: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        모드팩에서 번역 대상을 수집하고 통합합니다.
        selected_files가 제공되면 해당 파일들만 처리하고, 그렇지 않으면 전체를 스캔합니다.
        """
        logger.info(f"{len(selected_files)}개의 선택된 파일에 대한 번역 대상 수집 시작")
        if not self.loader.translation_files:
            logger.info("초기 파일 목록이 없습니다. 전체 파일을 먼저 스캔합니다.")
            self.loader.load_translation_files()

        all_files_map = {
            f["input"].replace("\\", "/"): f for f in self.loader.translation_files
        }
        translation_files = [
            all_files_map[path.replace("\\", "/")]
            for path in selected_files
            if path.replace("\\", "/") in all_files_map
        ]

        glossary_files = [
            all_files_map[path.replace("\\", "/")]
            for path in selected_glossary_files
            if path.replace("\\", "/") in all_files_map
        ]

        logger.info(f"필터링 후 {len(translation_files)}개의 파일을 처리합니다.")

        # 기존 번역 데이터 저장
        self.existing_translations = self.loader.get_all_existing_translations()
        if self.existing_translations:
            logger.info(f"기존 번역 데이터 {len(self.existing_translations)}개 발견")

        # 진행률 업데이트
        if self.progress_callback:
            msg = f"총 {len(translation_files)}개 파일 발견"
            if self.existing_translations:
                msg += f", 기존 번역 {len(self.existing_translations)}개 발견"
            self.progress_callback(
                "파일 수집 완료",
                0,
                len(translation_files),
                msg,
            )

        # 2. 파일들을 청크로 나누어 병렬 처리 (너무 많으면 메모리 부족 방지)
        chunk_size = 5  # 한 번에 처리할 파일 수 (테스트용으로 줄임)
        all_entries = []

        logger.info(
            f"번역 데이터 추출 시작 - 총 {len(translation_files)}개 파일 처리 예정"
        )

        # 소스 언어 파일만 필터링 (번역 대상)
        source_files = [
            f for f in translation_files if f.get("lang_type", "other") == "source"
        ]

        if len(source_files) != len(translation_files):
            logger.info(
                f"소스 언어 파일만 필터링: {len(source_files)}/{len(translation_files)}개 파일"
            )

        # 소스 파일들을 청크로 나누어 처리
        for i in range(0, len(source_files), chunk_size):
            chunk = source_files[i : i + chunk_size]

            # 현재 청크의 파일들을 병렬 처리
            chunk_tasks = [
                self._process_single_file(file_info["input"]) for file_info in chunk
            ]

            # 병렬 실행
            try:
                chunk_results = await asyncio.gather(
                    *chunk_tasks, return_exceptions=True
                )
            except Exception as e:
                logger.error(f"청크 처리 실패: {e}")
                chunk_results = [e] * len(chunk_tasks)

            # 결과 수집 (예외 처리)
            for file_info, result in zip(chunk, chunk_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"파일 처리 실패 ({Path(file_info['input']).name}): {result}"
                    )
                elif result:
                    all_entries.extend(result)

            # 진행률 콜백 호출
            processed_count = min(i + chunk_size, len(source_files))
            if self.progress_callback:
                self.progress_callback(
                    "번역 데이터 추출 중",
                    processed_count,
                    len(source_files),
                    f"번역 데이터 추출: {processed_count}/{len(source_files)} 파일 ({len(all_entries)}개 항목)",
                )

        logger.info(f"총 {len(all_entries)}개 번역 항목 수집됨")

        glossary_source_files = [
            f for f in glossary_files if f.get("lang_type", "other") == "source"
        ]

        self.glossary_text = ""

        if len(glossary_source_files) != len(selected_glossary_files):
            logger.info(
                f"사전 파일만 필터링: {len(glossary_source_files)}/{len(selected_glossary_files)}개 파일"
            )

        # 소스 파일들을 청크로 나누어 처리
        for i in range(0, len(glossary_source_files), chunk_size):
            chunk = glossary_source_files[i : i + chunk_size]

            # 현재 청크의 파일들을 병렬 처리
            chunk_tasks = [
                self._process_single_file(file_info["input"]) for file_info in chunk
            ]

            # 병렬 실행
            try:
                chunk_results = await asyncio.gather(
                    *chunk_tasks, return_exceptions=True
                )
            except Exception as e:
                logger.error(f"청크 처리 실패: {e}")
                chunk_results = [e] * len(chunk_tasks)

            # 결과 수집 (예외 처리)
            for file_info, result in zip(chunk, chunk_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"파일 처리 실패 ({Path(file_info['input']).name}): {result}"
                    )
                elif result:
                    self.glossary_text += "\n\n" + "\n".join(
                        str(i.original_text) for i in result
                    )

            # 진행률 콜백 호출
            processed_count = min(i + chunk_size, len(glossary_source_files))
            if self.progress_callback:
                self.progress_callback(
                    "사전 데이터 추출 중",
                    processed_count,
                    len(glossary_source_files),
                    f"사전 데이터 추출: {processed_count}/{len(glossary_source_files)} 파일",
                )

        # 3. 중복 제거 및 고유 엔트리만 남기기
        if self.progress_callback:
            self.progress_callback(
                "데이터 통합 시작",
                0,
                0,
                "중복 데이터를 제거하고 번역 데이터를 통합하고 있습니다...",
            )

        logger.info(f"통합 처리할 항목 수: {len(all_entries)}")

        # # puffish_skills 관련 항목만 필터링
        # puffish_entries = []
        # for entry in all_entries:
        #     if "kubejs" in entry.file_type.lower():
        #         puffish_entries.append(entry)

        # logger.info(
        #     f"puffish_skills 관련 항목만 필터링: {len(puffish_entries)}/{len(all_entries)}개 항목"
        # )
        # all_entries = puffish_entries

        # 통합 처리 실행
        self._integrate_translation_entries(all_entries)

        logger.info(
            f"통합 완료: {len(self.integrated_data)}개 항목이 self.integrated_data에 저장됨"
        )

        # 디버깅: 일부 샘플 확인
        if self.integrated_data:
            sample_keys = list(self.integrated_data.keys())[:3]
            for key in sample_keys:
                logger.debug(
                    f"샘플 데이터 - 키: {key}, 값: {self.integrated_data[key][:50]}..."
                )
        # # 통합된 데이터가 1000개를 초과하면 상위 1000개만 유지
        # if len(self.integrated_data) > 100:
        #     logger.info(
        #         f"통합 데이터가 1000개를 초과하여 상위 1000개만 유지 (원본: {len(self.integrated_data)}개)"
        #     )
        #     # 딕셔너리를 아이템 리스트로 변환 후 상위 1000개 슬라이싱
        #     top_1000 = dict(list(self.integrated_data.items())[:1000])
        #     self.integrated_data = top_1000
        return self.integrated_data

    async def _process_single_file(self, file_path: str) -> List:
        """개별 파일을 비동기로 처리"""
        try:
            file_name = Path(file_path).name
            logger.debug(f"파일 처리 시작: {file_name}")

            # 적용 가능한 필터 찾기
            logger.debug(f"필터 검색 중: {file_name}")
            applicable_filters = self.filter_manager.get_applicable_filters(file_path)

            if not applicable_filters:
                logger.debug(f"적용 가능한 필터 없음: {file_name}")
                return []

            # 가장 높은 우선순위 필터 사용
            primary_filter = applicable_filters[0]
            logger.debug(f"필터 선택됨: {file_name} -> {type(primary_filter).__name__}")

            # 번역 항목 추출 (비동기 함수이므로 직접 await 사용)
            logger.debug(f"번역 항목 추출 시작: {file_name}")

            entries = await primary_filter.extract_translations(file_path)

            logger.debug(f"번역 항목 추출 완료: {file_name}")

            if entries:
                logger.debug(f"{file_name}: {len(entries)}개 항목 추출됨")

            return entries

        except Exception as e:
            logger.error(f"파일 처리 실패 ({Path(file_path).name}): {e}")
            import traceback

            logger.error(f"트레이스백: {traceback.format_exc()}")
            return []

    def _integrate_translation_entries(self, entries: List):
        """번역 항목들을 통합하여 중복 제거 및 우선순위 적용"""
        logger.info(f"통합 처리 시작: {len(entries)}개 항목")

        # 키별로 그룹화 및 우선순위 적용
        key_groups = {}
        empty_text_count = 0
        processed_count = 0

        for entry in entries:
            processed_count += 1

            # 파일별로 고유한 키 생성 (전체 파일경로 + 원본키)
            # 모드팩 경로를 기준으로 상대 경로 생성하여 고유성 보장
            try:
                # 모드팩 경로를 기준으로 상대 경로 계산
                relative_path = Path(entry.file_path).relative_to(
                    Path(self.modpack_path)
                )
                file_identifier = str(relative_path).replace("\\", "/")  # Windows 호환
            except ValueError:
                # 상대 경로 계산이 실패하면 전체 경로 사용
                file_identifier = str(Path(entry.file_path)).replace("\\", "/")

            unique_key = f"{file_identifier}|{entry.key}"
            text = entry.original_text.strip() if entry.original_text else ""

            if not text:  # 빈 텍스트는 제외
                empty_text_count += 1
                if empty_text_count <= 5:  # 처음 5개만 로그
                    logger.debug(
                        f"빈 텍스트 제외: {unique_key}, 원본: '{entry.original_text}'"
                    )
                continue

            if unique_key not in key_groups:
                key_groups[unique_key] = []

            key_groups[unique_key].append(entry)

        logger.info(
            f"처리 완료: {processed_count}개 항목 중 {empty_text_count}개 빈 텍스트 제외, {len(key_groups)}개 유효 그룹"
        )

        # 각 키에 대해 가장 높은 우선순위 항목 선택
        added_count = 0
        for unique_key, group in key_groups.items():
            # 우선순위순으로 정렬 (높은 우선순위 먼저)
            group.sort(key=lambda x: x.priority, reverse=True)

            best_entry = group[0]
            text = best_entry.original_text.strip()

            # 통합 데이터에 추가 (고유 키 사용)
            self.integrated_data[unique_key] = text
            added_count += 1

            # 원본 위치 추적 정보 저장
            self.translation_map[unique_key] = [
                {
                    "file_path": entry.file_path,
                    "file_type": entry.file_type,
                    "context": entry.context,
                    "priority": entry.priority,
                    "original_key": entry.key,  # 원본 키 정보도 저장
                }
                for entry in group
            ]

        logger.info(f"통합 데이터 생성 완료: {added_count}개 항목 추가")

        # 샘플 데이터 출력
        if self.integrated_data:
            sample_items = list(self.integrated_data.items())[:3]
            for key, value in sample_items:
                logger.debug(f"통합 샘플 - '{key}': '{value[:50]}...'")
        else:
            logger.warning("통합 데이터가 비어있습니다!")

    async def translate_integrated_data(
        self,
        max_retries: int = 5,
        max_tokens_per_chunk: int = 2000,
        use_glossary: bool = True,
        use_vanilla_glossary: bool = True,
        vanilla_glossary_path: Optional[str] = None,
        llm_provider: str = "gemini",
        llm_model: str = "gemini-1.5-flash",
        temperature: float = 0.1,
        enable_quality_review: bool = True,
        final_fallback_max_retries: int = 2,
        max_quality_retries: int = 1,
        selected_glossary_files: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """통합된 번역 데이터를 번역"""
        logger.info("통합 번역 데이터 번역 시작")

        if not self.integrated_data:
            logger.warning("번역할 데이터가 없습니다.")
            return {}

        # 진행률 콜백 호출
        total_items = len(self.integrated_data)
        if self.progress_callback:
            self.progress_callback(
                "번역 시작", 0, total_items, f"총 {total_items}개 항목 번역 시작"
            )

        # JSONTranslator로 번역 (ModpackTranslator의 설정 사용)
        translated_result = await self.translator.translate(
            self.integrated_data,
            glossary_text=self.glossary_text,
            target_language=self.target_language,
            max_retries=max_retries,
            max_tokens_per_chunk=max_tokens_per_chunk,
            use_glossary=use_glossary,
            use_vanilla_glossary=use_vanilla_glossary,
            vanilla_glossary_path=vanilla_glossary_path,
            max_concurrent_requests=self.max_concurrent_requests,
            delay_between_requests_ms=self.delay_between_requests_ms,
            progress_callback=self.progress_callback,  # 진행률 콜백 전달
            existing_translations=self.existing_translations,  # 기존 번역 데이터 전달
            llm_provider=llm_provider,
            llm_model=llm_model,
            temperature=temperature,
            enable_quality_review=enable_quality_review,
            final_fallback_max_retries=final_fallback_max_retries,
            max_quality_retries=max_quality_retries,
        )

        # 결과가 문자열인 경우 JSON으로 파싱
        if isinstance(translated_result, str):
            translated_result = json.loads(translated_result)

        logger.info(f"번역 완료: {len(translated_result)}개 항목")

        # 번역 완료 콜백
        if self.progress_callback:
            self.progress_callback(
                "번역 완료",
                len(translated_result),
                total_items,
                f"번역 완료: {len(translated_result)}개 항목",
            )

        return translated_result

    async def apply_translations_to_files(
        self,
        translated_data: Dict[str, str],
        output_dir: Optional[str] = None,
        backup_originals: bool = True,
    ) -> Dict[str, int]:
        """번역된 데이터를 원본 파일들에 적용 (병렬 처리)"""
        logger.info("번역 데이터를 원본 파일들에 적용 시작")

        if not translated_data:
            logger.warning("적용할 번역 데이터가 없습니다.")
            return {}

        # 번역 데이터를 파일별로 그룹화
        file_groups = self._group_translations_by_file(translated_data)

        # 출력 디렉토리가 지정된 경우 원본 파일들을 먼저 복사
        if output_dir:
            logger.info(f"원본 파일들을 출력 디렉토리로 복사 중: {output_dir}")
            await self._copy_files_to_output_dir(file_groups.keys(), output_dir)

        # 파일들을 청크로 나누어 병렬 처리
        chunk_size = 20  # 파일 업데이트는 좀 더 보수적으로
        update_stats = {}

        file_items = list(file_groups.items())

        for i in range(0, len(file_items), chunk_size):
            chunk = file_items[i : i + chunk_size]

            # 현재 청크의 파일들을 병렬 처리
            chunk_tasks = [
                self._process_file_update(
                    file_path, file_translations, output_dir, backup_originals
                )
                for file_path, file_translations in chunk
            ]

            # 병렬 실행
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)

            # 결과 수집
            for (file_path, _), result in zip(chunk, chunk_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"파일 업데이트 실패 ({Path(file_path).name}): {result}"
                    )
                elif result > 0:
                    update_stats[file_path] = result
                    logger.debug(f"{Path(file_path).name}: {result}개 항목 업데이트")

            # 진행률 출력
            processed_count = min(i + chunk_size, len(file_items))
            logger.info(f"진행률: {processed_count}/{len(file_items)} 파일 처리됨")

        logger.info(f"총 {len(update_stats)}개 파일에 번역 적용 완료")
        return update_stats

    async def _copy_files_to_output_dir(self, file_paths: list, output_dir: str):
        """원본 파일들을 출력 디렉토리로 복사 (병렬 처리)"""
        copy_tasks = []

        for file_path in file_paths:
            target_path = self._get_target_path(file_path, output_dir)
            copy_tasks.append(self._copy_single_file(file_path, target_path))

        # 병렬로 파일 복사 실행
        await asyncio.gather(*copy_tasks, return_exceptions=True)
        logger.info(f"{len(file_paths)}개 파일을 출력 디렉토리로 복사 완료")

    async def _copy_single_file(self, source_path: str, target_path: str):
        """개별 파일을 비동기로 복사"""
        try:
            source_path_obj = Path(source_path)
            target_path_obj = Path(target_path)

            # 원본 파일이 존재하는지 확인
            if not source_path_obj.exists():
                logger.warning(f"원본 파일이 존재하지 않음: {source_path}")
                return

            # 타겟 디렉토리 생성
            target_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # 파일 복사
            async with aiofiles.open(source_path, "rb") as src:
                async with aiofiles.open(target_path, "wb") as dst:
                    content = await src.read()
                    await dst.write(content)

            logger.debug(f"파일 복사 완료: {source_path_obj.name}")

        except Exception as e:
            logger.error(f"파일 복사 실패 ({Path(source_path).name}): {e}")

    async def _process_file_update(
        self,
        file_path: str,
        file_translations: Dict[str, str],
        output_dir: Optional[str],
        backup_originals: bool,
    ) -> int:
        """개별 파일 업데이트를 비동기로 처리"""
        try:
            # 백업 생성
            if backup_originals:
                await self._backup_file_async(file_path)

            # 출력 경로 결정
            target_path = self._get_target_path(file_path, output_dir)

            # 파일 업데이트 (출력 디렉토리가 지정된 경우 타겟 파일에서 읽기)
            if output_dir:
                # 출력 디렉토리에 복사된 파일을 업데이트
                updated_count = await self._update_single_file(
                    target_path, target_path, file_translations
                )
            else:
                # 원본 파일을 업데이트
                updated_count = await self._update_single_file(
                    file_path, target_path, file_translations
                )

            return updated_count

        except Exception as e:
            logger.error(f"파일 업데이트 실패 ({Path(file_path).name}): {e}")
            return 0

    async def _backup_file_async(self, file_path: str):
        """원본 파일을 비동기로 백업"""
        try:
            source_path = Path(file_path)
            backup_path = source_path.with_suffix(source_path.suffix + ".backup")

            if source_path.exists():
                # 비동기 파일 복사
                async with aiofiles.open(source_path, "rb") as src:
                    async with aiofiles.open(backup_path, "wb") as dst:
                        content = await src.read()
                        await dst.write(content)

                logger.debug(f"파일 백업 생성: {backup_path}")
        except Exception as e:
            logger.warning(f"백업 생성 실패 ({Path(file_path).name}): {e}")

    def _group_translations_by_file(
        self, translated_data: Dict[str, str]
    ) -> Dict[str, Dict[str, str]]:
        """번역 데이터를 파일별로 그룹화"""
        file_groups = {}

        for unique_key, translated_text in translated_data.items():
            if unique_key not in self.translation_map:
                continue

            # 해당 키의 원본 위치 정보 가져오기 (첫 번째 항목 사용)
            mapping_info = self.translation_map[unique_key][0]
            file_path = mapping_info["file_path"]
            original_key = mapping_info["original_key"]  # 원본 키 사용

            if file_path not in file_groups:
                file_groups[file_path] = {}

            # 파일에 적용할 때는 원본 키를 사용
            file_groups[file_path][original_key] = translated_text

        return file_groups

    async def _update_single_file(
        self, source_path: str, target_path: str, translations: Dict[str, str]
    ) -> int:
        """개별 파일을 번역 데이터로 업데이트"""
        try:
            # 먼저 특수 필터들 확인 (KubeJS 등)
            applicable_filters = self.filter_manager.get_applicable_filters(source_path)

            # 특수 필터가 번역 적용 기능을 지원하는지 확인
            for filter_instance in applicable_filters:
                if hasattr(filter_instance, "apply_translations"):
                    logger.debug(
                        f"특수 필터 사용: {type(filter_instance).__name__} for {Path(source_path).name}"
                    )

                    # 출력 디렉토리 생성
                    Path(target_path).parent.mkdir(parents=True, exist_ok=True)

                    # 소스 파일을 타겟 위치로 복사 (필요시)
                    if source_path != target_path:
                        import shutil

                        shutil.copy2(source_path, target_path)

                    # 특수 필터의 번역 적용 기능 사용
                    success = await filter_instance.apply_translations(
                        target_path, translations
                    )

                    if success:
                        logger.debug(
                            f"특수 필터 번역 적용 완료: {Path(target_path).name}"
                        )
                        return len(translations)  # 번역 적용된 항목 수 반환
                    else:
                        logger.warning(
                            f"특수 필터 번역 적용 실패: {Path(target_path).name}"
                        )
                        break  # 다음 필터 시도하지 않고 일반 파서로 진행

            # 특수 필터가 없거나 실패한 경우 일반 파서 사용
            file_extension = Path(source_path).suffix.lower()
            parser_class = BaseParser.get_parser_by_extension(file_extension)

            if not parser_class:
                logger.warning(f"지원하지 않는 파일 형식: {file_extension}")
                return 0

            # 원본 파일 파싱
            source_parser = parser_class(Path(source_path))
            original_data = await source_parser.parse()

            # 번역 데이터로 업데이트
            updated_data = original_data.copy()
            update_count = 0

            for key, translated_text in translations.items():
                if key in updated_data:
                    updated_data[key] = translated_text
                    update_count += 1

            # 업데이트된 데이터를 파일로 저장
            target_parser = parser_class(Path(target_path))

            # 출력 디렉토리 생성
            Path(target_path).parent.mkdir(parents=True, exist_ok=True)

            await target_parser.dump(updated_data)

            return update_count

        except Exception as e:
            logger.error(f"파일 업데이트 중 오류 ({Path(source_path).name}): {e}")
            return 0

    def _get_target_path(self, source_path: str, output_dir: Optional[str]) -> str:
        """출력 파일 경로 결정"""
        if output_dir is None:
            # 원본 파일에 덮어쓰기
            return source_path
        else:
            # 출력 디렉토리에 저장
            source_path_obj = Path(source_path)
            modpack_path_obj = Path(self.modpack_path)

            try:
                # 모드팩 경로를 기준으로 상대 경로 계산
                relative_path = source_path_obj.relative_to(modpack_path_obj)
            except ValueError:
                # 상대 경로 계산 실패 시 파일명만 사용
                relative_path = source_path_obj.name

            return str(Path(output_dir) / relative_path)

    async def save_results_async(
        self,
        translated_data: Dict[str, str],
        output_path: str = "modpack_translation.json",
        save_mapping: bool = True,
        apply_to_files: bool = False,
        output_dir: Optional[str] = None,
        backup_originals: bool = True,
    ):
        """번역 결과를 비동기로 저장 (최적화된 병렬 처리)"""
        try:
            logger.info("번역 결과 저장 시작")

            # 출력 경로의 디렉토리 생성 (중요!)
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"출력 디렉토리 생성: {output_path_obj.parent}")

            # 병렬 저장 작업 준비
            save_tasks = []

            # 1. 번역 결과 저장
            save_tasks.append(self._save_json_async(translated_data, output_path))

            # 2. 매핑 정보 저장
            if save_mapping:
                mapping_path = output_path.replace(".json", "_mapping.json")
                # 매핑 파일의 디렉토리도 생성 (추가 보안)
                mapping_path_obj = Path(mapping_path)
                mapping_path_obj.parent.mkdir(parents=True, exist_ok=True)
                save_tasks.append(
                    self._save_json_async(self.translation_map, mapping_path)
                )

            # 3. 통계 정보 저장
            stats_path = output_path.replace(".json", "_stats.json")
            stats_path_obj = Path(stats_path)
            stats_path_obj.parent.mkdir(parents=True, exist_ok=True)
            stats = self._generate_stats(translated_data)
            save_tasks.append(self._save_json_async(stats, stats_path))

            # 병렬 저장 실행
            await asyncio.gather(*save_tasks)

            logger.info(f"번역 결과 저장 완료: {len(translated_data)}개 항목")
            logger.info(f"메인 파일: {output_path}")
            if save_mapping:
                logger.info(f"매핑 파일: {mapping_path}")
            logger.info(f"통계 파일: {stats_path}")

        except Exception as e:
            logger.error(f"결과 저장 실패: {e}")
            logger.error(f"출력 경로: {output_path}")
            logger.error(f"출력 디렉토리: {output_dir}")
            import traceback

            logger.error(f"트레이스백: {traceback.format_exc()}")
            raise

    async def _save_json_async(self, data: Dict, file_path: str):
        """JSON 데이터를 비동기로 저장 (디렉토리 생성 포함)"""
        try:
            # 파일 경로의 디렉토리 생성
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # 비동기 파일 쓰기
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                json_str = json.dumps(data, ensure_ascii=False, indent=2)
                await f.write(json_str)

            logger.debug(f"JSON 파일 저장 완료: {file_path}")
        except Exception as e:
            logger.error(f"JSON 파일 저장 실패 ({file_path}): {e}")
            raise

    def _generate_stats(self, translated_data: Dict[str, str]) -> Dict:
        """번역 통계 생성"""
        stats = {
            "total_entries": len(translated_data),
            "modpack_path": self.modpack_path,
            "source_language": self.source_lang,
            "target_language": self.target_language,
            "file_type_distribution": {},
            "filter_usage": {},
        }

        # 파일 타입별 분포
        for key, mappings in self.translation_map.items():
            for mapping in mappings:
                file_type = mapping["file_type"]
                stats["file_type_distribution"][file_type] = (
                    stats["file_type_distribution"].get(file_type, 0) + 1
                )

        return stats

    async def run_full_translation(
        self,
        loader: ModpackLoader,
        output_path: str = "modpack_translation.json",
        max_retries: int = 5,
        max_tokens_per_chunk: int = 2000,
        use_glossary: bool = True,
        use_vanilla_glossary: bool = True,
        vanilla_glossary_path: Optional[str] = None,
        save_mapping: bool = True,
        apply_to_files: bool = False,
        output_dir: Optional[str] = None,
        backup_originals: bool = True,
        enable_packaging: bool = True,
        max_concurrent_requests: Optional[int] = None,
        delay_between_requests_ms: Optional[int] = None,
        llm_provider: str = "gemini",
        llm_model: str = "gemini-1.5-flash",
        temperature: float = 0.1,
        enable_quality_review: bool = True,
        final_fallback_max_retries: int = 2,
        max_quality_retries: int = 1,
        selected_files: Optional[List[str]] = None,
        selected_glossary_files: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """전체 번역 과정 실행 (최적화된 병렬 처리)"""
        try:
            # API 호출 설정 업데이트 (필요시)
            if max_concurrent_requests is not None:
                self.max_concurrent_requests = max_concurrent_requests
                logger.info(f"동시 요청 수 변경: {max_concurrent_requests}")

            if delay_between_requests_ms is not None:
                self.delay_between_requests_ms = delay_between_requests_ms
                logger.info(f"요청 간 지연 변경: {delay_between_requests_ms}ms")

            self.loader.translation_files = loader.translation_files
            # 1. 번역 대상 수집 (병렬 처리)
            await self.collect_all_translations(
                selected_files=selected_files,
                selected_glossary_files=selected_glossary_files,
            )

            # self.integrated_data = dict(list(self.integrated_data.items())[:3000])
            # 디버그용

            # 2. 번역 실행
            translated_data = await self.translate_integrated_data(
                max_retries=max_retries,
                max_tokens_per_chunk=max_tokens_per_chunk,
                use_glossary=use_glossary,
                use_vanilla_glossary=use_vanilla_glossary,
                vanilla_glossary_path=vanilla_glossary_path,
                llm_provider=llm_provider,
                llm_model=llm_model,
                temperature=temperature,
                enable_quality_review=enable_quality_review,
                final_fallback_max_retries=final_fallback_max_retries,
                max_quality_retries=max_quality_retries,
                selected_glossary_files=selected_glossary_files,
            )

            # 3. 결과 저장 (병렬 처리)
            await self.save_results_async(
                translated_data,
                output_path,
                save_mapping,
                apply_to_files=False,  # save_results에서는 파일 업데이트하지 않음
                output_dir=output_dir,
                backup_originals=backup_originals,
            )

            # 4. 원본 파일들에 번역 적용 (병렬 처리)
            if apply_to_files:
                logger.info("원본 파일들에 번역 적용 시작...")
                update_stats = await self.apply_translations_to_files(
                    translated_data, output_dir, backup_originals
                )

                # 업데이트 통계 저장
                if update_stats:
                    update_stats_path = output_path.replace(
                        ".json", "_update_stats.json"
                    )
                    await self._save_json_async(update_stats, update_stats_path)
                    logger.info(f"파일 업데이트 통계 저장됨: {update_stats_path}")

            # 5. 패키징 (선택적)
            packaging_result = {"resource_pack_path": None, "override_files_path": None}
            if enable_packaging and apply_to_files and output_dir:
                packaging_result = await self.package_translations(output_dir)

            # 전체 결과 반환 (번역 데이터 + 패키징 결과)
            return {
                "translated_data": translated_data,
                "packaging_result": packaging_result,
            }

        except Exception:
            import traceback

            logger.error(f"번역 과정 중 오류 발생: {traceback.format_exc()}")
            raise

    async def package_translations(self, output_dir: str) -> Dict[str, Optional[str]]:
        """번역 결과를 패키징합니다.

        Returns:
            Dict[str, Optional[str]]: 패키징 결과 파일 경로들
                - "resource_pack_path": 리소스팩 zip 파일 경로
                - "override_files_path": 덮어쓰기 zip 파일 경로
        """
        try:
            logger.info("번역 결과 패키징 시작")

            # 번역된 파일 경로 구성
            translated_files = {}
            for key, mappings in self.translation_map.items():
                for mapping in mappings:
                    original_path = mapping["file_path"]
                    # 출력 디렉토리 기준으로 번역된 파일 경로 생성
                    translated_path = self._get_target_path(original_path, output_dir)
                    translated_files[original_path] = translated_path

                    # 모드팩 이름 추출
            modpack_name = Path(self.modpack_path).name

            # 대상 언어 코드 변환
            target_lang_code = self._convert_language_to_code(self.target_language)

            # 패키징 관리자 초기화
            try:
                from ..modpack_packaging.manager import PackageManager

                package_manager = PackageManager(
                    source_lang=self.source_lang,
                    target_lang=target_lang_code,
                    pack_format=15,  # MC 1.20.1 기준
                    pack_name=f"{modpack_name} Translation Pack",
                    pack_description=f"{modpack_name} Translation",
                )
            except ImportError as e:
                logger.warning(f"패키징 모듈 import 실패: {e}")
                logger.warning("패키징을 건너뜁니다.")
                return

            # 패키징 출력 디렉토리
            packaging_output = Path(output_dir).parent / "packaging_output"

            # 전체 패키징 실행
            results = await package_manager.package_all(
                translated_files=translated_files,
                output_dir=packaging_output,
                create_resourcepack=True,
                create_modpack=True,
                create_zips=True,
                create_jar_mods=True,
                mods_path=os.path.join(self.modpack_path, "mods"),
                parallel=True,
                modpack_name=modpack_name,  # 모드팩 이름 전달
            )

            # 결과 로깅
            logger.info("=== 패키징 결과 ===")
            for package_type, result in results.items():
                if result.success:
                    logger.info(
                        f"✅ {package_type}: {result.file_count}개 파일 → {result.output_path}"
                    )
                else:
                    logger.error(f"❌ {package_type}: 실패")
                    for error in result.errors:
                        logger.error(f"   - {error}")

            # README 파일 생성
            package_manager.create_readme(packaging_output, results)

            # 통계 저장
            stats = package_manager.get_package_statistics(results)
            stats_path = packaging_output / "packaging_stats.json"
            await self._save_json_async(stats, str(stats_path))

            logger.info(f"패키징 완료: {packaging_output}")

            # 생성된 파일 경로 추출
            resource_pack_path = None
            override_files_path = None

            # 리소스팩과 모드팩 결과에서 zip 파일 경로 찾기
            if "resourcepack" in results and results["resourcepack"].success:
                if results["resourcepack"].output_path:
                    resource_pack_path = str(results["resourcepack"].output_path)

            if "modpack" in results and results["modpack"].success:
                if results["modpack"].output_path:
                    override_files_path = str(results["modpack"].output_path)

            return {
                "resource_pack_path": resource_pack_path,
                "override_files_path": override_files_path,
            }

        except ImportError:
            logger.warning("패키징 모듈을 찾을 수 없습니다. 패키징을 건너뜁니다.")
            return {"resource_pack_path": None, "override_files_path": None}
        except Exception as e:
            logger.error(f"패키징 실패: {e}")
            # 패키징 실패는 전체 프로세스를 중단시키지 않음
            return {"resource_pack_path": None, "override_files_path": None}

    # 기존 save_results는 호환성을 위해 유지하되 비동기 버전 호출
    def save_results(
        self,
        translated_data: Dict[str, str],
        output_path: str = "modpack_translation.json",
        save_mapping: bool = True,
        apply_to_files: bool = False,
        output_dir: Optional[str] = None,
        backup_originals: bool = True,
    ):
        """번역 결과 저장 (호환성을 위한 동기 버전)"""
        import asyncio

        try:
            # 현재 이벤트 루프가 있는지 확인
            loop = asyncio.get_running_loop()
            # 이미 비동기 컨텍스트 내부이므로 task 생성
            loop.create_task(
                self.save_results_async(
                    translated_data,
                    output_path,
                    save_mapping,
                    apply_to_files,
                    output_dir,
                    backup_originals,
                )
            )
            logger.info("비동기 저장 작업이 시작되었습니다.")
        except RuntimeError:
            # 이벤트 루프가 없으면 새로 생성
            asyncio.run(
                self.save_results_async(
                    translated_data,
                    output_path,
                    save_mapping,
                    apply_to_files,
                    output_dir,
                    backup_originals,
                )
            )

    def _convert_language_to_code(self, language: str) -> str:
        """언어 이름을 마인크래프트 언어 코드로 변환합니다."""
        language_mapping = {
            "한국어": "ko_kr",
            "korean": "ko_kr",
            "일본어": "ja_jp",
            "japanese": "ja_jp",
            "중국어(간체)": "zh_cn",
            "chinese simplified": "zh_cn",
            "chinese_simplified": "zh_cn",
            "중국어(번체)": "zh_tw",
            "chinese traditional": "zh_tw",
            "chinese_traditional": "zh_tw",
            "프랑스어": "fr_fr",
            "french": "fr_fr",
            "독일어": "de_de",
            "german": "de_de",
            "스페인어": "es_es",
            "spanish": "es_es",
            "포르투갈어": "pt_br",
            "portuguese": "pt_br",
            "러시아어": "ru_ru",
            "russian": "ru_ru",
            "이탈리아어": "it_it",
            "italian": "it_it",
        }

        # 소문자로 변환하여 매칭 시도
        lang_lower = language.lower().strip()

        # 정확한 매칭 먼저 시도
        if lang_lower in language_mapping:
            return language_mapping[lang_lower]

        # 부분 매칭 시도
        for key, value in language_mapping.items():
            if lang_lower in key or key in lang_lower:
                return value

        # 이미 언어 코드 형식이면 그대로 반환
        if "_" in language and len(language) == 5:
            return language.lower()

        # 기본값으로 ko_kr 반환
        logger.warning(f"알 수 없는 언어: {language}, 기본값 ko_kr 사용")
        return "ko_kr"
