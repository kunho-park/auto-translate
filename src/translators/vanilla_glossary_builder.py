"""
바닐라 마인크래프트 번역 데이터로 Glossary 구축 모듈

바닐라 마인크래프트의 en_us.json과 ko_kr.json을 읽어서
LLM을 활용해 일관성 있는 용어 사전(Glossary)을 구축합니다.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

from src.prompts.vanilla_glossary_prompts import create_vanilla_glossary_prompt

from .json_translator import Glossary, GlossaryEntry

logger = logging.getLogger(__name__)


class VanillaGlossaryBuilder:
    """바닐라 마인크래프트 번역 데이터로 glossary를 구축하는 클래스"""

    def __init__(
        self,
        source_lang_file: str = "src/assets/vanilla_minecraft_assets/versions/1.21.5/en_us.json",
        target_lang_file: str = "src/assets/vanilla_minecraft_assets/versions/1.21.5/ko_kr.json",
        target_language: str = "한국어",
    ):
        self.source_lang_file = Path(source_lang_file)
        self.target_lang_file = Path(target_lang_file)
        self.target_language = target_language

        # 번역 데이터 저장
        self.vanilla_translations: Dict[str, str] = {}

    async def load_vanilla_translations(self) -> Dict[str, str]:
        """바닐라 마인크래프트 번역 데이터를 로드합니다."""
        logger.info("바닐라 마인크래프트 번역 데이터 로드 시작")

        try:
            # 소스 언어 파일 로드
            if not self.source_lang_file.exists():
                logger.error(
                    f"소스 언어 파일이 존재하지 않습니다: {self.source_lang_file}"
                )
                return {}

            with open(self.source_lang_file, "r", encoding="utf-8") as f:
                source_data = json.load(f)

            # 타겟 언어 파일 로드
            if not self.target_lang_file.exists():
                logger.error(
                    f"타겟 언어 파일이 존재하지 않습니다: {self.target_lang_file}"
                )
                return {}

            with open(self.target_lang_file, "r", encoding="utf-8") as f:
                target_data = json.load(f)

            # 매칭되는 번역 쌍 추출
            translations = {}
            for key in source_data:
                if key in target_data:
                    source_text = source_data[key].strip()
                    target_text = target_data[key].strip()

                    # 유효한 번역 쌍만 추가
                    if (
                        source_text
                        and target_text
                        and source_text != target_text
                        and len(source_text) > 1
                        and len(target_text) > 1
                    ):
                        translations[source_text] = target_text

            self.vanilla_translations = translations
            logger.info(
                f"바닐라 마인크래프트 번역 데이터 로드 완료: {len(translations)}개 번역 쌍"
            )
            return translations

        except Exception as e:
            logger.error(f"바닐라 번역 데이터 로드 실패: {e}")
            return {}

    async def build_vanilla_glossary(
        self,
        max_entries_per_batch: int = 200,
        max_concurrent_requests: int = 3,
        max_retries: int = 3,
        progress_callback: Optional[callable] = None,
    ) -> List[GlossaryEntry]:
        """바닐라 번역 데이터를 활용해 LLM으로 glossary를 구축합니다."""
        if not self.vanilla_translations:
            await self.load_vanilla_translations()

        if not self.vanilla_translations:
            logger.warning("바닐라 번역 데이터가 없어 glossary 구축을 건너뜁니다.")
            return []

        logger.info(
            f"바닐라 glossary 구축 시작: {len(self.vanilla_translations)}개 번역 쌍"
        )

        # 번역 데이터를 배치로 나누기
        translation_items = list(self.vanilla_translations.items())
        batches = [
            translation_items[i : i + max_entries_per_batch]
            for i in range(0, len(translation_items), max_entries_per_batch)
        ]

        logger.info(f"총 {len(batches)}개 배치로 나누어 처리")

        # 진행률 콜백 호출
        if progress_callback:
            progress_callback(
                "🎮 바닐라 사전 구축 중",
                0,
                len(batches),
                f"바닐라 마인크래프트 번역 데이터 {len(self.vanilla_translations)}개로 사전 구축 시작",
            )

        # 세마포어로 동시 요청 수 제한
        semaphore = asyncio.Semaphore(max_concurrent_requests)
        all_glossary_entries = []

        # 배치별로 병렬 처리
        tasks = [
            self._process_vanilla_batch(
                batch,
                batch_idx + 1,
                len(batches),
                semaphore,
                progress_callback,
                max_retries,
            )
            for batch_idx, batch in enumerate(batches)
        ]

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 수집
        for batch_idx, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"배치 {batch_idx + 1} 처리 실패: {result}")
            elif result:
                all_glossary_entries.extend(result.terms)

        # 진행률 콜백 호출 (완료)
        if progress_callback:
            progress_callback(
                "🎮 바닐라 사전 구축 완료",
                len(batches),
                len(batches),
                f"총 {len(all_glossary_entries)}개 용어가 포함된 바닐라 사전 구축 완료",
            )

        logger.info(f"바닐라 glossary 구축 완료: {len(all_glossary_entries)}개 용어")
        return all_glossary_entries

    async def _process_vanilla_batch(
        self,
        batch: List[tuple],
        batch_num: int,
        total_batches: int,
        semaphore: asyncio.Semaphore,
        progress_callback: Optional[callable] = None,
        max_retries: int = 3,
    ) -> Glossary:
        """바닐라 번역 배치를 처리하여 glossary 항목을 생성합니다."""
        async with semaphore:
            # 진행률 업데이트
            if progress_callback:
                progress_callback(
                    "🎮 바닐라 사전 구축 중",
                    batch_num - 1,
                    total_batches,
                    f"배치 {batch_num}/{total_batches} 처리 중 ({len(batch)}개 항목)",
                )

            # 배치를 JSON 형태로 구성
            batch_data = {source: target for source, target in batch}

            # 재시도 로직 구현
            last_error = None
            for attempt in range(max_retries + 1):  # 0번 시도부터 max_retries까지
                try:
                    # 재시도 시에는 temperature를 조금씩 올림
                    temperature = (
                        0.1 if attempt == 0 else min(0.3, 0.1 + attempt * 0.05)
                    )

                    # LLM 프롬프트 생성 (재시도 시 더 명확한 지시사항 추가)
                    prompt = self._create_vanilla_glossary_prompt(
                        batch_data, attempt > 0
                    )

                    if attempt > 0:
                        logger.info(
                            f"🔄 배치 {batch_num} 바닐라 사전 구축 재시도 {attempt}/{max_retries} (temperature={temperature})"
                        )
                        # 재시도 시 진행률 업데이트
                        if progress_callback:
                            progress_callback(
                                "🎮 바닐라 사전 구축 중",
                                batch_num - 1,
                                total_batches,
                                f"배치 {batch_num}/{total_batches} 재시도 중 ({attempt}/{max_retries})",
                            )

                    # LLM 호출 (타임아웃 추가)
                    llm = ChatGoogleGenerativeAI(
                        model="gemini-2.5-pro", temperature=temperature
                    )
                    # PydanticParser 사용
                    parser = PydanticOutputParser(pydantic_object=Glossary)
                    prompt_with_format = (
                        prompt + "\n\n" + parser.get_format_instructions()
                    )

                    # 30초 타임아웃으로 LLM 호출
                    response = await asyncio.wait_for(
                        llm.ainvoke(prompt_with_format), timeout=240
                    )

                    # 응답이 문자열인지 확인 후 파싱
                    if hasattr(response, "content"):
                        response_text = response.content
                    else:
                        response_text = str(response)

                    result = parser.parse(response_text)

                    # 성공 시 진행률 업데이트
                    if progress_callback:
                        success_msg = f"배치 {batch_num}/{total_batches} 완료"
                        if attempt > 0:
                            success_msg += f" (재시도 {attempt}회 후 성공)"
                        success_msg += (
                            f" ({len(result.terms) if result else 0}개 용어 생성)"
                        )

                        progress_callback(
                            "🎮 바닐라 사전 구축 중",
                            batch_num,
                            total_batches,
                            success_msg,
                        )

                    if attempt > 0:
                        logger.info(f"✅ 배치 {batch_num} 바닐라 사전 구축 재시도 성공")

                    logger.info(
                        f"배치 {batch_num} 완료: {len(result.terms) if result else 0}개 용어 생성"
                    )

                    return result or Glossary(terms=[])

                except asyncio.TimeoutError:
                    last_error = asyncio.TimeoutError("LLM 호출 타임아웃 (240초)")
                    logger.warning(
                        f"⏰ 배치 {batch_num} LLM 호출 타임아웃 (시도 {attempt + 1}/{max_retries + 1})"
                    )

                    # 타임아웃 시 더 긴 대기 시간
                    if attempt < max_retries:
                        await asyncio.sleep(min(5.0, (attempt + 1) * 1.0))

                except Exception as e:
                    last_error = e
                    error_type = type(e).__name__
                    logger.warning(
                        f"⚠️ 배치 {batch_num} 바닐라 사전 구축 실패 ({error_type}) (시도 {attempt + 1}/{max_retries + 1}): {e}"
                    )

                    # 마지막 시도가 아니면 잠시 대기
                    if attempt < max_retries:
                        await asyncio.sleep(
                            min(3.0, (attempt + 1) * 0.5)
                        )  # 0.5초, 1초, 1.5초, 2초, 2.5초, 3초 대기

            # 모든 재시도 실패 시
            logger.error(
                f"❌ 배치 {batch_num} 바닐라 사전 구축 {max_retries + 1}회 모두 실패: {last_error}"
            )

            # 실패해도 진행률 업데이트
            if progress_callback:
                progress_callback(
                    "🎮 바닐라 사전 구축 중",
                    batch_num,
                    total_batches,
                    f"배치 {batch_num}/{total_batches} 실패 (재시도 {max_retries}회 후)",
                )

            return Glossary(terms=[])

    def _create_vanilla_glossary_prompt(
        self, batch_data: Dict[str, str], is_retry: bool = False
    ) -> str:
        """바닐라 번역 데이터로 glossary 생성을 위한 프롬프트를 생성합니다."""
        return create_vanilla_glossary_prompt(
            batch_data, self.target_language, is_retry
        )

    async def save_vanilla_glossary(
        self,
        glossary_entries: List[GlossaryEntry],
        output_path: str = "vanilla_glossary.json",
    ) -> None:
        """생성된 바닐라 glossary를 파일로 저장합니다."""
        try:
            glossary_data = [entry.dict() for entry in glossary_entries]

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(glossary_data, f, ensure_ascii=False, indent=2)

            logger.info(
                f"바닐라 glossary 저장 완료: {output_path} ({len(glossary_entries)}개 용어)"
            )

        except Exception as e:
            logger.error(f"바닐라 glossary 저장 실패: {e}")

    async def load_vanilla_glossary(
        self, glossary_path: str = "vanilla_glossary.json"
    ) -> List[GlossaryEntry]:
        """저장된 바닐라 glossary를 로드합니다."""
        try:
            if not Path(glossary_path).exists():
                logger.warning(
                    f"바닐라 glossary 파일이 존재하지 않습니다: {glossary_path}"
                )
                return []

            with open(glossary_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            glossary_entries = [GlossaryEntry(**item) for item in data]
            logger.info(f"바닐라 glossary 로드 완료: {len(glossary_entries)}개 용어")
            return glossary_entries

        except Exception as e:
            logger.error(f"바닐라 glossary 로드 실패: {e}")
            return []

    async def create_or_load_vanilla_glossary(
        self,
        glossary_path: str = "vanilla_glossary.json",
        force_rebuild: bool = False,
        max_entries_per_batch: int = 200,
        max_concurrent_requests: int = 3,
        max_retries: int = 3,
        progress_callback: Optional[callable] = None,
    ) -> List[GlossaryEntry]:
        """바닐라 glossary를 생성하거나 기존 파일에서 로드합니다."""

        # 한국어인 경우 미리 준비된 사전 파일 확인
        if self.target_language == "한국어":
            preset_glossary_path = "src/assets/vanilla_glossary/ko_kr.json"

            # 미리 준비된 사전이 있으면 우선 사용
            if Path(preset_glossary_path).exists():
                logger.info("미리 준비된 한국어 바닐라 사전을 로드합니다.")
                try:
                    return await self.load_vanilla_glossary(preset_glossary_path)
                except Exception as e:
                    logger.warning(f"미리 준비된 사전 로드 실패, 기본 로직 사용: {e}")

        # 기존 파일이 있고 재구축을 강제하지 않는 경우 로드
        if Path(glossary_path).exists() and not force_rebuild:
            logger.info("기존 바닐라 glossary 파일을 로드합니다.")
            return await self.load_vanilla_glossary(glossary_path)

        # 새로 구축
        logger.info("바닐라 glossary를 새로 구축합니다.")
        glossary_entries = await self.build_vanilla_glossary(
            max_entries_per_batch=max_entries_per_batch,
            max_concurrent_requests=max_concurrent_requests,
            max_retries=max_retries,
            progress_callback=progress_callback,
        )

        # 저장
        if glossary_entries:
            await self.save_vanilla_glossary(glossary_entries, glossary_path)

        return glossary_entries


# 편의 함수들
async def create_vanilla_glossary(
    output_path: str = "vanilla_glossary.json",
    force_rebuild: bool = False,
    max_entries_per_batch: int = 200,
    max_concurrent_requests: int = 3,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
) -> List[GlossaryEntry]:
    """바닐라 마인크래프트 glossary를 생성하는 편의 함수"""
    builder = VanillaGlossaryBuilder()
    return await builder.create_or_load_vanilla_glossary(
        glossary_path=output_path,
        force_rebuild=force_rebuild,
        max_entries_per_batch=max_entries_per_batch,
        max_concurrent_requests=max_concurrent_requests,
        max_retries=max_retries,
        progress_callback=progress_callback,
    )


if __name__ == "__main__":
    # 테스트 실행
    async def test_vanilla_glossary():
        logger.basicConfig(level=logging.INFO)

        def progress_callback(title, current, total, message):
            print(f"{title}: {current}/{total} - {message}")

        glossary_entries = await create_vanilla_glossary(
            output_path="test_vanilla_glossary.json",
            force_rebuild=True,
            max_entries_per_batch=100,
            max_concurrent_requests=2,
            max_retries=3,
            progress_callback=progress_callback,
        )

        print(f"생성된 바닐라 glossary 용어 수: {len(glossary_entries)}")

        # 몇 개 예시 출력
        for i, entry in enumerate(glossary_entries[:5]):
            print(f"{i + 1}. {entry.original}")
            for meaning in entry.meanings:
                print(f"   -> {meaning.translation} (문맥: {meaning.context})")

    asyncio.run(test_vanilla_glossary())
