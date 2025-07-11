"""
LLM 프롬프트 템플릿 (XML 구조)
이 함수들은 번역 워크플로우를 위한 완전한 형식의 프롬프트를 반환합니다.
"""

# XML 구조의 프롬프트 템플릿
TRANSLATION_PROMPT_TEMPLATE = """<instructions>
당신은 전문 번역가입니다. 주어진 텍스트를 {language}로 번역해주세요.
번역이 완료된 각 항목에 대해 'TranslatedItem' 도구를 호출하여 결과를 기록해주세요.
</instructions>

<glossary>
{glossary}
</glossary>

<input>
번역할 항목들:
{chunk}
</input>

<rules>
<required>
- id는 절대 변경하지 마세요
- 모든 항목을 반드시 {language}로 완전히 번역해야 합니다
- 고유명사나 브랜드명이라도 가능한 한 {language}로 번역하거나 적절한 현지화를 해주세요
- 번역이 어려운 전문용어는 용어집을 참고하거나 의미를 살려서 번역해주세요
- 번역할 때 괄호 안에 영어 원문이나 설명을 추가하지 마세요 (예: "마법사 (Wizard)" 대신 "마법사"로만 번역)
- 주어진 모든 항목에 대해 반드시 'TranslatedItem' 도구를 호출해야 합니다 - 누락 절대 금지
</required>

<glossary_usage>
- 용어집에서 "(Context: ...)" 부분은 참고용 정보일 뿐이며, 실제 번역에는 포함하지 마세요
- 예: "마법사 (Context: 게임 직업)" → 번역 시 "마법사"만 사용하고 "(Context: 게임 직업)" 부분은 무시하세요
- Context는 용어의 의미를 이해하는 데만 활용하고, 번역 결과에는 절대 포함하지 마세요
</glossary_usage>

<critical_placeholders>
- [PXXX] 또는 [NEWLINE] 형식의 플레이스홀더는 절대로 삭제하거나 변경하지 마세요.
- 이러한 플레이스홀더들은 번역 후 원본 내용으로 복원되는 중요한 마커입니다.
- 플레이스홀더는 번역문에서 정확히 같은 위치에 그대로 유지되어야 합니다.
- 플레이스홀더를 번역하거나 다른 텍스트로 대체하는 것은 절대 금지됩니다.
</critical_placeholders>

<mandatory_completion>
- 주어진 모든 항목을 빠짐없이 번역하고 'TranslatedItem' 도구를 호출해야 합니다 - 누락 절대 금지
- 도구 호출을 하나라도 누락하면 작업 전체가 실패로 간주되고 큰 패널티가 부여됩니다
</mandatory_completion>

<forbidden>
- 영어 원문을 그대로 복사하는 것은 절대 금지됩니다
- 빈 번역이나 원문 그대로 두는 것은 허용되지 않습니다
- 번역된 텍스트에 괄호를 사용해서 영어 원문이나 설명을 추가하는 것은 금지됩니다
- [PXXX] 또는 [NEWLINE] 형식의 플레이스홀더를 삭제하거나 변경하는 것은 절대 금지됩니다.
- 일부 항목을 누락하거나 'TranslatedItem' 도구 호출을 생략하는 것은 절대 금지됩니다
- ID 값(T### 등)을 번역문에 포함하거나 ID만을 번역 결과로 반환하는 것은 절대 금지됩니다
- 용어집의 "(Context: ..." 부분을 번역 결과에 포함하는 것은 절대 금지됩니다
</forbidden>
</rules>"""

