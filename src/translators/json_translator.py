"""가져와서 사용할 수 있도록 translator.py에서 마이그레이션된 JSON 번역기 모듈입니다.

이 모듈은 LangGraph를 통해 Google Gemini를 사용하여 임의의 JSON 구조를
번역하기 위한 `JSONTranslator` 클래스와 지원 유틸리티를 제공합니다.
기존의 독립 실행형 스크립트는 이 모듈로 리팩터링되어 다음과 같이 가져올 수 있습니다.

    from translators import JSONTranslator

원본 파일 하단에 있던 대화형 예제 및 CLI 로직은 모듈을 독립적으로
유지하기 위해 제거되었습니다. 대신 프로그래밍 방식으로 실험하고 싶다면
편의를 위해 `run_example()` 코루틴이 제공됩니다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import regex as re
from langchain_core.language_models import BaseLLM
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from src.localization import get_message as _m
from src.prompts.llm_prompts import (
    contextual_terms_prompt,
    final_fallback_prompt,
    retry_contextual_terms_prompt,
    retry_translation_prompt,
    translation_prompt,
)
from src.translators.llm_manager import LLMManager

logger = logging.getLogger(__name__)

__all__ = [
    "TranslatorState",
    "TranslatedItem",
    "TermMeaning",
    "GlossaryEntry",
    "Glossary",
    "TranslationPair",
    "TranslationResult",
    "JSONTranslator",
    "run_example",
]

###############################################################################
# 1. State and data-model definitions                                        #
###############################################################################


class TranslatorState(TypedDict):
    """Runtime state carried between LangGraph nodes."""

    # Input & settings
    parsed_json: Dict[str, Any]
    target_language: str
    max_retries: int
    max_tokens_per_chunk: int
    max_concurrent_requests: int
    delay_between_requests_ms: int

    # Intermediate processing data
    placeholders: Dict[str, str]
    id_to_text_map: Dict[str, str]  # text_id -> original_text
    important_terms: List[GlossaryEntry]  # Glossary for consistent translation
    processed_json: Dict[str, Any]  # text with IDs substituted JSON
    translation_map: Dict[str, str]  # text_id -> translated_text

    # Final result
    translated_json: Dict[str, Any]  # id replaced back with translated text
    final_json: str

    # Workflow tracking
    retry_count: int
    error: Optional[str]
    glossary_path: Optional[str]
    use_glossary: bool
    progress_callback: Optional[callable]  # 진행률 콜백 추가

    # 기존 번역 데이터 (추가)
    existing_translations: Optional[Dict[str, str]]  # source_text -> target_text
    primary_glossary: List[GlossaryEntry]  # 기존 번역 데이터로 만든 1차 사전

    # 바닐라 glossary 관련 (추가)
    use_vanilla_glossary: bool  # 바닐라 사전 사용 여부
    vanilla_glossary_path: Optional[str]  # 바닐라 사전 파일 경로
    vanilla_glossary: List[GlossaryEntry]  # 바닐라 사전

    # LLM 클라이언트 (추가)
    llm_client: Optional[Any]  # LLM 클라이언트 인스턴스

    # 최종 재시도 횟수
    final_fallback_max_retries: int


class TranslatedItem(BaseModel):
    """Translation result item (ID based)."""

    id: str = Field(description="Unique ID of the text to translate")
    translated: str = Field(description="Translated text")


class TermMeaning(BaseModel):
    """A single meaning for a term, with context."""

    translation: str = Field(description="Translated term")
    context: str = Field(
        description="A very concise snippet of the surrounding text (under 10 words) to differentiate its meaning"
    )


class GlossaryEntry(BaseModel):
    """A glossary entry for a single original term, which may have multiple meanings."""

    original: str = Field(description="Original term")
    meanings: List[TermMeaning] = Field(
        description="A list of possible translations for the term, each with its own context"
    )


class SimpleGlossaryTerm(BaseModel):
    """A single glossary term with one meaning and its context."""

    original: str = Field(description="Original term")
    translation: str = Field(description="Translated term")
    context: str = Field(
        description="A very concise snippet of the surrounding text (under 10 words) to differentiate its meaning. This field is REQUIRED - if no specific context is available, provide a default value like '일반적인 사용' (general usage)"
    )


class Glossary(BaseModel):
    """The entire glossary, composed of multiple entries."""

    terms: List[GlossaryEntry]


class TranslationPair(BaseModel):
    """(original, translated) pair."""

    original: str = Field(description="Original text")
    translated: str = Field(description="Translated text")


class TranslationResult(BaseModel):
    """Structured output container returned from the LLM."""

    translations: List[TranslatedItem] = Field(description="List of translations")


###############################################################################
# 2. Utility helpers                                                          #
###############################################################################


class RequestDelayManager:
    """Small helper for yielding between API calls."""

    def __init__(self, delay_ms: int):
        self.delay_seconds = delay_ms / 1000.0

    async def wait(self) -> None:  # noqa: D401 – imperative mood is fine
        """Sleep for the configured delay."""
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)


class PlaceholderManager:
    """Extraction and restoration of special placeholder patterns."""

    # ------------------------------------------------------------------
    # Regex patterns for placeholders (expanded per user request)
    # ------------------------------------------------------------------
    FORMAT_CODE_PATTERN = r"[§&][0-9a-fk-or]"
    C_PLACEHOLDER_PATTERN = r"%(?:[0-9]+\$[sd]|[sd])"  # %1$s, %2$d, %s, %d 등
    ITEM_PLACEHOLDER_PATTERN = r"\$\([^)]*\)"
    JSON_PLACEHOLDER_PATTERN = r"\{(?:[^{}]|(?R))*\}"
    HTML_TAG_PATTERN = r"<[^>]*>"
    MINECRAFT_ITEM_CODE_PATTERN = (
        r"((\[[a-zA-Z_0-9]+[:.]([0-9a-zA-Z_]+([./][0-9a-zA-Z_]+)*)\])|"
        r"([a-zA-Z_0-9]+[:.]([0-9a-zA-Z_]+([./][0-9a-zA-Z_]+)*)))"
    )
    JS_TEMPLATE_LITERAL_PATTERN = r"\$\{[^}]+\}"
    SQUARE_BRACKET_TAG_PATTERN = r"\[[A-Za-z0-9_]+\]"
    LEGACY_MINECRAFT_PATTERN = (
        r"%[a-zA-Z_][a-zA-Z0-9_]*%"  # %username% 등, 더 정확한 매칭
    )
    NEWLINE_PATTERN = r"\\n|\\r\\n|\\r"  # \n, \r\n, \r 개행 문자들

    # Aggregate list for easy iteration (순서 중요: 더 구체적인 패턴을 먼저)
    _PLACEHOLDER_PATTERNS: List[str] = [
        NEWLINE_PATTERN,  # 개행 문자를 먼저 처리 (가장 구체적)
        C_PLACEHOLDER_PATTERN,  # %1$s, %2$d 등을 먼저 매칭
        FORMAT_CODE_PATTERN,
        ITEM_PLACEHOLDER_PATTERN,
        JSON_PLACEHOLDER_PATTERN,
        HTML_TAG_PATTERN,
        MINECRAFT_ITEM_CODE_PATTERN,
        JS_TEMPLATE_LITERAL_PATTERN,
        SQUARE_BRACKET_TAG_PATTERN,
        LEGACY_MINECRAFT_PATTERN,  # %username% 등은 나중에
        r"\{\{[^}]+\}\}",  # double-brace mustache style
    ]
    # 내부 치환 마커 검증을 위한 정규식
    _INTERNAL_PLACEHOLDER_PATTERN = r"\[P\d{3,}\]"
    _INTERNAL_NEWLINE_PATTERN = r"\[NEWLINE\]"
    _placeholder_counter = 0

    @staticmethod
    def reset_counter() -> None:
        """플레이스홀더 카운터를 리셋합니다."""
        PlaceholderManager._placeholder_counter = 0

    @staticmethod
    def extract_special_patterns_from_value(
        text: str, placeholders: Dict[str, str]
    ) -> str:
        """Find special patterns in *text* and replace them with placeholders."""

        if not isinstance(text, str):
            return text

        # 먼저 개행 문자를 특별히 처리
        text = PlaceholderManager._extract_newlines(text, placeholders)

        matches: List[str] = []
        for pattern in PlaceholderManager._PLACEHOLDER_PATTERNS:
            # 개행 패턴은 이미 처리했으므로 건너뛰기
            if pattern == PlaceholderManager.NEWLINE_PATTERN:
                continue

            found_matches = re.findall(pattern, text)
            # Handle case where findall returns tuples due to groups in regex
            for match in found_matches:
                if isinstance(match, tuple):
                    # Use the first non-empty group or the full match
                    match_str = next((group for group in match if group), match[0])
                else:
                    match_str = match
                matches.append(match_str)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_matches = [m for m in matches if not (m in seen or seen.add(m))]

        for match in unique_matches:
            PlaceholderManager._placeholder_counter += 1
            placeholder_id = f"[P{PlaceholderManager._placeholder_counter:03d}]"
            placeholders[placeholder_id] = match
            text = text.replace(match, placeholder_id, 1)

        return text

    @staticmethod
    def _extract_newlines(text: str, placeholders: Dict[str, str]) -> str:
        """개행 문자를 특별히 처리하여 [NEWLINE] placeholder로 대체합니다."""
        if not isinstance(text, str):
            return text

        newline_placeholder = "[NEWLINE]"
        # 여러 종류의 개행 문자를 하나의 플레이스홀더로 통일
        text = text.replace("\\r\\n", newline_placeholder)
        text = text.replace("\\n", newline_placeholder)
        text = text.replace("\\r", newline_placeholder)
        if newline_placeholder in text:
            placeholders[newline_placeholder] = "\\n"  # 복원 시 사용할 기본 개행 문자

        return text

    @staticmethod
    def process_json_object(obj: Any, placeholders: Dict[str, str]) -> Any:
        """Recursively traverse *obj* replacing string values with placeholders."""
        if isinstance(obj, dict):
            return {
                k: PlaceholderManager.process_json_object(v, placeholders)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [
                PlaceholderManager.process_json_object(i, placeholders) for i in obj
            ]
        if isinstance(obj, str):
            return PlaceholderManager.extract_special_patterns_from_value(
                obj, placeholders
            )
        return obj

    @staticmethod
    def restore_placeholders(text: str, placeholders: Dict[str, str]) -> str:  # noqa: D401
        """Replace placeholder IDs back with their original patterns."""
        # 먼저 개행 문자 placeholder들을 복원
        text = PlaceholderManager._restore_newlines(text, placeholders)

        # 그 다음 일반 placeholder들을 복원 (ID가 큰 것부터 처리하여 중첩 방지)
        sorted_placeholders = sorted(
            placeholders.items(),
            key=lambda item: (int(item[0][2:-1]) if item[0].startswith("[P") else -1),
            reverse=True,
        )

        for pid, original in sorted_placeholders:
            if pid == "[NEWLINE]":
                continue
            text = text.replace(pid, original)
        return text

    @staticmethod
    def _restore_newlines(text: str, placeholders: Dict[str, str]) -> str:
        """개행 문자 placeholder들을 원래 문자로 복원합니다."""
        if not isinstance(text, str):
            return text

        # [NEWLINE] 플레이스홀더를 저장된 개행 문자로 복원
        if "[NEWLINE]" in placeholders:
            text = text.replace("[NEWLINE]", placeholders["[NEWLINE]"])

        return text

    @classmethod
    def restore_placeholders_in_json(
        cls, json_obj: Any, placeholders: Dict[str, str]
    ) -> Any:
        """JSON 객체 레벨에서 안전하게 placeholder를 복원합니다."""
        if isinstance(json_obj, dict):
            return {
                k: cls.restore_placeholders_in_json(v, placeholders)
                for k, v in json_obj.items()
            }
        elif isinstance(json_obj, (list, tuple)):
            return [cls.restore_placeholders_in_json(i, placeholders) for i in json_obj]
        elif isinstance(json_obj, str):
            return cls.restore_placeholders(json_obj, placeholders)
        else:
            return json_obj

    @staticmethod
    def extract_placeholders_from_text(text: str) -> List[str]:
        """텍스트에서 플레이스홀더 패턴들을 추출합니다."""
        if not isinstance(text, str):
            return []

        placeholders = []

        for pattern in PlaceholderManager._PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    # 정규식 그룹이 있는 경우, 비어있지 않은 첫 번째 그룹 선택
                    match_str = next((group for group in match if group), match[0])
                else:
                    match_str = match

                if match_str and match_str not in placeholders:
                    placeholders.append(match_str)

        return placeholders

    @staticmethod
    def validate_placeholder_preservation(original: str, translated: str) -> bool:
        """원문의 플레이스홀더들이 번역문에서도 보존되었는지 검증합니다."""
        if not isinstance(original, str) or not isinstance(translated, str):
            return True

        # 내부 플레이스홀더 마커를 직접 비교
        original_placeholders = sorted(
            PlaceholderManager._extract_internal_placeholders(original)
        )
        translated_placeholders = sorted(
            PlaceholderManager._extract_internal_placeholders(translated)
        )

        return original_placeholders == translated_placeholders

    @staticmethod
    def get_missing_placeholders(original: str, translated: str) -> List[str]:
        """원문에는 있지만 번역문에서 빠진 플레이스홀더들을 반환합니다."""
        if not isinstance(original, str) or not isinstance(translated, str):
            return []

        original_placeholders = set(
            PlaceholderManager._extract_internal_placeholders(original)
        )
        translated_placeholders = set(
            PlaceholderManager._extract_internal_placeholders(translated)
        )

        missing = list(original_placeholders - translated_placeholders)
        return missing

    @staticmethod
    def _extract_internal_placeholders(text: str) -> List[str]:
        """텍스트에서 내부 플레이스홀더 마커([PXXX] 또는 [NEWLINE])를 추출합니다."""
        if not isinstance(text, str):
            return []

        placeholders = re.findall(
            PlaceholderManager._INTERNAL_PLACEHOLDER_PATTERN, text
        )
        newlines = re.findall(PlaceholderManager._INTERNAL_NEWLINE_PATTERN, text)
        return placeholders + newlines


class TokenOptimizer:
    """Helpers for ID substitution and token-count heuristics."""

    _id_counter = 0  # 클래스 변수로 ID 카운터 관리

    @staticmethod
    def reset_id_counter() -> None:
        """ID 카운터를 리셋합니다. 새로운 번역 작업 시작 시 호출하세요."""
        TokenOptimizer._id_counter = 0

    @staticmethod
    def format_chunk_for_llm(chunk: List[Dict[str, str]]) -> str:
        """JSON 청크를 LLM이 읽기 쉬운 형태로 포맷합니다."""
        if not chunk:
            return "No items."

        lines = [f"TEXTS ({len(chunk)}):"]

        for i, item in enumerate(chunk, 1):
            text_id = item.get("id", f"item_{i}")
            original_text = item.get("original", "")
            lines.append(f"{i}. [{text_id}]\n```\n{original_text}\n```")

        return "\n\n".join(lines)

    @staticmethod
    def format_glossary_for_llm(glossary_entries: List[GlossaryEntry]) -> str:
        """글로시리를 LLM이 읽기 쉬운 형태로 포맷합니다."""
        if not glossary_entries:
            return "No glossary."

        lines = [f"GLOSSARY ({len(glossary_entries)}):"]

        for i, entry in enumerate(glossary_entries, 1):
            original = entry.original
            meanings = []

            for meaning in entry.meanings:
                translation = meaning.translation
                context = meaning.context
                if context and context != "기존 번역":
                    meanings.append(f"{translation} (Context: {context})")
                else:
                    meanings.append(translation)

            meanings_str = " / ".join(meanings)
            lines.append(f"{i}. {original} -> {meanings_str}")

        return "\n".join(lines)

    @staticmethod
    def deduplicate_glossary_meanings(meanings: List[TermMeaning]) -> List[TermMeaning]:
        """글로시리 의미들에서 중복을 제거합니다. 같은 번역이면 context가 달라도 중복으로 간주합니다."""
        if not meanings:
            return meanings

        original_count = len(meanings)
        seen_translations = set()
        deduplicated = []

        for meaning in meanings:
            translation_key = meaning.translation.lower().strip()

            if translation_key not in seen_translations:
                seen_translations.add(translation_key)
                deduplicated.append(meaning)

        # 중복 제거 결과 로깅 (디버깅용)
        removed_count = original_count - len(deduplicated)
        if removed_count > 0:
            logger.debug(
                f"글로시리 의미 중복 제거: {original_count}개 → {len(deduplicated)}개 ({removed_count}개 제거)"
            )

        return deduplicated

    @staticmethod
    def merge_glossary_entry_meanings(
        existing_meanings: List[TermMeaning], new_meanings: List[TermMeaning]
    ) -> List[TermMeaning]:
        """기존 의미들과 새로운 의미들을 병합하면서 중복을 제거합니다."""
        # 기존 번역들을 소문자로 변환해서 집합에 저장
        existing_translations = {
            meaning.translation.lower().strip() for meaning in existing_meanings
        }

        # 새로운 의미들 중 중복되지 않는 것만 추가
        merged_meanings = existing_meanings.copy()

        for new_meaning in new_meanings:
            translation_key = new_meaning.translation.lower().strip()
            if translation_key not in existing_translations:
                merged_meanings.append(new_meaning)
                existing_translations.add(translation_key)

        # 최종적으로 중복 제거 (혹시 모를 중복을 위해)
        return TokenOptimizer.deduplicate_glossary_meanings(merged_meanings)

    @staticmethod
    def replace_text_with_ids(json_obj: Any, id_map: Dict[str, str]) -> Any:
        if isinstance(json_obj, dict):
            return {
                k: TokenOptimizer.replace_text_with_ids(v, id_map)
                for k, v in json_obj.items()
            }
        if isinstance(json_obj, list):
            return [TokenOptimizer.replace_text_with_ids(i, id_map) for i in json_obj]
        if isinstance(json_obj, str) and json_obj.strip():
            # 간단한 ID 생성 (T001, T002, ...) - 총 4자
            TokenOptimizer._id_counter += 1
            text_id = f"T{TokenOptimizer._id_counter:03d}"
            id_map[text_id] = json_obj
            return text_id
        return json_obj

    @staticmethod
    def optimize_json_for_translation(data: Dict[str, Any]) -> List[str]:
        texts: List[str] = []

        def collect(obj: Any) -> None:
            if isinstance(obj, dict):
                for v in obj.values():
                    collect(v)
            elif isinstance(obj, list):
                for i in obj:
                    collect(i)
            elif isinstance(obj, str) and obj.strip():
                # 새로운 패턴: T001, T002 등의 간단한 ID와 [P...], [NEWLINE] 제외
                if not re.match(r"^T\d{3,}$", obj) and not re.match(
                    r"^\[(P\d{3,}|NEWLINE)\]$", obj
                ):
                    texts.append(obj)

        collect(data)
        return list(set(texts))

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4 + 1

    @staticmethod
    def create_text_chunks(
        items: List[Dict[str, str]], max_tokens_per_chunk: int = 3000
    ) -> List[List[Dict[str, str]]]:
        chunks: List[List[Dict[str, str]]] = []
        current_chunk: List[Dict[str, str]] = []
        current_tokens = 0
        prompt_overhead = 500
        effective_max = max_tokens_per_chunk - prompt_overhead

        for item in items:
            text_tokens = TokenOptimizer.estimate_tokens(item["original"])
            if text_tokens > effective_max:
                if current_chunk:
                    chunks.append(current_chunk)
                chunks.append([item])
                current_chunk = []
                current_tokens = 0
            elif current_tokens + text_tokens > effective_max:
                chunks.append(current_chunk)
                current_chunk = [item]
                current_tokens = text_tokens
            else:
                current_chunk.append(item)
                current_tokens += text_tokens

        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    @staticmethod
    def handle_oversized_text(text: str, max_tokens: int) -> str:  # noqa: D401
        tokens = TokenOptimizer.estimate_tokens(text)
        if tokens > max_tokens:
            logger.warning(
                "⚠️  Single text contains %s tokens, exceeding limit (%s).",
                tokens,
                max_tokens,
            )
            logger.warning("   Preview: %s...", text[:100])
            logger.warning(
                "   The text will be sent as-is. Ensure the LLM can handle it."
            )
        return text


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

        id_to_text: Dict[str, str] = {}
        json_with_ids = TokenOptimizer.replace_text_with_ids(
            json_with_placeholders, id_to_text
        )

        state["id_to_text_map"] = id_to_text
        state["processed_json"] = json_with_ids

        logger.info(_m("translator.found_items", count=len(id_to_text)))
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

                llm = llm_client
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
            # TranslatedItem을 도구로 바인딩하여 LLM 호출
            llm_with_tools = llm.bind_tools([TranslatedItem])
            response = await llm_with_tools.ainvoke(prompt)

            # LLM의 도구 호출에서 TranslatedItem 추출
            translations = []
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call["name"] == "TranslatedItem":
                        try:
                            item = TranslatedItem(**tool_call["args"])
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
            return []


def restore_placeholders_node(state: TranslatorState) -> TranslatorState:  # noqa: D401
    try:
        logger.info("플레이스홀더 복원 시작...")
        # JSON 객체 레벨에서 안전하게 placeholder 복원
        restored_json = PlaceholderManager.restore_placeholders_in_json(
            state["translated_json"], state["placeholders"]
        )

        # 복원된 JSON 객체를 문자열로 변환
        state["final_json"] = json.dumps(restored_json, ensure_ascii=False, indent=2)
        logger.info("플레이스홀더 복원 완료.")
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
            # 2. 원본이 의미있는 텍스트인데 번역이 비어있거나 플레이스홀더인 경우
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
            )

            try:
                # 재시도 시 temperature를 약간 높여 다른 결과 유도
                temperature = min(1.0, attempt * 0.2)
                configured_llm = llm.with_config(
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
                            else:
                                last_error = "플레이스홀더 누락"
                                logger.warning(
                                    f"⚠️ 최종 번역 재시도({attempt + 1}) 후에도 플레이스홀더 누락: {tid} -> '{item.translated}'"
                                )
                else:
                    last_error = "응답 없음"
                    logger.warning(
                        f"⚠️ 최종 번역 재시도({attempt + 1}) 실패 (응답 없음): {tid}"
                    )

            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"🚨 최종 번역 재시도({attempt + 1}) API 호출 오류 (항목: {tid}): {e}"
                )

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
        logger.info("결과 JSON 재구성 완료.")
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
        # 2. 원본이 의미있는 텍스트인데 제대로 번역되지 않은 경우
        elif original:
            if len(translated) == 0:
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

    # 기존 번역 데이터를 GlossaryEntry로 변환
    for source_text, target_text in existing_translations.items():
        try:
            # 간단한 용어 추출 (단어 단위)
            words = source_text.split()
            if len(words) <= 3:  # 3단어 이하의 짧은 표현만 용어로 간주
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
                            TermMeaning(translation=target_text, context="기존 번역")
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
    return state


###############################################################################
# 4. Main translator class                                                    #
###############################################################################


class JSONTranslator:
    """High-level façade wrapping the LangGraph workflow."""

    def __init__(self, *, glossary_path: Optional[str] = None) -> None:
        self._workflow = self._create_workflow()
        self.glossary_path = glossary_path
        self.llm_manager = LLMManager()

    def _create_workflow(self) -> StateGraph:  # noqa: D401
        wf = StateGraph(TranslatorState)
        wf.add_node("parse_and_extract", parse_and_extract_node)
        wf.add_node("create_primary_glossary", create_primary_glossary_node)
        wf.add_node("load_vanilla_glossary", load_vanilla_glossary_node)
        wf.add_node("smart_translate", smart_translate_node)
        wf.add_node("validation_and_retry", validation_and_retry_node)
        wf.add_node("rebuild_json", rebuild_json_node)
        wf.add_node("restore_placeholders", restore_placeholders_node)
        wf.add_node(
            "extract_terms_from_json_chunks", extract_terms_from_json_chunks_node
        )
        wf.add_node("load_glossary", load_glossary_node)
        wf.add_node("save_glossary", save_glossary_node)
        wf.add_node("final_fallback_translation", final_fallback_translation_node)
        wf.add_node("final_check", lambda s: s)  # Passthrough node

        wf.set_entry_point("parse_and_extract")

        # Branch for glossary creation
        wf.add_conditional_edges(
            "parse_and_extract",
            should_create_glossary,
            {
                "create_glossary": "create_primary_glossary",
                "skip_glossary": "load_vanilla_glossary",  # 바닐라 사전 로드로 변경
            },
        )

        # 1차 사전 구축 후 바닐라 사전 로드
        wf.add_edge("create_primary_glossary", "load_vanilla_glossary")

        # 바닐라 사전 로드 후 기존 사전 로드
        wf.add_edge("load_vanilla_glossary", "load_glossary")

        # Glossary path
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
        wf.add_edge("restore_placeholders", "final_check")

        # Final check to decide on saving
        wf.add_conditional_edges(
            "final_check",
            should_save_glossary,
            {"save_glossary": "save_glossary", "end": END},
        )
        wf.add_edge("save_glossary", END)
        return wf.compile()

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
    ) -> str:
        if isinstance(json_input, dict):
            json_dict = json_input
        else:
            json_dict = json.loads(str(json_input).strip())

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

        # LLM 클라이언트 생성
        llm_client = await self.llm_manager.create_llm_client(
            llm_provider, llm_model, temperature=temperature, max_tokens=100000
        )

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
        )

        result = await self._workflow.ainvoke(initial_state)
        if result.get("error"):
            raise RuntimeError(result["error"])
        return result["final_json"]


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
