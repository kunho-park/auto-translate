import asyncio
import json
import logging
import os
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import regex as re
from langchain_core.language_models import BaseLLM
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import END, StateGraph

from src.localization import get_message as _m
from src.prompts.llm_prompts import (
    contextual_terms_prompt,
    final_fallback_prompt,
    quality_retranslation_prompt,
    retry_contextual_terms_prompt,
    retry_translation_prompt,
    translation_prompt,
)
from src.translators.multi_llm_manager import MultiLLMManager
from src.translators.token_counter import UniversalTokenCountingHandler

logger = logging.getLogger(__name__)

__all__ = [
    "TranslatorState",
    "TranslatedItem",
    "TermMeaning",
    "GlossaryEntry",
    "Glossary",
    "TranslationPair",
    "TranslationResult",
    "QualityIssue",
    "QualityReview",
    "JSONTranslator",
    "run_example",
]

###############################################################################
# 1. State and data-model definitions                                        #
###############################################################################


# ---------------------------------------------------------------------------
# Externalised data models & utilities (moved to separate modules for clarity)
# ---------------------------------------------------------------------------
from .models import (
    Glossary,
    GlossaryEntry,
    QualityIssue,
    QualityReview,
    SimpleGlossaryTerm,
    TermMeaning,
    TranslatedItem,
    TranslationPair,
    TranslationResult,
    TranslatorState,
)
from .utils import (
    PlaceholderManager,
    RequestDelayManager,
    TokenOptimizer,
    is_korean_text,
)

###############################################################################
# 2. Utility helpers                                                          #
###############################################################################


###############################################################################
# 3. LangGraph node functions (async)                                         #
###############################################################################


async def invoke_with_structured_output_fallback(llm_client: BaseLLM, schema, prompt):
    """구조화된 출력으로 LLM 호출, 실패 시 PydanticOutputParser로 폴백"""

    # 첫 번째 시도: with_structured_output 사용
    try:
        structured_llm = llm_client.with_structured_output(schema, include_raw=True)

        response = await structured_llm.ainvoke(prompt)
        result = response["parsed"]

        # 결과가 None이 아닌지 확인
        if result is not None:
            logger.debug("구조화된 출력 성공")
            return result
        else:
            logger.warning(
                "구조화된 출력 결과가 None입니다. PydanticOutputParser로 재시도합니다."
            )
            raise ValueError("구조화된 출력 결과가 None")

    except Exception as e:
        logger.warning(f"구조화된 출력 실패: {e}. PydanticOutputParser로 폴백합니다.")

    # 두 번째 시도: PydanticOutputParser 사용
    try:
        parser = PydanticOutputParser(pydantic_object=schema)

        # 프롬프트에 파서 지시사항 추가
        enhanced_prompt = f"{prompt}\n\n{parser.get_format_instructions()}"

        response = await llm_client.ainvoke(enhanced_prompt)
        result = parser.parse(response.content)

        if result is not None:
            logger.debug("PydanticOutputParser로 파싱 성공")
            return result
        else:
            logger.error("PydanticOutputParser 결과도 None입니다.")
            return None

    except Exception as e:
        logger.error(f"PydanticOutputParser도 실패: {e}")
        return None


def _filter_relevant_glossary_terms(
    chunk: List[Dict[str, str]], all_glossary_terms: List[GlossaryEntry]
) -> List[GlossaryEntry]:
    """해당 청크에 포함된 용어들만 글로시리에서 필터링"""
    if not all_glossary_terms:
        return []

    # 청크의 모든 텍스트를 하나로 합치기
    chunk_text = " ".join(item["original"].lower() for item in chunk)

    # 청크에 포함된 용어들만 필터링
    relevant_terms = []
    for term in all_glossary_terms:
        # 원본 용어가 청크 텍스트에 포함되어 있는지 확인
        if term.original.lower() in chunk_text:
            relevant_terms.append(term)

    return relevant_terms


async def parse_and_extract_node(state: TranslatorState) -> TranslatorState:  # noqa: D401
    try:
        # 새로운 번역 작업 시작 시 ID 및 플레이스홀더 카운터 리셋
        TokenOptimizer.reset_id_counter()
        PlaceholderManager.reset_counter()

        placeholders: Dict[str, str] = {}
        json_with_placeholders = PlaceholderManager.process_json_object(
            state["parsed_json"], placeholders
        )
        state["placeholders"] = placeholders

        # 이미 번역된 항목들을 제외하는 로직 추가
        existing_translations = state.get("existing_translations", {})

        # 전체 텍스트 항목 수를 먼저 계산
        original_text_count = len(
            TokenOptimizer.optimize_json_for_translation(json_with_placeholders)
        )

        id_to_text: Dict[str, str] = {}
        json_with_ids = TokenOptimizer.replace_text_with_ids_selective(
            json_with_placeholders, id_to_text, existing_translations
        )

        state["id_to_text_map"] = id_to_text
        state["processed_json"] = json_with_ids

        logger.info(_m("translator.found_items", count=len(id_to_text)))

        # 이미 번역된 항목 개수 로깅
        if existing_translations:
            already_translated_count = original_text_count - len(id_to_text)
            if already_translated_count > 0:
                logger.info(
                    f"이미 번역된 항목 {already_translated_count}개를 건너뛰었습니다."
                )

        return state
    except Exception as exc:
        state["error"] = f"전처리 오류: {exc}"
        return state


async def extract_terms_from_json_chunks_node(
    state: TranslatorState,
) -> TranslatorState:
    """Extracts terms by analyzing the full JSON in chunks for contextual accuracy."""
    try:
        # 여러 사전을 우선순위에 따라 병합
        vanilla_glossary = state.get("vanilla_glossary", [])
        primary_glossary = state.get("primary_glossary", [])
        existing_important_terms = state.get("important_terms", [])

        merged_glossary: Dict[str, GlossaryEntry] = {}

        # 1. 기존 중요 용어들 추가 (기본 사전)
        for term in existing_important_terms:
            merged_glossary[term.original.lower()] = term

        # 2. 바닐라 사전 용어들 병합 (최고 우선순위)
        vanilla_added_count = 0
        for vanilla_term in vanilla_glossary:
            key = vanilla_term.original.lower()
            if key in merged_glossary:
                # 기존 용어에 바닐라 의미들 추가 (우선순위 높음)
                # 바닐라 의미를 앞쪽에 추가하고 중복 제거
                vanilla_meanings = TokenOptimizer.deduplicate_glossary_meanings(
                    vanilla_term.meanings
                )
                existing_meanings = merged_glossary[key].meanings

                # 바닐라 의미를 앞에, 기존 의미를 뒤에 배치한 후 중복 제거
                combined_meanings = vanilla_meanings + existing_meanings
                merged_glossary[
                    key
                ].meanings = TokenOptimizer.deduplicate_glossary_meanings(
                    combined_meanings
                )
            else:
                # 새로운 바닐라 용어 추가 (의미 중복 제거)
                deduplicated_term = GlossaryEntry(
                    original=vanilla_term.original,
                    meanings=TokenOptimizer.deduplicate_glossary_meanings(
                        vanilla_term.meanings
                    ),
                )
                merged_glossary[key] = deduplicated_term
                vanilla_added_count += 1

        # 3. 1차 사전 용어들 병합 (기존 번역 데이터)
        primary_added_count = 0
        for primary_term in primary_glossary:
            key = primary_term.original.lower()
            if key in merged_glossary:
                # 기존 용어에 새로운 의미들 추가 (중복 제거)
                merged_glossary[
                    key
                ].meanings = TokenOptimizer.merge_glossary_entry_meanings(
                    merged_glossary[key].meanings, primary_term.meanings
                )
            else:
                # 새로운 용어 추가 (의미 중복 제거)
                deduplicated_term = GlossaryEntry(
                    original=primary_term.original,
                    meanings=TokenOptimizer.deduplicate_glossary_meanings(
                        primary_term.meanings
                    ),
                )
                merged_glossary[key] = deduplicated_term
                primary_added_count += 1

        # 병합된 사전을 상태에 저장
        state["important_terms"] = list(merged_glossary.values())

        # 병합 결과 로깅
        if vanilla_added_count > 0:
            logger.info(
                f"바닐라 사전에서 {vanilla_added_count}개 새로운 용어를 추가했습니다."
            )
        if primary_added_count > 0:
            logger.info(
                f"1차 사전에서 {primary_added_count}개 새로운 용어를 추가했습니다."
            )

        all_texts = "\n".join(state["id_to_text_map"].values())
        if not all_texts:
            logger.info(_m("translator.contextual_terms_no_new"))
            return state

        # Rough chunking by character count; can be improved
        chunk_size = 2000
        # 텍스트를 \n으로 구분하여 청크 크기에 맞게 분할
        chunks = []
        lines = all_texts.split("\n")
        current_chunk = []
        current_size = 0

        placeholder_pattern = r"\[(P\d{3,}|NEWLINE)\]"

        for line in lines:
            # placeholder 패턴을 빈 문자열로 교체
            line = re.sub(placeholder_pattern, "", line)

            # 빈 문자열이면 건너뛰기
            if not line.strip():
                continue

            # 현재 라인을 추가했을 때 청크 크기를 초과하는지 확인
            line_size = len(line)
            if current_size + line_size > chunk_size and current_chunk:
                # 현재 청크를 완성하고 새 청크 시작
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                # 현재 청크에 라인 추가
                current_chunk.append(line)
                current_size += line_size + 1  # +1 for \n

        # 마지막 청크 추가
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        logger.info(_m("translator.contextual_terms_start", count=len(chunks)))

        # 진행률 콜백 호출 (용어 추출 시작)
        progress_callback = state.get("progress_callback")
        if progress_callback:
            base_msg = (
                f"🔍 {len(chunks)}개 JSON 청크의 문맥을 분석하여 용어 추출을 시작합니다"
            )
            if primary_added_count > 0:
                base_msg += f" (1차 사전 {primary_added_count}개 용어 포함)"
            progress_callback(
                base_msg,
                0,
                len(chunks),
                f"총 {len(chunks)}개 청크 처리 예정",
            )

        sem = asyncio.Semaphore(state["max_concurrent_requests"])

        # 청크를 순차적으로 처리하여 진행률 업데이트 (완전 병렬 대신)
        tasks = []
        for chunk_idx, chunk in enumerate(chunks):
            tasks.append(
                _extract_terms_from_chunk_worker_with_progress(
                    text_chunk=chunk,
                    target_language=state["target_language"],
                    semaphore=sem,
                    chunk_idx=chunk_idx,
                    total_chunks=len(chunks),
                    progress_callback=progress_callback,
                    max_retries=state.get(
                        "max_retries", 3
                    ),  # 메인 설정의 재시도 횟수 사용
                    existing_glossary=list(
                        merged_glossary.values()
                    ),  # 1차 사전을 LLM에 제공
                    llm_client=state.get("llm_client"),  # LLM 클라이언트 전달
                    state=state,  # 다중 API 키 지원을 위한 상태 전달
                )
            )

        glossaries = await asyncio.gather(*tasks)

        # Merge glossaries from all chunks
        new_terms_count = 0

        for glossary in glossaries:
            for term in glossary.terms:
                key = term.original.lower()
                if key not in merged_glossary:
                    # 새로운 용어 추가 (의미 중복 제거)
                    deduplicated_term = GlossaryEntry(
                        original=term.original,
                        meanings=TokenOptimizer.deduplicate_glossary_meanings(
                            term.meanings
                        ),
                    )
                    merged_glossary[key] = deduplicated_term
                    new_terms_count += 1
                else:
                    # 기존 용어에 새로운 의미들 병합 (중복 제거)
                    merged_glossary[
                        key
                    ].meanings = TokenOptimizer.merge_glossary_entry_meanings(
                        merged_glossary[key].meanings, term.meanings
                    )

        state["important_terms"] = list(merged_glossary.values())

        # 진행률 콜백 호출 (용어 추출 완료)
        if progress_callback:
            progress_callback(
                "🔍 용어 추출 완료",
                len(chunks),
                len(chunks),
                f"LLM 분석으로 새로운 용어 {new_terms_count}개 추가됨"
                if new_terms_count > 0
                else "LLM 분석 완료, 새로운 용어 없음",
            )

        if new_terms_count > 0:
            logger.info(_m("translator.contextual_terms_finish", count=new_terms_count))
        else:
            logger.info(_m("translator.contextual_terms_no_new"))

        total_terms = len(merged_glossary)
        logger.info(
            f"최종 사전 크기: {total_terms}개 용어 (1차 사전: {len(primary_glossary)}개, LLM 추가: {new_terms_count}개)"
        )

        return state

    except Exception as exc:
        logger.error(_m("translator.contextual_terms_main_error", error=exc))
        # Non-critical, proceed without new terms
        return state