RETRY_TRANSLATION_PROMPT_TEMPLATE = """<instructions>
당신은 전문 번역가입니다. 이전에 번역에 실패한 항목들을 다시 번역해주세요.
이번에는 반드시 성공해야 합니다.
번역이 완료된 각 항목에 대해 'TranslatedItem' 도구를 호출하여 결과를 기록해주세요.
</instructions>

<glossary>
용어집 (일관성을 위해 반드시 준수):
{glossary}
</glossary>

<input>
재시도할 항목들:
{chunk}
</input>

<rules>
<critical>
- 이것은 재시도입니다. 이전에 실패했으므로 더욱 신중하게 번역하세요
- 모든 항목을 반드시 {language}로 완전히 번역해야 합니다
- 어려운 용어라도 용어집을 참고하거나 의미를 파악해서 번역하세요
- 고유명사나 브랜드명도 가능한 한 현지화하거나 {language}로 표기하세요
</critical>

<required>
- id는 절대 변경하지 마세요
- 이전에 실패했다고 해서 포기하지 말고 반드시 번역을 완료하세요
- 번역할 때 괄호 안에 영어 원문이나 설명을 추가하지 마세요 (예: "방패 (Shield)" 대신 "방패"로만 번역)
- 재시도하는 모든 항목에 대해 반드시 'TranslatedItem' 도구를 호출해야 합니다 - 누락 절대 금지
</required>

<glossary_usage>
- 용어집에서 "(Context: ...)" 부분은 참고용 정보일 뿐이며, 실제 번역에는 포함하지 마세요
- 예: "검사 (Context: 게임 직업)" → 번역 시 "검사"만 사용하고 "(Context: 게임 직업)" 부분은 무시하세요
- Context는 용어의 의미를 이해하는 데만 활용하고, 번역 결과에는 절대 포함하지 마세요
</glossary_usage>

<critical_placeholders>
- [PXXX] 또는 [NEWLINE] 형식의 플레이스홀더는 절대로 삭제하거나 변경하지 마세요.
- 이러한 플레이스홀더들은 번역 후 원본 내용으로 복원되는 매우 중요한 마커입니다.
- 플레이스홀더는 번역문에서 정확히 같은 위치에 그대로 유지되어야 합니다.
- 플레이스홀더를 번역하거나 다른 텍스트로 대체하는 것은 절대 금지됩니다.
- 재시도에서 특히 플레이스홀더 누락이 자주 발생하므로 더욱 주의하세요.
</critical_placeholders>

<mandatory_completion>
- 재시도하는 모든 항목을 빠짐없이 번역하고 'TranslatedItem' 도구를 호출해야 합니다 - 재시도에서도 일부만 번역하고 나머지를 누락하는 것은 절대 허용되지 않습니다
- 도구 호출을 하나라도 누락하면 작업 전체가 실패로 간주되고 큰 패널티가 부여됩니다
</mandatory_completion>

<forbidden>
- 영어 원문을 그대로 복사하거나 유지하는 것은 절대 금지됩니다 
- 빈 번역이나 원문 그대로 두는 것은 허용되지 않습니다
- 번역된 텍스트에 괄호를 사용해서 영어 원문이나 설명을 추가하는 것은 금지됩니다
- [PXXX] 또는 [NEWLINE] 형식의 플레이스홀더를 삭제하거나 변경하는 것은 절대 금지됩니다.
- 일부 항목을 누락하거나 'TranslatedItem' 도구 호출을 생략하는 것은 절대 금지됩니다
- ID 값(T### 등)을 번역문에 포함하거나 ID만을 번역 결과로 반환하는 것은 절대 금지됩니다
- 용어집의 "(Context: ..." 부분을 번역 결과에 포함하는 것은 절대 금지됩니다
</forbidden>
</rules>"""

CONTEXTUAL_TERMS_PROMPT_TEMPLATE = """<instructions>
당신은 용어 전문가입니다. 다음 텍스트에서 일관된 번역이 필요한 중요 용어를 추출해주세요.
</instructions>

<glossary>
{glossary}
</glossary>

<input>
{chunk}
</input>

<task>
텍스트에서 중요 용어를 추출하여 원본({language} 번역) 및 문맥을 제공하세요.
한 용어에 여러 의미가 있다면, 각 의미마다 'SimpleGlossaryTerm' 도구를 개별적으로 호출해주세요.
</task>

<rules>
<required>
- 중요한 용어만 추출하세요
- context는 10단어 미만으로 간결하게 작성하세요
- 각 용어의 의미/번역마다 'SimpleGlossaryTerm' 도구를 호출해야 합니다.
- 추출한 모든 용어에 대해 반드시 'SimpleGlossaryTerm' 도구를 호출해야 합니다 - 누락 절대 금지
</required>

<mandatory_completion>
- 추출한 모든 중요 용어에 대해 빠짐없이 'SimpleGlossaryTerm' 도구를 호출해야 합니다 - 누락 절대 금지
- 도구 호출을 하나라도 누락하면 작업 전체가 실패로 간주되고 큰 패널티가 부여됩니다
</mandatory_completion>
</rules>"""

