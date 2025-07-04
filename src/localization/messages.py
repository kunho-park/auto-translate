"""
애플리케이션 전체의 지역화를 위한 메시지 카탈로그입니다.

모든 사용자 대상 문자열(로그, GUI 레이블 등)은
런타임에 번역하거나 대체할 수 있도록 안정적인 키로 여기에 정의됩니다.
형식화된 텍스트를 검색하려면 `get_message(key, **kwargs)`를 사용하세요.
"""

from __future__ import annotations

from typing import Any, Dict

# ---------------------------------------------------------------------------
# 1. 언어별 메시지 카탈로그
# ---------------------------------------------------------------------------

_CATALOGS: Dict[str, Dict[str, str]] = {
    "en": {
        # Token optimizer warnings
        "translator.oversized_warning": "⚠️  Single text contains {tokens} tokens, exceeding limit ({limit}).",
        "translator.oversized_preview": "   Preview: {preview}…",
        "translator.oversized_as_is": "   The text will be sent as-is. Ensure the LLM can handle it.",
        # Chunk translation lifecycle
        "translator.chunk_start": "🔄 (worker {current}/{total}) Chunk parallel {kind} started…",
        "translator.chunk_finish": "✅ (worker {current}/{total}) Chunk parallel {kind} finished.",
        "translator.chunk_fail": "❌ (worker {current}/{total}) Chunk {kind} failed: {error}",
        "translator.llm_empty_result": "⚠️ (worker {current}/{total}) LLM returned empty result, possibly due to a content filter or parsing failure.",
        # Extraction / preparation
        "translator.found_items": "🔍 Found {count} translatable text items.",
        "translator.chunks_split": "📦 Split into {chunks} chunks. Starting parallel translation (max concurrent: {concurrent}).",
        # Validation & retry
        "translator.missing_retry": "⚠️ {missing} missing translations detected. Retrying {attempt}/{max_attempts}…",
        "translator.error_abort": "❗️ Error occurred: {error}. Aborting workflow.",
        "translator.untranslated_retry": "🔍 Untranslated items detected. Retrying (attempt {attempt}/{max_attempts})",
        "translator.max_retry_reached": "🔔 Reached maximum retry ({max_attempts}) with untranslated items remaining.",
        "translator.translation_ok": "✅ Translation verification completed. No missing items.",
        # Translator settings
        "translator.settings": "⚙️  Translation settings: max retries {max_retries}, max tokens per chunk {chunk_tokens}",
        "translator.parallel_settings": "⚙️  Parallel processing: max concurrent requests {concurrent}, delay between requests {delay} ms",
        # Example/demo
        "translator.init_translator": "🔧 Initializing JSONTranslator…",
        "translator.starting_translation": "🚀 Starting parallel translation…",
        "translator.result": "📋 Result:",
        "translator.error_occurred": "❌ An error occurred:",
        # Glossary / Important Terms
        "translator.terms_found": "🔍 Found {count} potential important terms. Translating top terms: {terms}",
        "translator.terms_prompt": "You are a terminology expert. Translate the following list of terms into {language}. Provide the translation in a structured format with 'original', 'translation', and a brief 'context' for each term. Terms to translate: \n{terms}",
        "translator.terms_translated": "✅ Successfully created a glossary with {count} terms.",
        "translator.terms_empty_result": "⚠️ Glossary creation returned no terms. Proceeding without a glossary.",
        "translator.terms_raw_result": "Raw result from LLM for glossary creation: {result!r}",
        "translator.terms_error": "⚠️ Could not create a glossary due to an error: {error}. Proceeding without it.",
        "translator.translation_prompt": """You are an expert translator. Translate the 'original' text in the following JSON object list into {language}.

IMPORTANT: You MUST adhere to the provided glossary for consistent translation.
Glossary:
{glossary}

Return the result as a JSON object list with 'id' and 'translated' fields. Do not change the 'id'.

List to {kind}:
{chunk}""",
        "translator.retry_translation_prompt": """You are an expert translator. This is a RETRY attempt for items that failed previous translation.

CRITICAL REQUIREMENTS:
1. You MUST translate ALL items completely - NO EMPTY TRANSLATIONS
2. You MUST adhere to the provided glossary for consistent translation
3. You MUST return different translations than original text
4. You MUST provide meaningful translations, not just copying the original

Glossary for consistency:
{glossary}

Return the result as a JSON object list with 'id' and 'translated' fields. Do not change the 'id'.
EVERY item MUST have a proper translation in the 'translated' field.

Failed items to retry {kind}:
{chunk}""",
        "translator.glossary_loaded": "✅ Loaded {count} terms from existing glossary: {path}",
        "translator.glossary_load_error": "⚠️ Could not load glossary from {path}: {error}",
        "translator.glossary_saved": "✅ Saved {count} terms to glossary: {path}",
        "translator.glossary_save_error": "❌ Could not save glossary to {path}: {error}",
        "translator.contextual_terms_start": "🔍 Analyzing JSON context to extract terms from {count} chunks...",
        "translator.contextual_terms_finish": "✅ Extracted {count} new contextual terms.",
        "translator.contextual_terms_no_new": "✅ No new contextual terms found.",
        "translator.contextual_terms_error": "⚠️ Could not extract terms from a chunk: {error}",
        "translator.contextual_terms_main_error": "❌ A critical error occurred during contextual term extraction: {error}",
        "translator.contextual_terms_prompt": """You are a terminology expert. Your task is to analyze the following block of text and identify important terms that require consistent translation.

For each term you identify, provide its original form and its translation into {language}. For the 'context', provide a very concise snippet of the surrounding text (under 10 words) to differentiate its meaning.

Respond in a structured format.

Text to analyze:
{chunk}""",
        # 1차 사전 구축 관련 메시지
        "translator.primary_glossary_start": "Creating primary glossary from existing translations...",
        "translator.primary_glossary_finish": "Primary glossary created with {count} terms",
        "translator.primary_glossary_skip": "No existing translations found, skipping primary glossary creation",
        "translator.existing_translations_found": "Found {count} existing translation pairs",
        "translator.existing_translations_analyzing": "Analyzing existing translations from {files} file pairs",
        # 새로운 GUI 메시지들
        "gui.app_title": "Modpack Browser - Auto Translate",
        "gui.title_main": "Modpack Browser",
        "gui.search_hint": "Search modpacks...",
        "gui.button.back": "Back",
        "gui.button.theme_toggle": "Toggle Theme",
        "gui.section.modpack_info": "Modpack Information",
        "gui.label.author": "Author",
        "gui.label.modpack_version": "Modpack Version",
        "gui.label.minecraft_version": "Minecraft Version",
        "gui.label.path": "Path",
        "gui.button.start_translation": "Start Translation",
        "gui.dialog.translation_settings": "Translation Settings",
        "gui.dialog.translation_options": "Translation Options:",
        "gui.option.lang_files": "Translate Lang files",
        "gui.option.snbt_files": "Translate SNBT files",
        "gui.option.js_files": "Translate JS files",
        "gui.option.txt_files": "Translate TXT files",
        "gui.button.cancel": "Cancel",
        "gui.button.start": "Start Translation",
        "gui.status.error": "Error",
        "gui.status.translation_started": "Starting translation for {name}...",
        "gui.button.language": "Language",
        "gui.dialog.select_language": "Select Language",
        "gui.language.english": "English",
        "gui.language.korean": "한국어",
    },
    # 한국어 카탈로그
    "ko": {
        # 토큰 최적화기 경고
        "translator.oversized_warning": "⚠️  단일 텍스트가 {tokens} 토큰으로 제한({limit})을 초과했습니다.",
        "translator.oversized_preview": "   미리보기: {preview}…",
        "translator.oversized_as_is": "   텍스트를 그대로 전송합니다. LLM이 처리할 수 있는지 확인하세요.",
        # Chunk translation lifecycle
        "translator.chunk_start": "🔄 (작업자 {current}/{total}) {kind} 청크 병렬 처리 시작…",
        "translator.chunk_finish": "✅ (작업자 {current}/{total}) {kind} 청크 병렬 처리 완료.",
        "translator.chunk_fail": "❌ (작업자 {current}/{total}) {kind} 청크 실패: {error}",
        "translator.llm_empty_result": "⚠️ (작업자 {current}/{total}) LLM이 빈 결과를 반환했습니다, 내용 필터 또는 파싱 실패의 결과일 수 있습니다.",
        # Extraction / preparation
        "translator.found_items": "🔍 {count}개의 번역 가능한 텍스트 항목을 찾았습니다.",
        "translator.chunks_split": "📦 {chunks}개의 청크로 분할했습니다. 병렬 번역 시작 (최대 동시 처리: {concurrent}).",
        # Validation & retry
        "translator.missing_retry": "⚠️ {missing}개의 누락된 번역이 감지되었습니다. 재시도 중 {attempt}/{max_attempts}…",
        "translator.error_abort": "❗️ 오류 발생: {error}. 워크플로우를 중단합니다.",
        "translator.untranslated_retry": "🔍 번역되지 않은 항목이 감지되었습니다. 재시도 중 (시도 {attempt}/{max_attempts})",
        "translator.max_retry_reached": "🔔 최대 재시도 횟수({max_attempts})에 도달했으나 번역되지 않은 항목이 남아있습니다.",
        "translator.translation_ok": "✅ 번역 검증 완료. 누락된 항목이 없습니다.",
        # Translator settings
        "translator.settings": "⚙️  번역 설정: 최대 재시도 {max_retries}, 청크당 최대 토큰 {chunk_tokens}",
        "translator.parallel_settings": "⚙️  병렬 처리: 최대 동시 요청 {concurrent}, 요청 간 지연 {delay} ms",
        # Example/demo
        "translator.init_translator": "🔧 JSONTranslator 초기화 중…",
        "translator.starting_translation": "🚀 병렬 번역 시작…",
        "translator.result": "📋 결과:",
        "translator.error_occurred": "❌ 오류가 발생했습니다:",
        # Glossary / Important Terms
        "translator.terms_found": "🔍 {count}개의 중요 단어 후보를 찾았습니다. 상위 단어 번역 중: {terms}",
        "translator.terms_prompt": "You are a terminology expert. Translate the following list of terms into {language}. Provide the translation in a structured format with 'original', 'translation', and a brief 'context' for each term. Terms to translate: \n{terms}",
        "translator.terms_translated": "✅ {count}개의 단어로 용어집을 생성했습니다.",
        "translator.terms_empty_result": "⚠️ 용어집 생성 결과가 비어있습니다. 용어집 없이 진행합니다.",
        "translator.terms_raw_result": "용어집 생성을 위한 LLM의 원본 결과: {result!r}",
        "translator.terms_error": "⚠️ 오류로 인해 용어집을 생성할 수 없습니다: {error}. 용어집 없이 진행합니다.",
        "translator.translation_prompt": """당신은 전문 번역가입니다. 다음 JSON 객체 리스트의 'original' 텍스트를 {language}로 번역하세요.

중요: 일관된 번역을 위해 반드시 아래 용어집을 준수해야 합니다.
용어집:
{glossary}

결과는 'id'와 'translated' 필드를 가진 JSON 객체 리스트로 반환하세요. 'id'는 절대 변경하면 안 됩니다.

{kind}할 리스트:
{chunk}""",
        "translator.retry_translation_prompt": """당신은 전문 번역가입니다. 이것은 이전 번역에 실패한 항목들에 대한 재시도입니다.

중요한 요구사항:
1. 모든 항목을 완전히 번역해야 합니다 - 빈 번역은 절대 불가
2. 일관된 번역을 위해 반드시 아래 용어집을 준수해야 합니다
3. 원본 텍스트와 다른 번역을 제공해야 합니다
4. 단순히 원본을 복사하지 말고 의미 있는 번역을 제공해야 합니다

일관성을 위한 용어집:
{glossary}

결과는 'id'와 'translated' 필드를 가진 JSON 객체 리스트로 반환하세요. 'id'는 절대 변경하면 안 됩니다.
모든 항목은 'translated' 필드에 적절한 번역이 있어야 합니다.

재시도할 실패 항목들:
{chunk}""",
        "translator.glossary_loaded": "✅ 기존 용어집에서 {count}개의 용어를 불러왔습니다: {path}",
        "translator.glossary_load_error": "⚠️ 용어집을 불러오지 못했습니다 ({path}): {error}",
        "translator.glossary_saved": "✅ {count}개의 용어를 용어집에 저장했습니다: {path}",
        "translator.glossary_save_error": "❌ 용어집을 저장하지 못했습니다 ({path}): {error}",
        "translator.contextual_terms_start": "🔍 {count}개 JSON 청크의 문맥을 분석하여 용어 추출을 시작합니다...",
        "translator.contextual_terms_finish": "✅ {count}개의 새로운 문맥 기반 용어를 추출했습니다.",
        "translator.contextual_terms_no_new": "✅ 새로운 문맥 기반 용어를 찾지 못했습니다.",
        "translator.contextual_terms_error": "⚠️ 일부 청크에서 용어를 추출하지 못했습니다: {error}",
        "translator.contextual_terms_main_error": "❌ 문맥 기반 용어 추출 중 심각한 오류 발생: {error}",
        "translator.contextual_terms_prompt": """당신은 용어 전문가입니다. 당신의 임무는 다음 텍스트 블록을 분석하여 일관된 번역이 필요한 중요 용어를 식별하는 것입니다.

식별한 각 용어에 대해 원본 형식과 {language}로의 번역을 제공하세요. 'context' 필드에는 의미를 구분할 수 있도록 주변 텍스트의 매우 간결한 일부(10단어 미만)를 제공하세요.

구조화된 형식으로 응답하세요.

분석할 텍스트:
{chunk}""",
        # 1차 사전 구축 관련 메시지
        "translator.primary_glossary_start": "기존 번역 데이터로 1차 사전을 구축하고 있습니다...",
        "translator.primary_glossary_finish": "{count}개 용어가 포함된 1차 사전이 구축되었습니다",
        "translator.primary_glossary_skip": "기존 번역 데이터가 없어 1차 사전 구축을 건너뜁니다",
        "translator.existing_translations_found": "{count}개의 기존 번역 쌍을 발견했습니다",
        "translator.existing_translations_analyzing": "{files}개 파일 쌍에서 기존 번역을 분석하고 있습니다",
        # 새로운 GUI 메시지들
        "gui.app_title": "모드팩 브라우저 - Auto Translate",
        "gui.title_main": "모드팩 브라우저",
        "gui.search_hint": "모드팩 검색...",
        "gui.button.back": "뒤로가기",
        "gui.button.theme_toggle": "테마 변경",
        "gui.section.modpack_info": "모드팩 정보",
        "gui.label.author": "제작자",
        "gui.label.modpack_version": "모드팩 버전",
        "gui.label.minecraft_version": "마인크래프트 버전",
        "gui.label.path": "경로",
        "gui.button.start_translation": "번역 시작",
        "gui.dialog.translation_settings": "번역 설정",
        "gui.dialog.translation_options": "번역 옵션:",
        "gui.option.lang_files": "언어 파일 번역",
        "gui.option.snbt_files": "SNBT 파일 번역",
        "gui.option.js_files": "JS 파일 번역",
        "gui.option.txt_files": "TXT 파일 번역",
        "gui.button.cancel": "취소",
        "gui.button.start": "번역 시작",
        "gui.status.error": "오류",
        "gui.status.translation_started": "{name} 번역 시작 중...",
        "gui.button.language": "언어",
        "gui.dialog.select_language": "언어 선택",
        "gui.language.english": "영어",
        "gui.language.korean": "한국어",
    },
}

# 현재 선택된 언어 (기본값: 영어).
_LANG: str = "en"


# ---------------------------------------------------------------------------
# 2. API 헬퍼
# ---------------------------------------------------------------------------


def set_language(lang: str) -> None:  # noqa: D401
    """지역화를 위한 전역 언어를 설정합니다 (예: "en", "ko")."""
    global _LANG
    if lang in _CATALOGS:
        _LANG = lang
    else:
        _LANG = "en"


def get_message(key: str, *args: Any, **kwargs: Any) -> str:  # noqa: D401
    """지정된 키에 대한 지역화된 메시지를 반환합니다."""
    # args는 이전 버전과의 호환성을 위해 유지됩니다.
    # 하지만 kwargs를 사용하는 것이 좋습니다.
    catalog = _CATALOGS.get(_LANG, _CATALOGS["en"])
    template = catalog.get(key, f"<{key}>")
    try:
        return template.format(*args, **kwargs)
    except (KeyError, IndexError):
        # 포맷팅 실패 시 템플릿을 그대로 반환
        return template