async def _extract_terms_from_chunk_worker_with_progress(
    *,
    text_chunk: str,
    target_language: str,
    semaphore: asyncio.Semaphore,
    chunk_idx: int,
    total_chunks: int,
    progress_callback: Optional[callable] = None,
    max_retries: int = 3,
    existing_glossary: List[GlossaryEntry] = None,
    llm_client: Any = None,
    state: TranslatorState = None,
) -> Glossary:
    """Worker to extract glossary terms from a single JSON chunk with progress reporting and retry logic."""

    if existing_glossary is None:
        existing_glossary = []

    async with semaphore:
        # 진행률 콜백 호출 (청크 처리 시작)
        if progress_callback:
            progress_callback(
                "🔍 JSON 청크 분석 중",
                chunk_idx,
                total_chunks,
                f"청크 {chunk_idx + 1}/{total_chunks} 용어 추출 중",
            )

        # 1차 사전 정보를 LLM에 제공하기 위한 프롬프트 수정
        existing_glossary_text = ""
        if existing_glossary:
            # 청크 텍스트에 실제로 포함된 용어들만 필터링
            chunk_text_lower = text_chunk.lower()
            relevant_existing_terms = [
                term
                for term in existing_glossary
                if term.original.lower() in chunk_text_lower
            ]

            if relevant_existing_terms:
                existing_glossary_text = TokenOptimizer.format_glossary_for_llm(
                    relevant_existing_terms
                )

        # 재시도 로직 구현
        last_error = None
        for attempt in range(max_retries + 1):  # 0번 시도부터 max_retries까지
            try:
                if attempt > 0:
                    prompt = retry_contextual_terms_prompt(
                        target_language, text_chunk, existing_glossary_text
                    )
                else:
                    prompt = contextual_terms_prompt(
                        target_language, text_chunk, existing_glossary_text
                    )
                # 재시도 시에는 temperature를 조금씩 올림 (최대 1.0까지)
                temperature = 0 if attempt == 0 else min(1.0, attempt * 0.1)

                # LLM 클라이언트 검증
                if llm_client is None:
                    logger.error("LLM 클라이언트가 설정되지 않았습니다")
                    return Glossary(terms=[])

                # 다중 API 키 사용 시 새로운 클라이언트 가져오기
                current_llm = llm_client
                if (
                    state
                    and state.get("use_multi_api_keys")
                    and state.get("multi_llm_manager")
                ):
                    multi_manager = state["multi_llm_manager"]
                    fresh_client = await multi_manager.get_client()
                    if fresh_client:
                        # 토큰 카운터 콜백 추가
                        try:
                            token_counter = (
                                state.get("token_counter") if state else None
                            )
                            if token_counter and hasattr(fresh_client, "callbacks"):
                                if fresh_client.callbacks is None:
                                    fresh_client.callbacks = []
                                if token_counter not in fresh_client.callbacks:
                                    fresh_client.callbacks.append(token_counter)
                        except Exception:
                            pass

                        current_llm = fresh_client
                        logger.debug(
                            f"용어 추출 청크 {chunk_idx + 1}: 다중 API 키에서 새 클라이언트 사용"
                        )
                    else:
                        logger.warning(
                            f"용어 추출 청크 {chunk_idx + 1}: 다중 API 키 클라이언트 가져오기 실패, 기본 클라이언트 사용"
                        )

                llm = current_llm
                if attempt > 0:
                    logger.info(
                        f"🔄 청크 {chunk_idx + 1} 용어 추출 재시도 {attempt}/{max_retries} (temperature={temperature})"
                    )
                    # 재시도 시 진행률 업데이트
                    if progress_callback:
                        progress_callback(
                            "🔍 JSON 청크 분석 중",
                            chunk_idx,
                            total_chunks,
                            f"청크 {chunk_idx + 1}/{total_chunks} 재시도 중 ({attempt}/{max_retries})",
                        )

                # SimpleGlossaryTerm을 도구로 바인딩하여 LLM 호출
                llm_with_tools = llm.bind_tools([SimpleGlossaryTerm])
                response = await llm_with_tools.ainvoke(prompt)

                # LLM의 도구 호출에서 SimpleGlossaryTerm 추출
                simple_terms: List[SimpleGlossaryTerm] = []
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        if tool_call["name"] == "SimpleGlossaryTerm":
                            try:
                                term = SimpleGlossaryTerm(**tool_call["args"])
                                simple_terms.append(term)
                            except Exception as e:
                                logger.warning(
                                    f"SimpleGlossaryTerm 파싱 중 오류가 발생하여 재시도를 유발합니다: {e}, args: {tool_call['args']}"
                                )
                                raise

                # SimpleGlossaryTerm 리스트를 GlossaryEntry 리스트로 변환 (집계)
                aggregated_entries: Dict[str, GlossaryEntry] = {}
                for term in simple_terms:
                    key = term.original.lower()
                    if key not in aggregated_entries:
                        aggregated_entries[key] = GlossaryEntry(
                            original=term.original, meanings=[]
                        )

                    aggregated_entries[key].meanings.append(
                        TermMeaning(translation=term.translation, context=term.context)
                    )

                result = Glossary(terms=list(aggregated_entries.values()))

                # 성공 시 진행률 콜백 호출
                if progress_callback:
                    success_msg = f"청크 {chunk_idx + 1}/{total_chunks} 완료"
                    if attempt > 0:
                        success_msg += f" (재시도 {attempt}회 후 성공)"
                    success_msg += (
                        f" - {len(result.terms) if result else 0}개 용어 발견"
                    )

                    progress_callback(
                        "🔍 JSON 청크 분석 중",
                        chunk_idx + 1,
                        total_chunks,
                        success_msg,
                    )

                if attempt > 0:
                    logger.info(f"✅ 청크 {chunk_idx + 1} 용어 추출 재시도 성공")

                return result or Glossary(terms=[])

            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"⚠️ 청크 {chunk_idx + 1} 용어 추출 실패 (시도 {attempt + 1}/{max_retries + 1}): {exc}"
                )

                # 다중 API 키 사용 시 해당 키의 실패를 기록
                if (
                    state
                    and state.get("use_multi_api_keys")
                    and state.get("multi_llm_manager")
                ):
                    logger.debug(f"용어 추출 청크 {chunk_idx + 1}: API 키 실패 기록됨")

                # 마지막 시도가 아니면 잠시 대기
                if attempt < max_retries:
                    await asyncio.sleep(
                        min(2.0, (attempt + 1) * 0.5)
                    )  # 0.5초, 1초, 1.5초, 2초 대기

        # 모든 재시도 실패 시
        logger.error(
            f"❌ 청크 {chunk_idx + 1} 용어 추출 {max_retries + 1}회 모두 실패: {last_error}"
        )

        # 실패해도 진행률 업데이트
        if progress_callback:
            progress_callback(
                "🔍 JSON 청크 분석 중",
                chunk_idx + 1,
                total_chunks,
                f"청크 {chunk_idx + 1}/{total_chunks} 실패 (재시도 {max_retries}회 후)",
            )

        return Glossary(terms=[])


def should_create_glossary(state: TranslatorState) -> str:
    """Determines whether to proceed with glossary creation."""
    if state.get("use_glossary"):
        return "create_glossary"
    logger.info(_m("translator.skipping_glossary"))
    return "skip_glossary"


def should_save_glossary(state: TranslatorState) -> str:
    """Determines whether to save the glossary at the end."""
    if state.get("use_glossary") and state.get("glossary_path"):
        return "save_glossary"
    return "end"


async def smart_translate_node(state: TranslatorState) -> TranslatorState:
    try:
        # LLM 클라이언트 가져오기
        llm = state.get("llm_client")
        if llm is None:
            logger.error("LLM 클라이언트가 설정되지 않았습니다")
            state["error"] = "LLM 클라이언트가 설정되지 않았습니다"
            return state
        id_map = state["id_to_text_map"]

        if not id_map:
            state["translation_map"] = {}
            return state

        items = [{"id": k, "original": v} for k, v in id_map.items()]
        chunks = TokenOptimizer.create_text_chunks(items, state["max_tokens_per_chunk"])

        logger.info(
            _m(
                "translator.chunks_split",
                chunks=len(chunks),
                concurrent=state["max_concurrent_requests"],
            )
        )

        # 진행률 콜백 호출 (번역 시작)
        progress_callback = state.get("progress_callback")
        if progress_callback:
            progress_callback(
                "📝 번역 진행 중", 0, len(chunks), f"총 {len(chunks)}개 청크 번역 시작"
            )

        delay_mgr = RequestDelayManager(state["delay_between_requests_ms"])
        sem = asyncio.Semaphore(state["max_concurrent_requests"])

        tasks = [
            _translate_chunk_worker_with_progress(
                chunk=c,
                state=state,
                llm=llm,
                target_language=state["target_language"],
                delay_manager=delay_mgr,
                semaphore=sem,
                chunk_num=i,
                total_chunks=len(chunks),
                progress_callback=progress_callback,
            )
            for i, c in enumerate(chunks, 1)
        ]
        results = await asyncio.gather(*tasks)

        translation_map: Dict[str, str] = {}
        for res in results:
            for item in res:
                translation_map[item.id] = item.translated

        state["translation_map"] = translation_map

        # 진행률 콜백 호출 (번역 완료)
        if progress_callback:
            progress_callback(
                "📝 번역 완료",
                len(chunks),
                len(chunks),
                f"총 {len(translation_map)}개 항목 번역 완료",
            )

        return state
    except Exception as exc:
        state["error"] = f"번역 오류: {exc}"
        return state