RETRY_CONTEXTUAL_TERMS_PROMPT_TEMPLATE = """<instructions>
당신은 용어 전문가입니다. 이전에 용어 추출에 실패했으니 다시 시도해주세요.
이번에는 규칙을 반드시 준수해야 합니다.
</instructions>

<glossary>
{glossary}
</glossary>

<input>
{chunk}
</input>

<task>
텍스트에서 중요 용어를 추출하여 원본({language} 번역) 및 문맥을 제공하세요.
한 용어에 여러 의미가 있다면, 각 의미마다 'SimpleGlossaryTerm' 도구를 개별적으로 호출해주세요.
</task>

<rules>
<critical>
- 이것은 재시도입니다. 이전에 'context' 필드에 null 값을 제공하여 오류가 발생했습니다.
- 'context' 필드는 절대 null이 될 수 없으며, 항상 문자열 값을 가져야 합니다.
- 문맥을 찾기 어렵다면 "일반" 또는 "범용"과 같이 간단한 문자열이라도 반드시 제공해야 합니다.
</critical>

<required>
- 중요한 용어만 추출하세요
- context는 10단어 미만으로 간결하게 작성하세요
- 각 용어의 의미/번역마다 'SimpleGlossaryTerm' 도구를 호출해야 합니다.
- 추출한 모든 용어에 대해 반드시 'SimpleGlossaryTerm' 도구를 호출해야 합니다 - 누락 절대 금지
</required>

<mandatory_completion>
- 추출한 모든 중요 용어에 대해 빠짐없이 'SimpleGlossaryTerm' 도구를 호출해야 합니다 - 누락 절대 금지
- 도구 호출을 하나라도 누락하면 작업 전체가 실패로 간주되고 큰 패널티가 부여됩니다
</mandatory_completion>
</rules>"""

FINAL_FALLBACK_PROMPT_TEMPLATE = """<instructions>
당신은 번역 전문가입니다. 다음 텍스트는 이전에 번역에 실패했거나 플레이스홀더가 누락되었습니다.
이번에는 반드시 규칙을 준수하여 완벽하게 번역해야 합니다.
번역이 완료되면 'TranslatedItem' 도구를 호출하여 결과를 기록해주세요.
</instructions>

<metadata>
- 번역 대상 언어: {language}
- 원본 텍스트 ID: {text_id}
</metadata>

<input_text>
{original_text}
</input_text>

<required_placeholders>
번역문에 반드시 포함되어야 하는 플레이스홀더 목록입니다. 순서와 개수를 정확히 맞춰야 합니다.
{placeholders}
</required_placeholders>

<glossary>
{glossary}
</glossary>

<rules>
<critical>
- 이것은 최종 재시도입니다. 모든 규칙을 엄격하게 준수하세요.
- 번역 결과에는 반드시 <required_placeholders>에 명시된 모든 플레이스홀더가 포함되어야 합니다.
- 플레이스홀더를 절대 번역하거나 변경하거나 생략해서는 안 됩니다.
- 원본 텍스트의 플레이스홀더 순서와 구조를 최대한 유지해주세요.
- 번역 결과에는 반드시 ID를 포함하지 마세요.
</critical>

<forbidden>
- <required_placeholders>에 없는 플레이스홀더를 임의로 추가하지 마세요.
- 번역문에 영어 원문을 괄호로 포함하지 마세요. (예: "마법사 (Wizard)" -> "마법사")
- 빈 번역이나 원문과 동일한 번역은 허용되지 않습니다.
- 번역 결과에는 반드시 ID를 포함하지 마세요.
</forbidden>
</rules>
"""

