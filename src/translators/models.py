from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

__all__ = [
    "TranslatorState",
    "TranslatedItem",
    "TermMeaning",
    "GlossaryEntry",
    "SimpleGlossaryTerm",
    "Glossary",
    "TranslationPair",
    "TranslationResult",
    "QualityIssue",
    "QualityReview",
]


class TranslatorState(TypedDict):
    """Runtime state carried between LangGraph nodes."""

    parsed_json: Dict[str, Any]
    target_language: str
    max_retries: int
    max_tokens_per_chunk: int
    max_concurrent_requests: int
    delay_between_requests_ms: int

    placeholders: Dict[str, str]
    id_to_text_map: Dict[str, str]  # text_id -> original_text
    important_terms: List["GlossaryEntry"]  # Glossary for consistent translation
    processed_json: Dict[str, Any]  # text with IDs substituted JSON
    translation_map: Dict[str, str]  # text_id -> translated_text

    translated_json: Dict[str, Any]  # id replaced back with translated text
    final_json: str

    retry_count: int
    error: Optional[str]
    glossary_path: Optional[str]
    use_glossary: bool
    progress_callback: Optional[callable]  # 진행률 콜백 추가

    existing_translations: Optional[Dict[str, str]]  # source_text -> target_text
    primary_glossary: List["GlossaryEntry"]  # 기존 번역 데이터로 만든 1차 사전

    use_vanilla_glossary: bool  # 바닐라 사전 사용 여부
    vanilla_glossary_path: Optional[str]  # 바닐라 사전 파일 경로
    vanilla_glossary: List["GlossaryEntry"]  # 바닐라 사전

    llm_client: Optional[Any]  # LLM 클라이언트 인스턴스

    glossary_text: str  # 선택된 사전 파일 경로

    final_fallback_max_retries: int

    enable_quality_review: bool  # 품질 검토 사용 여부
    quality_issues: List[Any]  # 품질 검토 결과
    quality_retry_count: int  # 품질 기반 재번역 횟수
    max_quality_retries: int  # 품질 기반 재번역 최대 횟수

    # 다중 API 키 지원 관련 필드
    use_multi_api_keys: bool  # 다중 API 키 사용 여부
    multi_llm_manager: Optional[Any]  # MultiLLMManager 인스턴스


class TranslatedItem(BaseModel):
    """Translation result item (ID based)."""

    id: str = Field(description="Unique ID of the text to translate")
    translated: str = Field(description="Translated text (Do not return ID)")


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


class QualityIssue(BaseModel):
    """번역 품질 문제를 나타내는 모델"""

    text_id: str = Field(description="문제가 있는 텍스트의 ID")
    issue_type: str = Field(
        description="문제 유형 (예: 오역, 누락, 부자연스러움, 플레이스홀더 문제)"
    )
    severity: str = Field(description="심각도 (low, medium, high)")
    description: str = Field(description="문제에 대한 설명")
    suggested_fix: Optional[str] = Field(description="수정 제안 (선택사항)")


class QualityReview(BaseModel):
    """번역 품질 검토 결과"""

    issues: List[QualityIssue] = Field(description="발견된 품질 문제들")
    overall_quality: str = Field(
        description="전체적인 품질 평가 (excellent, good, fair, poor)"
    )
    summary: str = Field(description="검토 요약")