async def _translate_chunk_worker_with_progress(
    *,
    chunk: List[Dict[str, str]],
    state: TranslatorState,
    llm: Any,
    target_language: str,
    delay_manager: RequestDelayManager,
    semaphore: asyncio.Semaphore,
    chunk_num: int,
    total_chunks: int,
    progress_callback: Optional[callable] = None,
    is_retry: bool = False,
    temperature: float = 0.0,
) -> List[TranslatedItem]:
    """번역 청크 워커 (진행률 업데이트 포함)"""
    # 전체 글로시리에서 이 청크에 관련된 용어들만 필터링
    all_glossary_terms = state.get("important_terms", [])
    relevant_glossary = _filter_relevant_glossary_terms(chunk, all_glossary_terms)

    log_prefix = "retry" if is_retry else "translation"
    async with semaphore:
        await delay_manager.wait()

        # 진행률 콜백 호출 (청크 번역 시작)
        if progress_callback:
            progress_callback(
                "📝 번역 진행 중",
                chunk_num - 1,
                total_chunks,
                f"청크 {chunk_num}/{total_chunks} 번역 중 ({len(chunk)}개 항목)",
            )

        logger.info(
            _m(
                "translator.chunk_start",
                current=chunk_num,
                total=total_chunks,
                kind=log_prefix,
            )
        )

        # 글로시리 필터링 결과 로깅
        if all_glossary_terms:
            logger.info(
                f"📚 청크 {chunk_num}: 전체 글로시리 {len(all_glossary_terms)}개 중 "
                f"{len(relevant_glossary)}개 용어 포함"
            )

        glossary_str = TokenOptimizer.format_glossary_for_llm(relevant_glossary)
        chunk_str = TokenOptimizer.format_chunk_for_llm(chunk)

        # 번역 프롬프트 생성 (재시도 여부 반영)
        if is_retry:
            prompt = retry_translation_prompt(
                state["target_language"], glossary_str, chunk_str
            )
        else:
            prompt = translation_prompt(
                state["target_language"], glossary_str, chunk_str
            )

        try:
            # 다중 API 키 사용 시 새로운 클라이언트 가져오기
            current_llm = llm
            if state.get("use_multi_api_keys") and state.get("multi_llm_manager"):
                multi_manager = state["multi_llm_manager"]
                fresh_client = await multi_manager.get_client()
                if fresh_client:
                    current_llm = fresh_client
                    logger.debug(
                        f"청크 {chunk_num}: 다중 API 키에서 새 클라이언트 사용"
                    )
                else:
                    logger.warning(
                        f"청크 {chunk_num}: 다중 API 키 클라이언트 가져오기 실패, 기본 클라이언트 사용"
                    )

            # TranslatedItem을 도구로 바인딩하여 LLM 호출
            llm_with_tools = current_llm.bind_tools([TranslatedItem])
            response = await llm_with_tools.ainvoke(prompt)

            # LLM의 도구 호출에서 TranslatedItem 추출
            translations = []
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call["name"] == "TranslatedItem":
                        try:
                            item = TranslatedItem(**tool_call["args"])
                            # ID 패턴(T###) 그대로 반환되는 경우 필터링
                            if re.match(r"^T\d{3,}$", item.translated.strip()):
                                logger.debug(
                                    f"TranslatedItem returned ID unchanged for {item.id}, dropping."
                                )
                            else:
                                translations.append(item)
                        except Exception as e:
                            logger.warning(
                                f"TranslatedItem 파싱 중 오류: {e}, args: {tool_call['args']}"
                            )

            # 진행률 콜백 호출 (청크 번역 완료)
            if progress_callback:
                progress_callback(
                    "📝 번역 진행 중",
                    chunk_num,
                    total_chunks,
                    f"청크 {chunk_num}/{total_chunks} 완료 ({len(translations)}개 항목)",
                )

            return translations
        except Exception as exc:
            logger.error(f"청크 {chunk_num} 번역 실패: {exc}")

            # 다중 API 키 사용 시 해당 키의 실패를 기록
            if state.get("use_multi_api_keys") and state.get("multi_llm_manager"):
                # 실패한 키 정보는 MultiLLMManager에서 자동으로 처리됨
                logger.debug(f"청크 {chunk_num}: API 키 실패 기록됨")

            return []


def restore_placeholders_node(state: TranslatorState) -> TranslatorState:  # noqa: D401
    try:
        logger.info("플레이스홀더 복원 시작...")

        placeholders = state["placeholders"]
        newline_value = placeholders.get("[NEWLINE]")

        # Sort placeholders ONCE, excluding newline
        sorted_placeholders = sorted(
            (item for item in placeholders.items() if item[0] != "[NEWLINE]"),
            key=lambda item: (int(item[0][2:-1]) if item[0].startswith("[P") else -1),
            reverse=True,
        )

        # JSON 객체 레벨에서 안전하게 placeholder 복원
        restored_json = PlaceholderManager.restore_placeholders_in_json(
            state["translated_json"], sorted_placeholders, newline_value
        )

        # 복원된 JSON 객체를 문자열로 변환
        state["final_json"] = json.dumps(restored_json, ensure_ascii=False, indent=2)
        logger.info("플레이스홀더 복원 완료.")
        logger.info(_m("translator.placeholders_restore_finish"))
        return state
    except Exception as exc:
        state["error"] = f"Placeholder 복원 오류: {exc}"
        return state


def apply_translations_to_json(json_obj: Any, translation_map: Dict[str, str]) -> Any:  # noqa: D401
    if isinstance(json_obj, dict):
        return {
            k: apply_translations_to_json(v, translation_map)
            for k, v in json_obj.items()
        }
    if isinstance(json_obj, list):
        return [apply_translations_to_json(i, translation_map) for i in json_obj]
    if isinstance(json_obj, str):
        return translation_map.get(json_obj, json_obj)
    return json_obj


async def validation_and_retry_node(state: TranslatorState) -> TranslatorState:  # noqa: D401
    try:
        id_map = state["id_to_text_map"]
        translation_map = state["translation_map"]
        retry_count = state.get("retry_count", 0) + 1
        state["retry_count"] = retry_count

        # 번역되지 않은 항목 찾기 (지능적인 체크)
        to_retry = []
        placeholder_issues = 0

        for tid, orig in id_map.items():
            translated = translation_map.get(tid, "").strip()
            original = orig.strip()

            # 번역이 필요한 상황 체크
            should_retry = False
            retry_reason = ""

            # 1. 번역이 아예 없는 경우
            if not translated:
                should_retry = True
                retry_reason = "번역 누락"
            # 2. 번역 결과가 ID 패턴(T###)인 경우 (실제 번역이 아님)
            elif re.match(r"^T\d{3,}$", translated):
                should_retry = True
                retry_reason = "ID 그대로 반환"
            # 3. 원본이 의미있는 텍스트인데 번역이 비어있거나 플레이스홀더인 경우
            elif original:
                if len(translated) == 0:
                    should_retry = True
                    retry_reason = "빈 번역"
                elif not PlaceholderManager.validate_placeholder_preservation(
                    original, translated
                ):
                    should_retry = True
                    retry_reason = "플레이스홀더 누락"
                    placeholder_issues += 1

                    missing_placeholders = PlaceholderManager.get_missing_placeholders(
                        original, translated
                    )
                    logger.debug(
                        f"플레이스홀더 누락 감지: '{original}' -> '{translated}' "
                        f"(누락된 플레이스홀더: {missing_placeholders})"
                    )
                elif (
                    original.startswith("[P") and original.endswith("]")
                ) or original == "[NEWLINE]":
                    should_retry = False
                # 3. 번역 결과가 원본과 동일한 경우 (영어로 유지해야 하는 경우 제외)
                elif translated == original and len(original) > 3:
                    should_retry = True
                    retry_reason = "동일한 결과"
                    logger.debug(
                        f"번역 누락 감지: '{original}' -> '{translated}' (동일한 결과)"
                    )
            if should_retry:
                to_retry.append({"id": tid, "original": orig, "reason": retry_reason})

        if not to_retry:
            logger.info("모든 항목이 성공적으로 번역되었습니다.")
            logger.info(_m("translator.items_translated_ok"))
            return state

        # 재시도 이유별 통계 계산
        retry_reasons = {}
        for item in to_retry:
            reason = item.get("reason", "알 수 없음")
            retry_reasons[reason] = retry_reasons.get(reason, 0) + 1

        logger.warning(
            _m(
                "translator.missing_retry",
                missing=len(to_retry),
                attempt=retry_count,
                max_attempts=state["max_retries"],
            )
        )

        # 재시도 이유별 통계 출력
        if retry_reasons:
            logger.warning("재시도 이유별 통계:")
            for reason, count in retry_reasons.items():
                logger.warning(f"  - {reason}: {count}개")

        # 플레이스홀더 이슈가 있는 경우 특별히 로그
        if placeholder_issues > 0:
            logger.warning(f"🔧 플레이스홀더 누락 감지: {placeholder_issues}개 항목")

        # 재시도할 항목들의 ID 목록 저장 (디버깅용)
        retry_ids = [item["id"] for item in to_retry]
        logger.debug(f"재시도 대상 ID들: {retry_ids[:10]}...")  # 처음 10개만 로그

        # 디버깅: 처음 5개 재시도 항목의 상세 정보 출력
        if len(to_retry) > 100:  # 100개 이상일 때만 디버깅 출력
            logger.warning("🔍 재시도 대상 샘플 분석:")
            for i, item in enumerate(to_retry[:5]):
                original = item["original"].strip()
                translated = translation_map.get(item["id"], "").strip()
                reason = item.get("reason", "알 수 없음")
                logger.warning(
                    f"  샘플 {i + 1}: '{original}' -> '{translated}' (이유: {reason}, ID: {item['id']})"
                )
            logger.warning(f"  ... 총 {len(to_retry)}개 항목 중 처음 5개만 표시")

        # 진행률 콜백 호출 (재시도 시작)
        progress_callback = state.get("progress_callback")
        if progress_callback:
            progress_callback(
                "🔄 번역 재시도 중",
                0,
                len(to_retry),
                f"미번역 항목 {len(to_retry)}개 재시도 ({retry_count}차 시도)",
            )

        # LLM 클라이언트 가져오기
        llm = state.get("llm_client")
        if llm is None:
            logger.error("LLM 클라이언트가 설정되지 않았습니다")
            state["error"] = "LLM 클라이언트가 설정되지 않았습니다"
            return state
        retry_chunks = TokenOptimizer.create_text_chunks(
            to_retry, state["max_tokens_per_chunk"]
        )

        delay_mgr = RequestDelayManager(state["delay_between_requests_ms"])
        sem = asyncio.Semaphore(state["max_concurrent_requests"])

        # 재시도 횟수에 따라 temperature 동적 조정 (최대 1.0까지)
        retry_temperature = min(1.0, retry_count * 0.1)
        logger.info(f"번역 재시도 temperature: {retry_temperature}")

        tasks = [
            _translate_chunk_worker_with_progress(
                chunk=c,
                state=state,
                llm=llm,
                target_language=state["target_language"],
                delay_manager=delay_mgr,
                semaphore=sem,
                chunk_num=i,
                total_chunks=len(retry_chunks),
                progress_callback=progress_callback,
                is_retry=True,
                temperature=retry_temperature,  # 재시도 횟수에 따라 동적 조정
            )
            for i, c in enumerate(retry_chunks, 1)
        ]
        retry_results = await asyncio.gather(*tasks)

        # 재시도 결과 업데이트 (플레이스홀더 검증 포함)
        retry_count_success = 0
        retry_count_failed = 0
        retry_count_placeholder_fixed = 0

        for res in retry_results:
            for item in res:
                original_text = id_map.get(item.id, "").strip()
                new_translation = item.translated.strip()
                old_translation = translation_map.get(item.id, "").strip()

                # 번역이 유효한지 체크 (플레이스홀더 검증 포함)
                is_valid_translation = False
                validation_passed = False

                if new_translation:
                    # 1. 기본 번역 유효성 체크
                    if new_translation != old_translation:
                        # 이전 번역과 다르면 개선된 것으로 간주
                        is_valid_translation = True
                    elif new_translation != original_text:
                        # 원본과 다르면 유효
                        is_valid_translation = True
                    elif len(new_translation) >= 1:
                        # 최소 1글자 이상이면 유효 (너무 엄격했던 2글자 조건 완화)
                        is_valid_translation = True

                    # 2. 플레이스홀더 검증 (더 중요한 검증)
                    if is_valid_translation:
                        if PlaceholderManager.validate_placeholder_preservation(
                            original_text, new_translation
                        ):
                            validation_passed = True

                            # 플레이스홀더 이슈가 해결된 경우 추가 카운트
                            if not PlaceholderManager.validate_placeholder_preservation(
                                original_text, old_translation
                            ):
                                retry_count_placeholder_fixed += 1
                                logger.debug(
                                    f"플레이스홀더 복원 성공: {item.id} -> {new_translation[:50]}..."
                                )
                        else:
                            # 플레이스홀더가 여전히 누락된 경우
                            missing_placeholders = (
                                PlaceholderManager.get_missing_placeholders(
                                    original_text, new_translation
                                )
                            )
                            logger.debug(
                                f"재시도 후에도 플레이스홀더 누락: {item.id} -> '{new_translation}' "
                                f"(누락: {missing_placeholders})"
                            )
                            validation_passed = False

                if validation_passed:
                    translation_map[item.id] = new_translation
                    retry_count_success += 1
                    logger.debug(f"재시도 성공: {item.id} -> {new_translation[:50]}...")
                else:
                    retry_count_failed += 1
                    logger.debug(
                        f"재시도 실패: {item.id} -> '{new_translation}' (원본: '{original_text}')"
                    )

        # 진행률 콜백 호출 (재시도 완료)
        if progress_callback:
            status_msg = f"재시도 결과: 성공 {retry_count_success}개, 실패 {retry_count_failed}개"
            if retry_count_placeholder_fixed > 0:
                status_msg += f", 플레이스홀더 복원 {retry_count_placeholder_fixed}개"
            progress_callback(
                "🔄 번역 재시도 완료",
                len(retry_chunks),
                len(retry_chunks),
                status_msg,
            )

        log_msg = (
            f"재시도 완료: 성공 {retry_count_success}개, 실패 {retry_count_failed}개"
        )
        if retry_count_placeholder_fixed > 0:
            log_msg += f", 플레이스홀더 복원 {retry_count_placeholder_fixed}개"
        logger.info(log_msg)

        # 재시도 후에도 실패한 항목들이 있으면 로그 출력
        if retry_count_failed > 0:
            logger.warning(
                f"재시도 후에도 {retry_count_failed}개 항목이 번역되지 않았습니다."
            )

        return state

    except Exception as exc:
        logger.error(f"재시도 중 오류: {exc}")
        state["error"] = f"재시도 중 오류: {exc}"
        return state