QUALITY_REVIEW_PROMPT_TEMPLATE = """<instructions>
당신은 번역 품질 검토 전문가입니다. 다음 번역들을 검토하여 품질 문제를 찾아주세요.
문제를 발견할 때마다 즉시 'QualityIssue' 도구를 호출하여 개별 문제를 기록해주세요.
</instructions>

<input>
{review_text}
</input>

<review_criteria>
번역 품질 검토 기준:
1. 원문의 의미가 정확히 전달되었는지
2. 번역이 자연스럽고 읽기 쉬운지  
3. 플레이스홀더([P###], [NEWLINE] 등)가 보존되었는지
4. 용어나 표현이 일관성 있게 번역되었는지
5. 오타나 문법 오류가 없는지
6. 번역이 {target_language}의 자연스러운 표현인지
</review_criteria>

<rules>
<required>
- 각 [T아이디] 항목을 개별적으로 검토하세요
- 문제를 발견할 때마다 즉시 'QualityIssue' 도구를 호출하세요
- 각 문제에 대해 text_id, issue_type, severity, description을 명확히 기록하세요
- 심각도는 low, medium, high 중 하나로 분류하세요
- 가능하면 수정 제안(suggested_fix)도 제공하세요
- 검토를 완료한 후 발견된 모든 문제에 대해 'QualityIssue' 도구를 호출했는지 확인하세요
</required>

<issue_types>
주요 문제 유형:
- 오역: 원문의 의미가 잘못 번역됨
- 누락: 원문의 일부가 번역에서 빠짐
- 부자연스러움: 번역이 어색하거나 자연스럽지 않음
- 플레이스홀더 문제: [P###], [NEWLINE] 등이 누락되거나 변경됨
- 일관성 문제: 같은 용어가 다르게 번역됨
- 문법 오류: 맞춤법이나 문법상 오류
- 미번역: 원문이 그대로 유지됨
</issue_types>

<severity_guidelines>
심각도 분류 기준:
- high: 의미 왜곡, 플레이스홀더 누락, 완전한 오역
- medium: 어색한 표현, 일관성 문제, 부분적 오역
- low: 사소한 문법 오류, 더 나은 표현 제안
</severity_guidelines>

<workflow>
검토 진행 방식:
1. 각 번역 항목을 순서대로 검토
2. 문제 발견 시 즉시 'QualityIssue' 도구 호출
3. 모든 항목 검토 완료 후 누락된 문제가 없는지 재확인
4. 문제가 없는 항목이라도 검토했다는 의미로 간단한 확인 메시지 제공
</workflow>

<mandatory_completion>
- 모든 번역 항목을 빠짐없이 검토해야 합니다
- 발견된 모든 문제에 대해 반드시 'QualityIssue' 도구를 호출해야 합니다
- 문제가 없더라도 검토 과정을 완료해야 합니다
- 검토 작업을 중단하거나 일부를 건너뛰는 것은 금지됩니다
</mandatory_completion>

<examples>
좋은 QualityIssue 호출 예시:
- text_id: "T001"
- issue_type: "플레이스홀더 문제"
- severity: "high"
- description: "[P001] 플레이스홀더가 번역문에서 누락됨"
- suggested_fix: "번역문에 [P001] 플레이스홀더를 원래 위치에 추가"
</examples>
</rules>"""