async def _translate_single_item_worker(
    *,
    tid: str,
    state: TranslatorState,
    llm: Any,
    target_language: str,
    delay_manager: RequestDelayManager,
    semaphore: asyncio.Semaphore,
    max_retries: int = 2,
) -> tuple[str, Optional[str]]:
    """개별 항목 번역을 위한 비동기 워커 (재시도 기능 포함)"""
    async with semaphore:
        id_map = state["id_to_text_map"]
        original_text = id_map[tid]

        # 이 항목에 필요한 플레이스홀더 목록 추출
        required_placeholders = PlaceholderManager._extract_internal_placeholders(
            original_text
        )
        placeholders_str = (
            "\n".join(f"- `{p}`" for p in required_placeholders)
            if required_placeholders
            else "없음"
        )

        # 단일 항목에 대한 글로시리 추출 및 포맷팅
        all_glossary_terms = state.get("important_terms", [])
        relevant_glossary = _filter_relevant_glossary_terms(
            [{"original": original_text}], all_glossary_terms
        )
        glossary_str = TokenOptimizer.format_glossary_for_llm(relevant_glossary)

        # 재시도 루프
        last_error = None
        for attempt in range(max_retries + 1):
            await delay_manager.wait()

            # 새 프롬프트 사용
            prompt = final_fallback_prompt(
                language=target_language,
                text_id=tid,
                original_text=original_text,
                placeholders=placeholders_str,
                glossary=glossary_str,
            )

            try:
                # 다중 API 키 사용 시 새로운 클라이언트 가져오기
                current_llm = llm
                if state.get("use_multi_api_keys") and state.get("multi_llm_manager"):
                    multi_manager = state["multi_llm_manager"]
                    fresh_client = await multi_manager.get_client()
                    if fresh_client:
                        current_llm = fresh_client
                        logger.debug(
                            f"최종 번역 {tid}: 다중 API 키에서 새 클라이언트 사용"
                        )
                    else:
                        logger.warning(
                            f"최종 번역 {tid}: 다중 API 키 클라이언트 가져오기 실패, 기본 클라이언트 사용"
                        )

                # 재시도 시 temperature를 약간 높여 다른 결과 유도
                temperature = min(1.0, attempt * 0.2)
                configured_llm = current_llm.with_config(
                    configurable={"temperature": temperature}
                )
                llm_with_tools = configured_llm.bind_tools([TranslatedItem])

                response = await llm_with_tools.ainvoke(prompt)

                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        if (
                            tool_call["name"] == "TranslatedItem"
                            and tool_call["args"].get("id") == tid
                        ):
                            item = TranslatedItem(**tool_call["args"])
                            # 최종 검증: 플레이스홀더 보존 여부
                            if PlaceholderManager.validate_placeholder_preservation(
                                original_text, item.translated
                            ):
                                logger.info(
                                    f"✅ 최종 번역 재시도 성공 (시도 {attempt + 1}): {tid} -> {item.translated[:50]}..."
                                )
                                return tid, item.translated
                            elif re.match(r"^T\d{3,}$", item.translated):
                                last_error = "ID 그대로 반환"
                                logger.info(
                                    f"⚠️ 최종 번역 재시도({attempt + 1}) 후에도 ID 그대로 반환: {tid} -> {item.translated}"
                                )
                            else:
                                last_error = "플레이스홀더 누락"
                                logger.warning(
                                    f"⚠️ 최종 번역 재시도({attempt + 1}) 후에도 플레이스홀더 누락: {tid} -> '{item.translated}'"
                                )
                else:
                    last_error = "응답 없음"
                    # logger.warning(
                    #     f"⚠️ 최종 번역 재시도({attempt + 1}) 실패 (응답 없음): {tid}"
                    # )

            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"🚨 최종 번역 재시도({attempt + 1}) API 호출 오류 (항목: {tid}): {e}"
                )

                # 다중 API 키 사용 시 해당 키의 실패를 기록
                if state.get("use_multi_api_keys") and state.get("multi_llm_manager"):
                    logger.debug(f"최종 번역 {tid}: API 키 실패 기록됨")

            # 재시도 전 잠시 대기
            if attempt < max_retries:
                await asyncio.sleep(min(2.0, (attempt + 1) * 0.5))

        logger.error(
            f"❌ 최종 번역 모든 재시도 실패 ({max_retries + 1}회): {tid}, 마지막 오류: {last_error}"
        )
        return tid, None


async def final_fallback_translation_node(state: TranslatorState) -> TranslatorState:
    """최종적으로 누락된 항목들을 하나씩 다시 번역 요청합니다."""
    try:
        logger.info("최종 번역 단계 시작: 누락된 항목을 개별적으로 번역합니다.")
        logger.info(_m("translator.final_translation_start"))

        id_map = state["id_to_text_map"]
        translation_map = state["translation_map"]
        llm = state.get("llm_client")
        if llm is None:
            state["error"] = "LLM 클라이언트가 설정되지 않았습니다."
            return state

        # 번역되지 않은 항목 찾기 (should_retry와 동일한 로직)
        untranslated_items = []
        for tid, original_text in id_map.items():
            translated = translation_map.get(tid, "").strip()
            original = original_text.strip()
            needs_translation = False

            if not translated:
                needs_translation = True
            elif original:
                if len(translated) == 0:
                    needs_translation = True
                elif not PlaceholderManager.validate_placeholder_preservation(
                    original, translated
                ):
                    needs_translation = True
                elif (
                    original.startswith("[P") and original.endswith("]")
                ) or original == "[NEWLINE]":
                    needs_translation = False
                elif translated.strip() == original.strip() and len(original) > 3:
                    needs_translation = True

            if needs_translation:
                untranslated_items.append(tid)

        if not untranslated_items:
            logger.info("누락된 항목이 없습니다. 최종 번역 단계를 건너뜁니다.")
            logger.info(_m("translator.final_translation_skip_no_missing"))
            return state

        logger.info(
            f"{len(untranslated_items)}개의 누락된 항목에 대한 개별 번역을 시작합니다."
        )

        progress_callback = state.get("progress_callback")
        if progress_callback:
            progress_callback(
                "📝 최종 번역 중",
                0,
                len(untranslated_items),
                f"누락된 {len(untranslated_items)}개 항목 개별 번역 시작",
            )

        target_language = state["target_language"]
        delay_mgr = RequestDelayManager(state["delay_between_requests_ms"])
        sem = asyncio.Semaphore(state["max_concurrent_requests"])

        final_fallback_max_retries = state.get("final_fallback_max_retries", 4)
        logger.info(f"개별 항목당 최대 {final_fallback_max_retries}회 재시도합니다.")

        # 개별 요청이지만, 동시에 여러 개를 보내서 속도 향상
        tasks = []
        for tid in untranslated_items:
            tasks.append(
                _translate_single_item_worker(
                    tid=tid,
                    state=state,
                    llm=llm,
                    target_language=target_language,
                    delay_manager=delay_mgr,
                    semaphore=sem,
                    max_retries=final_fallback_max_retries,
                )
            )

        results = await asyncio.gather(*tasks)

        count_success = 0
        for i, (tid, new_translation) in enumerate(results):
            if new_translation:
                translation_map[tid] = new_translation
                count_success += 1

            if progress_callback:
                progress_callback(
                    "📝 최종 번역 중",
                    i + 1,
                    len(untranslated_items),
                    f"{i + 1}/{len(untranslated_items)} 항목 처리됨",
                )

        logger.info(
            f"최종 번역 완료. {count_success}/{len(untranslated_items)}개 항목 번역 성공."
        )

        return state

    except Exception as exc:
        state["error"] = f"최종 개별 번역 단계에서 오류 발생: {exc}"
        logger.error(f"최종 개별 번역 단계 오류: {traceback.format_exc()}")
        return state


def rebuild_json_node(state: TranslatorState) -> TranslatorState:  # noqa: D401
    try:
        logger.info("결과 JSON 재구성 시작...")
        logger.info(_m("translator.rebuild_json_start"))
        id_map = state["translation_map"]

        def replace(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: replace(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [replace(i) for i in obj]
            if isinstance(obj, str):
                # T001, T002 같은 ID가 translation_map에 있는지 확인
                if obj in id_map:
                    return id_map[obj]
                # ID 패턴이지만 번역이 없는 경우 경고
                elif re.match(r"^T\d{3,}$", obj):
                    logger.warning(f"번역되지 않은 ID 발견: {obj}")
                    # 원본 텍스트로 복원 시도
                    original_text = state["id_to_text_map"].get(obj, obj)
                    logger.warning(f"원본 텍스트로 복원: {obj} -> {original_text}")
                    return original_text
            return obj

        state["translated_json"] = replace(state["processed_json"])
        logger.info("결과 JSON 재구성 완료.")
        logger.info(_m("translator.rebuild_json_finish"))
        return state
    except Exception as exc:
        state["error"] = f"JSON 재구성 오류: {exc}"
        return state


def should_retry(state: TranslatorState) -> str:  # noqa: D401
    if state.get("error"):
        logger.error(_m("translator.error_abort", error=state["error"]))
        return "end"

    current_retry = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    id_map = state.get("id_to_text_map", {})
    translation_map = state.get("translation_map", {})

    if not id_map:
        return "complete"

    # 번역되지 않은 항목 체크 (지능적으로, 플레이스홀더 검증 포함)
    untranslated_items = []
    placeholder_failed_items = []

    for tid, original_text in id_map.items():
        translated = translation_map.get(tid, "").strip()
        original = original_text.strip()

        # 번역이 필요한 상황 체크
        needs_translation = False

        # 1. 번역이 아예 없는 경우
        if not translated:
            needs_translation = True
        # 2. 번역 결과가 ID 패턴(T###)인 경우 (실제 번역이 아님)
        elif re.match(r"^T\d{3,}$", translated):
            needs_translation = True
        # 3. 원본이 의미있는 텍스트인데 제대로 번역되지 않은 경우
        elif original:
            if len(translated) == 0:
                needs_translation = True
            elif re.match(r"^T\d{3,}$", translated):
                needs_translation = True
            elif not PlaceholderManager.validate_placeholder_preservation(
                original, translated
            ):
                needs_translation = True
                placeholder_failed_items.append(tid)
            elif (
                original.startswith("[P") and original.endswith("]")
            ) or original == "[NEWLINE]":
                needs_translation = False
            elif translated.strip() == original.strip() and len(original) > 3:
                needs_translation = True
        if needs_translation:
            untranslated_items.append(tid)

    needs_retry = len(untranslated_items) > 0

    if needs_retry and current_retry < max_retries:
        logger.info(
            _m(
                "translator.untranslated_retry",
                attempt=current_retry + 1,
                max_attempts=max_retries,
            )
        )
        logger.debug(f"재시도 필요한 항목 수: {len(untranslated_items)}")
        if placeholder_failed_items:
            logger.debug(f"플레이스홀더 누락 항목 수: {len(placeholder_failed_items)}")
        return "retry"
    elif needs_retry:
        logger.warning(_m("translator.max_retry_reached", max_attempts=max_retries))
        logger.warning(f"최종적으로 번역되지 않은 항목: {len(untranslated_items)}개")
        if placeholder_failed_items:
            logger.warning(f"플레이스홀더 누락 항목: {len(placeholder_failed_items)}개")
        # 번역되지 않은 항목이 있어도 완료로 처리 (무한 루프 방지)
        logger.info("개별 항목 재번역을 위한 최종 단계로 넘어갑니다.")
        logger.info(_m("translator.individual_retranslation_stage"))
        return "final_fallback"
    else:
        logger.info(_m("translator.translation_ok"))
        return "complete"


async def load_vanilla_glossary_node(state: TranslatorState) -> TranslatorState:
    """바닐라 마인크래프트 glossary를 로드합니다."""
    if not state.get("use_vanilla_glossary", False):
        state["vanilla_glossary"] = []
        return state

    vanilla_path = state.get("vanilla_glossary_path", "vanilla_glossary.json")

    # 한국어인 경우 미리 준비된 사전 경로 사용
    target_language = state.get("target_language", "")
    if target_language == "한국어" and vanilla_path == "vanilla_glossary.json":
        # 기본 경로인 경우만 미리 준비된 사전으로 변경
        preset_path = "src/assets/vanilla_glossary/ko_kr.json"
        if Path(preset_path).exists():
            vanilla_path = preset_path
            logger.info("한국어 타겟 언어 감지, 미리 준비된 바닐라 사전 사용")
            logger.info(_m("translator.use_vanilla_glossary"))

    try:
        # 바닐라 glossary builder를 동적으로 임포트 (순환 임포트 방지)
        from .vanilla_glossary_builder import VanillaGlossaryBuilder

        builder = VanillaGlossaryBuilder()

        # 진행률 콜백 호출
        progress_callback = state.get("progress_callback")
        if progress_callback:
            progress_callback(
                "🎮 바닐라 사전 로드 중",
                0,
                1,
                "바닐라 마인크래프트 사전을 로드하고 있습니다...",
            )

        vanilla_glossary = await builder.create_or_load_vanilla_glossary(
            glossary_path=vanilla_path,
            force_rebuild=False,  # 기존 파일이 있으면 로드, 없으면 생성
            max_entries_per_batch=200,
            max_concurrent_requests=3,
            progress_callback=progress_callback,
        )

        state["vanilla_glossary"] = vanilla_glossary

        if progress_callback:
            progress_callback(
                "🎮 바닐라 사전 로드 완료",
                1,
                1,
                f"바닐라 사전 {len(vanilla_glossary)}개 용어 로드 완료",
            )

        logger.info(f"바닐라 glossary 로드 완료: {len(vanilla_glossary)}개 용어")

    except Exception as exc:
        logger.warning(f"바닐라 glossary 로드 실패: {exc}")
        state["vanilla_glossary"] = []

    return state


def load_glossary_node(state: TranslatorState) -> TranslatorState:
    """Load existing glossary from the specified file path."""
    path = state.get("glossary_path")
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                state["important_terms"] = [GlossaryEntry(**item) for item in data]
                logger.info(
                    _m(
                        "translator.glossary_loaded",
                        count=len(state["important_terms"]),
                        path=path,
                    )
                )
        except (IOError, json.JSONDecodeError, TypeError) as exc:
            logger.warning(_m("translator.glossary_load_error", path=path, error=exc))
            state["important_terms"] = []
    else:
        state["important_terms"] = []
    return state


def save_glossary_node(state: TranslatorState) -> TranslatorState:
    """Save the final glossary to the specified file path."""
    path = state.get("glossary_path")
    glossary = state.get("important_terms")
    if path and glossary:
        try:
            logger.info("용어집 저장 시작...")
            logger.info(_m("translator.glossary_save_start"))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    [term.dict() for term in glossary], f, ensure_ascii=False, indent=2
                )
            logger.info(_m("translator.glossary_saved", count=len(glossary), path=path))
        except IOError as exc:
            logger.error(_m("translator.glossary_save_error", path=path, error=exc))
    return state


def create_primary_glossary_node(state: TranslatorState) -> TranslatorState:
    """기존 번역 데이터로 1차 사전을 구축합니다."""
    existing_translations = state.get("existing_translations")
    if not existing_translations:
        logger.info("기존 번역 데이터가 없어 1차 사전 구축을 건너뜁니다.")
        state["primary_glossary"] = []
        logger.info(_m("translator.primary_glossary_skip"))
        return state

    logger.info(f"기존 번역 데이터 {len(existing_translations)}개로 1차 사전 구축 시작")

    # 진행률 콜백 호출
    progress_callback = state.get("progress_callback")
    if progress_callback:
        progress_callback(
            "📖 1차 사전 구축 중",
            0,
            len(existing_translations),
            f"기존 번역 데이터 {len(existing_translations)}개 분석 중",
        )

    primary_terms = []
    processed_count = 0
    korean_translated_count = 0
    valid_term_count = 0

    # 기존 번역 데이터를 GlossaryEntry로 변환
    for source_text, target_text in existing_translations.items():
        try:
            # 타겟 텍스트가 한글인지 확인
            if is_korean_text(target_text):
                korean_translated_count += 1

                # 간단한 용어 추출 (단어 단위)
                words = source_text.split()
                if len(words) <= 3:  # 3단어 이하의 짧은 표현만 용어로 간주
                    valid_term_count += 1

                    # 이미 존재하는 용어인지 확인
                    existing_term = None
                    for term in primary_terms:
                        if term.original.lower() == source_text.lower():
                            existing_term = term
                            break

                    if existing_term:
                        # 기존 용어에 새로운 의미 추가 (중복 방지)
                        new_meaning = TermMeaning(
                            translation=target_text, context="기존 번역"
                        )

                        # 중복 체크 (번역만 비교)
                        translation_exists = any(
                            m.translation.lower().strip() == target_text.lower().strip()
                            for m in existing_term.meanings
                        )

                        if not translation_exists:
                            existing_term.meanings.append(new_meaning)
                    else:
                        # 새로운 용어 추가
                        new_term = GlossaryEntry(
                            original=source_text,
                            meanings=[
                                TermMeaning(
                                    translation=target_text, context="기존 번역"
                                )
                            ],
                        )
                        primary_terms.append(new_term)

            processed_count += 1

            # 진행률 업데이트 (500개마다)
            if processed_count % 500 == 0 and progress_callback:
                progress_callback(
                    "📖 1차 사전 구축 중",
                    processed_count,
                    len(existing_translations),
                    f"{processed_count}/{len(existing_translations)} 항목 처리됨",
                )

        except Exception as e:
            logger.debug(f"용어 처리 중 오류 ({source_text}): {e}")

    # 최종적으로 모든 용어에서 중복 의미 제거
    for term in primary_terms:
        term.meanings = TokenOptimizer.deduplicate_glossary_meanings(term.meanings)

    state["primary_glossary"] = primary_terms

    # 진행률 콜백 호출 (완료)
    if progress_callback:
        progress_callback(
            "📖 1차 사전 구축 완료",
            len(existing_translations),
            len(existing_translations),
            f"총 {len(primary_terms)}개 용어가 포함된 1차 사전 구축 완료",
        )

    logger.info(f"1차 사전 구축 완료: {len(primary_terms)}개 용어 생성")
    logger.info(
        f"한글 번역 항목: {korean_translated_count}개, 유효 용어: {valid_term_count}개"
    )
    return state


async def quality_review_node(state: TranslatorState) -> TranslatorState:
    """번역 품질을 검토하는 노드"""
    try:
        # 품질 검토가 비활성화된 경우 건너뛰기
        if not state.get("enable_quality_review", True):
            logger.info("품질 검토가 비활성화되어 건너뜁니다.")
            logger.info(_m("translator.quality_review_disabled"))
            return state

        logger.info("번역 품질 검토 시작...")
        logger.info(_m("translator.quality_review_start"))

        id_map = state["id_to_text_map"]
        translation_map = state["translation_map"]
        llm = state.get("llm_client")

        if not llm or not id_map or not translation_map:
            logger.info("품질 검토를 건너뜁니다 (필수 데이터 없음)")
            logger.info(_m("translator.quality_review_skip_missing_data"))
            return state

        # 검토할 항목들 준비 (번역된 것만)
        placeholder_only_pattern = r"^\[(P\d{3,}|NEWLINE)\]$"
        review_items = []
        for tid, original_text in id_map.items():
            translated_text = translation_map.get(tid, "")
            if not translated_text.strip():
                continue

            # 원문과 번역이 모두 내부 플레이스홀더만으로 이루어진 경우 품질 검토 건너뜀
            if re.match(placeholder_only_pattern, original_text.strip()) and re.match(
                placeholder_only_pattern, translated_text.strip()
            ):
                continue

            review_items.append(
                {
                    "id": tid,
                    "original": original_text,
                    "translated": translated_text,
                }
            )

        if not review_items:
            logger.info("검토할 번역 항목이 없습니다.")
            logger.info(_m("translator.quality_review_no_items"))
            return state

        logger.info(f"품질 검토 대상: {len(review_items)}개 항목")

        # 진행률 콜백 호출
        progress_callback = state.get("progress_callback")
        if progress_callback:
            progress_callback(
                "🔍 번역 품질 검토 중",
                0,
                len(review_items),
                f"총 {len(review_items)}개 항목 품질 검토 시작",
            )

        # 2000글자 청크로 나누기
        chunks = _create_quality_review_chunks(review_items, max_chars=4000)
        logger.info(f"품질 검토를 위해 {len(chunks)}개 청크로 분할")

        # 동시 요청 제한
        sem = asyncio.Semaphore(state["max_concurrent_requests"])
        delay_mgr = RequestDelayManager(state["delay_between_requests_ms"])

        # 각 청크별로 품질 검토 실행
        tasks = []
        for chunk_idx, chunk in enumerate(chunks):
            tasks.append(
                _review_chunk_worker(
                    chunk=chunk,
                    target_language=state["target_language"],
                    llm=llm,
                    state=state,
                    semaphore=sem,
                    delay_manager=delay_mgr,
                    chunk_idx=chunk_idx,
                    total_chunks=len(chunks),
                    progress_callback=progress_callback,
                )
            )

        review_results = await asyncio.gather(*tasks)

        # 결과 집계 - 각 청크에서 개별 QualityIssue들을 수집
        all_issues = []

        for review_result in review_results:
            if review_result:  # review_result는 List[QualityIssue]
                all_issues.extend(review_result)

        # 품질 검토 결과 로깅
        if all_issues:
            logger.warning(f"🔍 품질 검토 결과: {len(all_issues)}개 문제 발견")

            # 심각도별 분류
            severity_counts = {}
            issue_type_counts = {}

            for issue in all_issues:
                severity_counts[issue.severity] = (
                    severity_counts.get(issue.severity, 0) + 1
                )
                issue_type_counts[issue.issue_type] = (
                    issue_type_counts.get(issue.issue_type, 0) + 1
                )

            logger.warning("심각도별 분류:")
            for severity, count in severity_counts.items():
                logger.warning(f"  - {severity}: {count}개")

            logger.warning("문제 유형별 분류:")
            for issue_type, count in issue_type_counts.items():
                logger.warning(f"  - {issue_type}: {count}개")

            # 심각한 문제들 상세 로깅
            high_severity_issues = [
                issue for issue in all_issues if issue.severity == "high"
            ]
            if high_severity_issues:
                logger.warning(f"🚨 심각한 문제 {len(high_severity_issues)}개:")
                for issue in high_severity_issues[:5]:  # 최대 5개만 표시
                    logger.warning(
                        f"  - [{issue.text_id}] {issue.issue_type}: {issue.description}"
                    )
                    if issue.suggested_fix:
                        logger.warning(f"    제안: {issue.suggested_fix}")
        else:
            logger.info("✅ 품질 검토 결과: 심각한 문제 없음")
            logger.info(_m("translator.quality_review_no_critical"))

        # 전체 품질 점수 계산은 개별 QualityIssue 방식에서는 생략
        # 대신 심각도별 통계를 통해 전체 품질 상태를 파악

        # 진행률 콜백 호출 (완료)
        if progress_callback:
            summary = f"품질 검토 완료 - 문제 {len(all_issues)}개 발견"
            progress_callback(
                "🔍 번역 품질 검토 완료", len(chunks), len(chunks), summary
            )

        # 상태에 검토 결과 저장 (선택사항)
        state["quality_issues"] = all_issues

        return state

    except Exception as exc:
        logger.error(f"품질 검토 중 오류: {exc}")
        logger.error(traceback.format_exc())
        # 품질 검토 실패는 전체 프로세스를 중단하지 않음
        return state


def _create_quality_review_chunks(
    review_items: List[Dict], max_chars: int = 2000
) -> List[List[Dict]]:
    """품질 검토를 위해 항목들을 청크로 나눕니다."""
    chunks = []
    current_chunk = []
    current_chars = 0

    for item in review_items:
        # 항목의 예상 문자 수 계산 (ID + 원본 + 번역 + 포맷팅)
        item_chars = (
            len(item["id"]) + len(item["original"]) + len(item["translated"]) + 50
        )

        # 단일 항목이 max_chars를 초과하는 경우 별도 청크로 처리
        if item_chars > max_chars:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_chars = 0
            chunks.append([item])
        # 현재 청크에 추가했을 때 제한을 초과하는 경우
        elif current_chars + item_chars > max_chars:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = [item]
            current_chars = item_chars
        # 현재 청크에 추가
        else:
            current_chunk.append(item)
            current_chars += item_chars

    # 마지막 청크 추가
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def _review_chunk_worker(
    *,
    chunk: List[Dict],
    target_language: str,
    llm: Any,
    state: TranslatorState,
    semaphore: asyncio.Semaphore,
    delay_manager: RequestDelayManager,
    chunk_idx: int,
    total_chunks: int,
    progress_callback: Optional[callable] = None,
) -> List[QualityIssue]:
    """청크별 품질 검토를 수행하는 워커 - 개별 QualityIssue들을 반환"""
    async with semaphore:
        await delay_manager.wait()

        # 진행률 콜백 호출
        if progress_callback:
            progress_callback(
                "🔍 번역 품질 검토 중",
                chunk_idx,
                total_chunks,
                f"청크 {chunk_idx + 1}/{total_chunks} 검토 중 ({len(chunk)}개 항목)",
            )

        try:
            # 다중 API 키 사용 시 새로운 클라이언트 가져오기
            current_llm = llm
            if state.get("use_multi_api_keys") and state.get("multi_llm_manager"):
                multi_manager = state["multi_llm_manager"]
                fresh_client = await multi_manager.get_client()
                if fresh_client:
                    current_llm = fresh_client
                    logger.debug(
                        f"품질 검토 청크 {chunk_idx + 1}: 다중 API 키에서 새 클라이언트 사용"
                    )
                else:
                    logger.warning(
                        f"품질 검토 청크 {chunk_idx + 1}: 다중 API 키 클라이언트 가져오기 실패, 기본 클라이언트 사용"
                    )

            # 검토용 텍스트 포맷팅
            review_text = _format_chunk_for_quality_review(chunk)

            # 품질 검토 프롬프트 생성
            from src.prompts.llm_prompts import quality_review_prompt

            prompt = quality_review_prompt(target_language, review_text)

            # LLM 호출 - QualityIssue 도구 바인딩
            llm_with_tools = current_llm.bind_tools([QualityIssue])
            response = await llm_with_tools.ainvoke(prompt)

            # 응답 파싱 - 개별 QualityIssue들 수집
            quality_issues = []
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call["name"] == "QualityIssue":
                        try:
                            issue = QualityIssue(**tool_call["args"])
                            quality_issues.append(issue)
                            logger.debug(
                                f"품질 문제 발견: [{issue.text_id}] {issue.issue_type} ({issue.severity})"
                            )
                        except Exception as e:
                            logger.warning(
                                f"QualityIssue 파싱 오류: {e}, args: {tool_call['args']}"
                            )

            logger.debug(
                f"청크 {chunk_idx + 1} 품질 검토 완료: {len(quality_issues)}개 문제 발견"
            )
            return quality_issues

        except Exception as exc:
            logger.error(f"청크 {chunk_idx + 1} 품질 검토 실패: {exc}")

            # 다중 API 키 사용 시 해당 키의 실패를 기록
            if state.get("use_multi_api_keys") and state.get("multi_llm_manager"):
                logger.debug(f"품질 검토 청크 {chunk_idx + 1}: API 키 실패 기록됨")

            return []


def _format_chunk_for_quality_review(chunk: List[Dict]) -> str:
    """품질 검토용 청크 포맷팅"""
    lines = []

    for item in chunk:
        text_id = item["id"]
        original = item["original"]
        translated = item["translated"]

        lines.append(f"[{text_id}]")
        lines.append(f"원본: {original}")
        lines.append(f"번역: {translated}")
        lines.append("")  # 빈 줄 추가

    return "\n".join(lines)


def should_retranslate_based_on_quality(state: TranslatorState) -> str:
    """품질 검토 결과에 따라 재번역 여부를 결정합니다."""
    if state.get("error"):
        return "end"

    quality_issues = state.get("quality_issues", [])

    # 모든 품질 문제를 재번역 대상으로 고려
    if quality_issues:
        quality_retry_count = state.get("quality_retry_count", 0)
        max_quality_retries = state.get("max_quality_retries", 2)

        if quality_retry_count < max_quality_retries:
            logger.info(
                f"품질 검토 결과 {len(quality_issues)}개 문제 발견, 재번역 진행 ({quality_retry_count + 1}/{max_quality_retries})"
            )
            return "quality_retranslate"
        else:
            logger.warning(
                f"품질 기반 재번역 최대 횟수 ({max_quality_retries}) 도달, 완료로 진행"
            )
            return "complete"
    else:
        logger.info("품질 검토 결과 문제 없음, 완료로 진행")
        logger.info(_m("translator.quality_review_ok_complete"))
        return "complete"


async def quality_based_retranslation_node(state: TranslatorState) -> TranslatorState:
    """품질 검토 결과를 바탕으로 문제가 있는 항목들을 다시 번역합니다."""
    try:
        quality_issues = state.get("quality_issues", [])
        id_map = state["id_to_text_map"]
        translation_map = state["translation_map"]
        llm = state.get("llm_client")

        # 재번역 카운터 증가
        quality_retry_count = state.get("quality_retry_count", 0) + 1
        state["quality_retry_count"] = quality_retry_count

        logger.info(f"품질 기반 재번역 시작 ({quality_retry_count}차 시도)")

        # 모든 품질 문제가 있는 항목들 추출
        all_issues = quality_issues

        # 재번역할 항목들 준비
        items_to_retranslate = []
        for issue in all_issues:
            text_id = issue.text_id
            if text_id in id_map:
                original_text = id_map[text_id]
                current_translation = translation_map.get(text_id, "")

                items_to_retranslate.append(
                    {
                        "id": text_id,
                        "original": original_text,
                        "current_translation": current_translation,
                        "issue": issue,
                    }
                )

        # 중복 제거 (같은 ID가 여러 문제로 중복될 수 있음)
        unique_items = {}
        for item in items_to_retranslate:
            text_id = item["id"]
            if text_id not in unique_items:
                unique_items[text_id] = item
            else:
                # 기존 항목에 추가 이슈 정보 병합
                if "issues" not in unique_items[text_id]:
                    unique_items[text_id]["issues"] = [unique_items[text_id]["issue"]]
                    del unique_items[text_id]["issue"]
                unique_items[text_id]["issues"].append(item["issue"])

        items_to_retranslate = list(unique_items.values())

        if not items_to_retranslate:
            logger.info("재번역할 항목이 없습니다.")
            logger.info(_m("translator.no_items_for_retranslation"))
            return state

        logger.info(
            f"품질 문제로 {len(items_to_retranslate)}개 항목 재번역 진행 (전체 문제 {len(all_issues)}개)"
        )

        # 진행률 콜백 호출
        progress_callback = state.get("progress_callback")
        if progress_callback:
            progress_callback(
                "🔄 품질 기반 재번역 중",
                0,
                len(items_to_retranslate),
                f"품질 문제 {len(items_to_retranslate)}개 항목 재번역 시작",
            )

        # 청크로 나누기
        chunks = TokenOptimizer.create_text_chunks(
            items_to_retranslate, state["max_tokens_per_chunk"]
        )

        # 동시 요청 제한
        sem = asyncio.Semaphore(state["max_concurrent_requests"])
        delay_mgr = RequestDelayManager(state["delay_between_requests_ms"])

        # 재번역 실행
        tasks = []
        for chunk_idx, chunk in enumerate(chunks):
            tasks.append(
                _quality_retranslate_chunk_worker(
                    chunk=chunk,
                    state=state,
                    llm=llm,
                    target_language=state["target_language"],
                    delay_manager=delay_mgr,
                    semaphore=sem,
                    chunk_idx=chunk_idx,
                    total_chunks=len(chunks),
                    progress_callback=progress_callback,
                    max_retries=3,  # 품질 기반 재번역에서는 더 많은 재시도
                )
            )

        results = await asyncio.gather(*tasks)

        # 결과 업데이트
        success_count = 0
        failed_count = 0

        for chunk_results in results:
            for item in chunk_results:
                text_id = item.id
                new_translation = item.translated.strip()
                original_text = id_map.get(text_id, "")

                # 플레이스홀더 검증
                if PlaceholderManager.validate_placeholder_preservation(
                    original_text, new_translation
                ):
                    translation_map[text_id] = new_translation
                    success_count += 1
                    logger.debug(
                        f"품질 재번역 성공: {text_id} -> {new_translation[:50]}..."
                    )
                else:
                    failed_count += 1
                    missing_placeholders = PlaceholderManager.get_missing_placeholders(
                        original_text, new_translation
                    )
                    logger.warning(
                        f"품질 재번역 후에도 플레이스홀더 누락: {text_id} (누락: {missing_placeholders})"
                    )

        # 진행률 콜백 호출 (완료)
        if progress_callback:
            progress_callback(
                "🔄 품질 기반 재번역 완료",
                len(chunks),
                len(chunks),
                f"성공: {success_count}개, 실패: {failed_count}개",
            )

        logger.info(
            f"품질 기반 재번역 완료: 성공 {success_count}개, 실패 {failed_count}개"
        )

        # 재번역을 한 번 수행했으므로 이후 품질 검토는 생략하도록 플래그 비활성화
        # (무한 루프 및 불필요한 추가 품질 검토 방지)
        state["enable_quality_review"] = False

        # JSON 재구성 및 플레이스홀더 복원
        try:
            # JSON 재구성
            logger.info("품질 재번역 후 JSON 재구성 시작...")
            id_map = state["translation_map"]

            def replace(obj: Any) -> Any:
                if isinstance(obj, dict):
                    return {k: replace(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [replace(i) for i in obj]
                if isinstance(obj, str) and obj in id_map:
                    return id_map[obj]
                return obj

            state["translated_json"] = replace(state["processed_json"])
            logger.info("품질 재번역 후 JSON 재구성 완료.")

            # 플레이스홀더 복원
            logger.info("품질 재번역 후 플레이스홀더 복원 시작...")
            placeholders = state["placeholders"]
            newline_value = placeholders.get("[NEWLINE]")

            # Sort placeholders ONCE, excluding newline
            sorted_placeholders = sorted(
                (item for item in placeholders.items() if item[0] != "[NEWLINE]"),
                key=lambda item: (
                    int(item[0][2:-1]) if item[0].startswith("[P") else -1
                ),
                reverse=True,
            )

            # JSON 객체 레벨에서 안전하게 placeholder 복원
            restored_json = PlaceholderManager.restore_placeholders_in_json(
                state["translated_json"], sorted_placeholders, newline_value
            )

            # 복원된 JSON 객체를 문자열로 변환
            state["final_json"] = json.dumps(
                restored_json, ensure_ascii=False, indent=2
            )
            logger.info("품질 재번역 후 플레이스홀더 복원 완료.")

        except Exception as exc:
            logger.error(f"품질 재번역 후 JSON 처리 중 오류: {exc}")
            state["error"] = f"품질 재번역 후 JSON 처리 중 오류: {exc}"

        return state

    except Exception as exc:
        logger.error(f"품질 기반 재번역 중 오류: {exc}")
        logger.error(traceback.format_exc())
        return state


async def _quality_retranslate_chunk_worker(
    *,
    chunk: List[Dict],
    state: TranslatorState,
    llm: Any,
    target_language: str,
    delay_manager: RequestDelayManager,
    semaphore: asyncio.Semaphore,
    chunk_idx: int,
    total_chunks: int,
    progress_callback: Optional[callable] = None,
    max_retries: int = 3,
) -> List[TranslatedItem]:
    """품질 기반 재번역을 위한 청크 워커"""
    async with semaphore:
        await delay_manager.wait()

        # 진행률 콜백 호출
        if progress_callback:
            progress_callback(
                "🔄 품질 기반 재번역 중",
                chunk_idx,
                total_chunks,
                f"청크 {chunk_idx + 1}/{total_chunks} 재번역 중 ({len(chunk)}개 항목)",
            )

        # 글로시리에서 관련 용어 필터링
        all_glossary_terms = state.get("important_terms", [])
        relevant_glossary = _filter_relevant_glossary_terms(chunk, all_glossary_terms)

        # 재번역 시도
        for attempt in range(max_retries + 1):
            try:
                # 다중 API 키 사용 시 새로운 클라이언트 가져오기
                current_llm = llm
                if state.get("use_multi_api_keys") and state.get("multi_llm_manager"):
                    multi_manager = state["multi_llm_manager"]
                    fresh_client = await multi_manager.get_client()
                    if fresh_client:
                        current_llm = fresh_client
                        logger.debug(
                            f"품질 재번역 청크 {chunk_idx + 1}: 다중 API 키에서 새 클라이언트 사용"
                        )
                    else:
                        logger.warning(
                            f"품질 재번역 청크 {chunk_idx + 1}: 다중 API 키 클라이언트 가져오기 실패, 기본 클라이언트 사용"
                        )

                # 프롬프트 생성 (품질 문제를 고려한 상세한 프롬프트)
                glossary_text = TokenOptimizer.format_glossary_for_llm(
                    relevant_glossary
                )
                retry_info = (
                    f"⚠️ 재시도 {attempt}회 - 이전 번역에서 문제가 있었습니다. 특히 다음 사항들을 주의깊게 확인해주세요: 1. 플레이스홀더([P###], [NEWLINE] 등)를 정확히 보존 2. 원문의 의미를 정확히 전달 3. 자연스럽고 일관된 번역"
                    if attempt > 0
                    else "품질 문제 해결을 위한 재번역"
                )
                formatted_items = _format_items_for_quality_retranslation(chunk)

                prompt = quality_retranslation_prompt(
                    target_language, glossary_text, retry_info, formatted_items
                )

                # LLM 호출
                llm_with_tools = current_llm.bind_tools([TranslatedItem])
                response = await llm_with_tools.ainvoke(prompt)

                # 응답 파싱
                translations = []
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        if tool_call["name"] == "TranslatedItem":
                            try:
                                item = TranslatedItem(**tool_call["args"])
                                translations.append(item)
                            except Exception as e:
                                logger.warning(f"TranslatedItem 파싱 오류: {e}")

                # 플레이스홀더 검증
                valid_translations = []
                for translation in translations:
                    original_text = next(
                        (
                            item["original"]
                            for item in chunk
                            if item["id"] == translation.id
                        ),
                        "",
                    )

                    # ID 패턴(T###)이 그대로 반환된 경우 무시
                    if re.match(r"^T\d{3,}$", translation.translated.strip()):
                        logger.debug(f"ID 그대로 반환된 항목 무시: {translation.id}")
                        continue

                    if PlaceholderManager.validate_placeholder_preservation(
                        original_text, translation.translated
                    ):
                        valid_translations.append(translation)
                    else:
                        logger.debug(f"플레이스홀더 검증 실패: {translation.id}")

                # 모든 번역이 유효하면 성공
                if len(valid_translations) == len(chunk):
                    if attempt > 0:
                        logger.info(
                            f"품질 재번역 청크 {chunk_idx + 1} 성공 (재시도 {attempt}회)"
                        )
                    return valid_translations
                else:
                    logger.warning(
                        f"품질 재번역 청크 {chunk_idx + 1} 시도 {attempt + 1}: 유효한 번역 {len(valid_translations)}/{len(chunk)}"
                    )

                    # 마지막 시도가 아니면 계속 진행
                    if attempt < max_retries:
                        await asyncio.sleep(min(2.0, (attempt + 1) * 0.5))
                        continue
                    else:
                        # 마지막 시도에서는 유효한 번역이라도 반환
                        return valid_translations

            except Exception as exc:
                logger.error(
                    f"품질 재번역 청크 {chunk_idx + 1} 시도 {attempt + 1} 실패: {exc}"
                )

                # 다중 API 키 사용 시 해당 키의 실패를 기록
                if state.get("use_multi_api_keys") and state.get("multi_llm_manager"):
                    logger.debug(
                        f"품질 재번역 청크 {chunk_idx + 1}: API 키 실패 기록됨"
                    )

                if attempt < max_retries:
                    await asyncio.sleep(min(2.0, (attempt + 1) * 0.5))
                else:
                    return []

        return []


def _format_items_for_quality_retranslation(chunk: List[Dict]) -> str:
    """품질 기반 재번역을 위한 프롬프트 생성에 필요한 포맷팅"""
    lines = []
    for i, item in enumerate(chunk, 1):
        text_id = item["id"]
        original = item["original"]
        current_translation = item.get("current_translation", "")

        # 품질 문제 정보 추가
        issues = item.get("issues", [item.get("issue")] if item.get("issue") else [])

        lines.append(f"{i}. [{text_id}]")
        lines.append(f"   원본: {original}")
        if current_translation:
            lines.append(f"   이전 번역: {current_translation}")

        if issues:
            lines.append("   발견된 문제:")
            for issue in issues:
                if issue:
                    lines.append(f"   - {issue.issue_type}: {issue.description}")
                    if issue.suggested_fix:
                        lines.append(f"     제안: {issue.suggested_fix}")

        lines.append("")

    return "\n".join(lines)


###############################################################################
# 4. Main translator class                                                    #
###############################################################################


class JSONTranslator:
    """JSON 번역기"""

    def __init__(self, *, glossary_path: Optional[str] = None) -> None:
        self.glossary_path = glossary_path
        self.token_counter = UniversalTokenCountingHandler()
        self._workflow = self._create_workflow()

    def _create_workflow(self) -> StateGraph:  # noqa: D401
        """Create the translation workflow."""
        wf = StateGraph(TranslatorState)

        # Add nodes
        wf.add_node("parse_and_extract", parse_and_extract_node)
        wf.add_node("load_vanilla_glossary", load_vanilla_glossary_node)
        wf.add_node("load_glossary", load_glossary_node)
        wf.add_node(
            "extract_terms_from_json_chunks", extract_terms_from_json_chunks_node
        )
        wf.add_node("smart_translate", smart_translate_node)
        wf.add_node("validation_and_retry", validation_and_retry_node)
        wf.add_node("final_fallback_translation", final_fallback_translation_node)
        wf.add_node("rebuild_json", rebuild_json_node)
        wf.add_node("restore_placeholders", restore_placeholders_node)
        wf.add_node("quality_review", quality_review_node)
        wf.add_node("quality_based_retranslation", quality_based_retranslation_node)
        wf.add_node("save_glossary", save_glossary_node)
        wf.add_node("final_check", lambda state: state)

        # Set entry point
        wf.set_entry_point("parse_and_extract")

        # Define edges
        wf.add_edge("parse_and_extract", "load_vanilla_glossary")
        wf.add_edge("load_vanilla_glossary", "load_glossary")
        wf.add_edge("load_glossary", "extract_terms_from_json_chunks")
        wf.add_edge("extract_terms_from_json_chunks", "smart_translate")

        # Main translation path with retries
        wf.add_conditional_edges(
            "smart_translate",
            should_retry,
            {
                "retry": "validation_and_retry",
                "complete": "rebuild_json",
                "end": "final_check",  # Go to final check on error
                "final_fallback": "final_fallback_translation",
            },
        )
        wf.add_conditional_edges(
            "validation_and_retry",
            should_retry,
            {
                "retry": "validation_and_retry",
                "complete": "rebuild_json",
                "end": "final_check",  # Go to final check on error
                "final_fallback": "final_fallback_translation",
            },
        )

        # Success path
        wf.add_edge("final_fallback_translation", "rebuild_json")
        wf.add_edge("rebuild_json", "restore_placeholders")

        # 품질 검토를 재번역 전 한 번만 수행하도록 조건부 분기
        wf.add_conditional_edges(
            "restore_placeholders",
            should_run_quality_review,
            {"review": "quality_review", "skip": "final_check"},
        )

        # Quality review based retranslation
        wf.add_conditional_edges(
            "quality_review",
            should_retranslate_based_on_quality,
            {
                "quality_retranslate": "quality_based_retranslation",
                "complete": "final_check",
                "end": "final_check",
            },
        )

        # After quality-based retranslation, go directly to final check
        wf.add_edge("quality_based_retranslation", "final_check")

        # Final check to decide on saving
        wf.add_conditional_edges(
            "final_check",
            should_save_glossary,
            {"save_glossary": "save_glossary", "end": END},
        )
        wf.add_edge("save_glossary", END)

        return wf.compile()

    def get_token_summary(self) -> Dict[str, Any]:
        """토큰 사용량 요약 반환"""
        return self.token_counter.get_token_summary()

    def get_formatted_token_summary(self) -> str:
        """포맷된 토큰 사용량 요약 반환"""
        return self.token_counter.get_formatted_summary()

    def reset_token_counter(self):
        """토큰 카운터 초기화"""
        self.token_counter.reset_counts()

    async def translate(
        self,
        json_input: Any,
        target_language: str = "한국어",
        *,
        use_glossary: bool = True,
        use_vanilla_glossary: bool = True,
        vanilla_glossary_path: Optional[str] = None,
        max_retries: int = 3,
        max_tokens_per_chunk: int = 3000,
        max_concurrent_requests: int = 5,
        delay_between_requests_ms: int = 200,
        progress_callback: Optional[callable] = None,
        existing_translations: Optional[Dict[str, str]] = None,
        llm_provider: str = "gemini",
        llm_model: str = "gemini-1.5-flash",
        temperature: float = 0.1,
        final_fallback_max_retries: int = 2,
        enable_quality_review: bool = True,
        max_quality_retries: int = 1,
        use_multi_api_keys: bool = False,
        multi_llm_manager: Optional[MultiLLMManager] = None,
        track_tokens: bool = True,
    ) -> Dict[str, Any]:
        """번역 실행 및 토큰 사용량 추적"""
        if isinstance(json_input, dict):
            json_dict = json_input
        else:
            json_dict = json.loads(str(json_input).strip())

        # 토큰 카운터 초기화
        if track_tokens:
            self.reset_token_counter()

        logger.info(
            _m(
                "translator.settings",
                max_retries=max_retries,
                chunk_tokens=max_tokens_per_chunk,
            )
        )
        logger.info(
            _m(
                "translator.parallel_settings",
                concurrent=max_concurrent_requests,
                delay=delay_between_requests_ms,
            )
        )

        # 항상 다중 API 키 모드 사용
        # multi_llm_manager가 전달되지 않았다면 새로 생성
        multi_llm_manager = multi_llm_manager or MultiLLMManager()
        active_keys = multi_llm_manager.get_active_keys()
        if not active_keys:
            raise RuntimeError(
                "사용 가능한 API 키가 없습니다. 다중 API 키를 등록해주세요."
            )
        logger.info(f"다중 API 키 모드 활성화: {len(active_keys)}개 키 사용 가능")

        # LLM 클라이언트 획득 (로테이션 적용)
        llm_client = await multi_llm_manager.get_client()
        if not llm_client:
            raise RuntimeError("다중 API 키 클라이언트 생성에 실패했습니다.")

        # 토큰 카운터를 LLM 클라이언트에 추가
        if track_tokens:
            if hasattr(llm_client, "callbacks"):
                if llm_client.callbacks is None:
                    llm_client.callbacks = []
                llm_client.callbacks.append(self.token_counter)
            else:
                # 새로운 LLM 클라이언트 생성 시 콜백 추가
                logger.warning("LLM 클라이언트에 콜백을 추가할 수 없습니다.")

        initial_state: TranslatorState = TranslatorState(
            parsed_json=json_dict,
            placeholders={},
            id_to_text_map={},
            important_terms=[],
            processed_json={},
            translation_map={},
            translated_json={},
            final_json="",
            target_language=target_language,
            retry_count=0,
            max_retries=max_retries,
            max_tokens_per_chunk=max_tokens_per_chunk,
            max_concurrent_requests=max_concurrent_requests,
            delay_between_requests_ms=delay_between_requests_ms,
            error=None,
            glossary_path=self.glossary_path,
            use_glossary=use_glossary,
            progress_callback=progress_callback,
            existing_translations=existing_translations,
            primary_glossary=[],
            use_vanilla_glossary=use_vanilla_glossary,
            vanilla_glossary_path=vanilla_glossary_path or "vanilla_glossary.json",
            vanilla_glossary=[],
            llm_client=llm_client,
            final_fallback_max_retries=final_fallback_max_retries,
            enable_quality_review=enable_quality_review,
            quality_issues=[],
            quality_retry_count=0,
            max_quality_retries=max_quality_retries,
            # 다중 API 키 관련 추가
            use_multi_api_keys=use_multi_api_keys,
            multi_llm_manager=multi_llm_manager,
            token_counter=self.token_counter,
        )

        result = await self._workflow.ainvoke(initial_state, {"recursion_limit": 50})
        if result.get("error"):
            raise RuntimeError(result["error"])

        # 토큰 사용량 로그 출력
        if track_tokens:
            token_summary = self.get_formatted_token_summary()
            logger.info(f"번역 완료 - 토큰 사용량:\n{token_summary}")

        return json.loads(result["final_json"])


###############################################################################
# 5. Optional runnable example                                                #
###############################################################################


async def run_example() -> None:  # pragma: no cover – utility function
    """Run a quick interactive demo similar to the original script."""

    logging.basicConfig(level=logging.INFO)
    logger.info(_m("translator.init_translator"))
    translator = JSONTranslator()

    # Put your test JSON here or load from file.
    test_json = {"hello": "world"}

    try:
        logger.info(_m("translator.starting_translation"))
        translated = await translator.translate(test_json, "한국어")
        logger.info(_m("translator.result"))
        logger.info(translated)
    except Exception:  # pragma: no cover – human experimentation
        logger.error(_m("translator.error_occurred"))
        logger.error(traceback.format_exc())


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run_example())


def should_run_quality_review(state: TranslatorState) -> str:
    """품질 검토를 수행할지 결정한다.

    - 재번역 전(quality_retry_count == 0) 에만 품질 검토 실행
    - 재번역 후에는 바로 완료 단계로 이동하여 불필요한 두 번째 검토를 건너뛴다
    """
    if (
        state.get("enable_quality_review", True)
        and state.get("quality_retry_count", 0) == 0
    ):
        return "review"
    return "skip"