QUALITY_RETRANSLATION_PROMPT_TEMPLATE = """<instructions>
당신은 전문 번역가입니다. 다음 텍스트들은 품질 검토에서 문제가 발견되어 재번역이 필요합니다.
각 항목의 문제점을 해결하여 고품질 번역을 제공해주세요.
번역이 완료된 각 항목에 대해 'TranslatedItem' 도구를 호출하여 결과를 기록해주세요.
</instructions>

<target_language>
{target_language}
</target_language>

<glossary>
{glossary}
</glossary>

<retry_info>
{retry_info}
</retry_info>

<input>
{formatted_items}
</input>

<rules>
<critical>
- 이것은 품질 문제 해결을 위한 재번역입니다
- 각 항목에 명시된 문제점을 반드시 해결해야 합니다
- 플레이스홀더([P###], [NEWLINE] 등)를 정확히 보존해야 합니다
- 발견된 문제의 수정 제안이 있다면 참고하여 번역하세요
</critical>

<required>
- id는 절대 변경하지 마세요
- 모든 항목을 반드시 {target_language}로 완전히 번역해야 합니다
- 품질 문제를 해결하면서도 원문의 의미를 정확히 전달해야 합니다
- 번역할 때 괄호 안에 영어 원문이나 설명을 추가하지 마세요
- 재번역하는 모든 항목에 대해 반드시 'TranslatedItem' 도구를 호출해야 합니다
</required>

<glossary_usage>
- 용어집에서 "(Context: ...)" 부분은 참고용 정보일 뿐이며, 실제 번역에는 포함하지 마세요
- Context는 용어의 의미를 이해하는 데만 활용하고, 번역 결과에는 절대 포함하지 마세요
</glossary_usage>

<critical_placeholders>
- [PXXX] 또는 [NEWLINE] 형식의 플레이스홀더는 절대로 삭제하거나 변경하지 마세요
- 이러한 플레이스홀더들은 번역 후 원본 내용으로 복원되는 중요한 마커입니다
- 플레이스홀더는 번역문에서 정확히 같은 위치에 그대로 유지되어야 합니다
- 플레이스홀더를 번역하거나 다른 텍스트로 대체하는 것은 절대 금지됩니다
</critical_placeholders>

<quality_improvement>
- 원문의 의미를 정확히 전달하면서도 자연스러운 번역을 제공하세요
- 일관성 있는 용어 사용을 위해 용어집을 적극 활용하세요
- 문법과 맞춤법을 정확히 지켜주세요
- {target_language}의 자연스러운 표현을 사용하세요
</quality_improvement>

<mandatory_completion>
- 재번역하는 모든 항목을 빠짐없이 번역하고 'TranslatedItem' 도구를 호출해야 합니다
- 문제가 있었던 항목이라도 반드시 번역을 시도하고 결과를 제출해야 합니다
- 재번역 작업을 중단하거나 일부를 건너뛰는 것은 금지됩니다
</mandatory_completion>

<forbidden>
- 영어 원문을 그대로 복사하거나 유지하는 것은 절대 금지됩니다
- 빈 번역이나 원문 그대로 두는 것은 허용되지 않습니다
- 번역된 텍스트에 괄호를 사용해서 영어 원문이나 설명을 추가하는 것은 금지됩니다
- [PXXX] 또는 [NEWLINE] 형식의 플레이스홀더를 삭제하거나 변경하는 것은 절대 금지됩니다
- 일부 항목을 누락하거나 'TranslatedItem' 도구 호출을 생략하는 것은 절대 금지됩니다
- ID 값(T### 등)을 번역문에 포함하거나 ID만을 번역 결과로 반환하는 것은 절대 금지됩니다
- 용어집의 "(Context: ..." 부분을 번역 결과에 포함하는 것은 절대 금지됩니다
</forbidden>
</rules>"""


def translation_prompt(language: str, glossary: str, chunk: str) -> str:
    """형식화된 번역 프롬프트를 반환합니다."""
    return TRANSLATION_PROMPT_TEMPLATE.format(
        language=language,
        glossary=glossary,
        chunk=chunk,
    )


def retry_translation_prompt(language: str, glossary: str, chunk: str) -> str:
    """형식화된 재시도 번역 프롬프트를 반환합니다."""
    return RETRY_TRANSLATION_PROMPT_TEMPLATE.format(
        language=language,
        glossary=glossary,
        chunk=chunk,
    )


def contextual_terms_prompt(language: str, chunk: str, glossary: str) -> str:
    """형식화된 문맥 기반 용어 추출 프롬프트를 반환합니다."""
    return CONTEXTUAL_TERMS_PROMPT_TEMPLATE.format(
        language=language, chunk=chunk, glossary=glossary
    )


def retry_contextual_terms_prompt(language: str, chunk: str, glossary: str) -> str:
    """형식화된 문맥 기반 용어 추출 재시도 프롬프트를 반환합니다."""
    return RETRY_CONTEXTUAL_TERMS_PROMPT_TEMPLATE.format(
        language=language, chunk=chunk, glossary=glossary
    )


def final_fallback_prompt(
    language: str,
    text_id: str,
    original_text: str,
    placeholders: str,
    glossary: str,
) -> str:
    """형식화된 최종 재시도 프롬프트를 반환합니다."""
    return FINAL_FALLBACK_PROMPT_TEMPLATE.format(
        language=language,
        text_id=text_id,
        original_text=original_text,
        placeholders=placeholders,
        glossary=glossary,
    )


def quality_review_prompt(target_language: str, review_text: str) -> str:
    """형식화된 품질 검토 프롬프트를 반환합니다."""
    return QUALITY_REVIEW_PROMPT_TEMPLATE.format(
        target_language=target_language,
        review_text=review_text,
    )


def quality_retranslation_prompt(
    target_language: str, glossary: str, retry_info: str, formatted_items: str
) -> str:
    """형식화된 품질 기반 재번역 프롬프트를 반환합니다."""
    return QUALITY_RETRANSLATION_PROMPT_TEMPLATE.format(
        target_language=target_language,
        glossary=glossary,
        retry_info=retry_info,
        formatted_items=formatted_items,
    )
