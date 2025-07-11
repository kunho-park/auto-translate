"""
LLM Prompt Templates (XML Structure)
These functions return fully formatted prompts for the translation workflow.
"""

# XML-structured prompt templates
TRANSLATION_PROMPT_TEMPLATE = """<instructions>
You are a professional translator. Please translate the given text into {language}.
For each completed translation item, call the 'TranslatedItem' tool to record the result.
</instructions>

<glossary>
{glossary}
</glossary>

<input>
Items to translate:
{chunk}
</input>

<rules>
<required>
- Never change the id
- All items must be completely translated into {language}
- Even proper nouns or brand names should be translated into {language} or appropriately localized when possible
- For difficult technical terms, refer to the glossary or translate while preserving the meaning
- Do not add English original text or explanations in parentheses when translating (e.g., use "마법사" instead of "마법사 (Wizard)")
- You must call the 'TranslatedItem' tool for all given items - absolutely no omissions allowed
</required>

<glossary_usage>
- The "(Context: ...)" parts in the glossary are for reference only and should not be included in actual translations
- Example: "마법사 (Context: 게임 직업)" → Use only "마법사" in translation and ignore the "(Context: 게임 직업)" part
- Use Context only to understand the meaning of terms, never include it in translation results
</glossary_usage>

<critical_placeholders>
- Never delete or modify placeholders in the format [PXXX] or [NEWLINE].
- These placeholders are important markers that will be restored to original content after translation.
- Placeholders must remain in exactly the same position in the translated text.
- Translating or replacing placeholders with other text is absolutely forbidden.
</critical_placeholders>

<mandatory_completion>
- You must translate all given items without omission and call the 'TranslatedItem' tool - absolutely no omissions allowed
- Missing even one tool call will result in the entire task being considered failed with severe penalties
</mandatory_completion>

<forbidden>
- Copying English original text as-is is absolutely forbidden
- Empty translations or leaving original text unchanged is not allowed
- Adding English original text or explanations in parentheses to translated text is forbidden
- Deleting or modifying placeholders in the format [PXXX] or [NEWLINE] is absolutely forbidden.
- Omitting some items or skipping 'TranslatedItem' tool calls is absolutely forbidden
- Including ID values (T### etc.) in translations or returning only IDs as translation results is absolutely forbidden
- Including "(Context: ..." parts from the glossary in translation results is absolutely forbidden
</forbidden>
</rules>"""

RETRY_TRANSLATION_PROMPT_TEMPLATE = """<instructions>
You are a professional translator. Please re-translate the items that failed translation previously.
This time, you must succeed.
For each completed translation item, call the 'TranslatedItem' tool to record the result.
</instructions>

<glossary>
Glossary (must be followed for consistency):
{glossary}
</glossary>

<input>
Items to retry:
{chunk}
</input>

<rules>
<critical>
- This is a retry. Since it failed previously, translate more carefully
- All items must be completely translated into {language}
- Even difficult terms should be translated by referring to the glossary or understanding the meaning
- Proper nouns and brand names should also be localized or written in {language} when possible
</critical>

<required>
- Never change the id
- Don't give up just because it failed previously - you must complete the translation
- Do not add English original text or explanations in parentheses when translating (e.g., use "방패" instead of "방패 (Shield)")
- You must call the 'TranslatedItem' tool for all retry items - absolutely no omissions allowed
</required>

<glossary_usage>
- The "(Context: ...)" parts in the glossary are for reference only and should not be included in actual translations
- Example: "검사 (Context: 게임 직업)" → Use only "검사" in translation and ignore the "(Context: 게임 직업)" part
- Use Context only to understand the meaning of terms, never include it in translation results
</glossary_usage>

<critical_placeholders>
- Never delete or modify placeholders in the format [PXXX] or [NEWLINE].
- These placeholders are very important markers that will be restored to original content after translation.
- Placeholders must remain in exactly the same position in the translated text.
- Translating or replacing placeholders with other text is absolutely forbidden.
- Be especially careful about placeholder omissions in retries as they occur frequently.
</critical_placeholders>

<mandatory_completion>
- You must translate all retry items without omission and call the 'TranslatedItem' tool - even in retries, translating only some items and omitting the rest is absolutely not allowed
- Missing even one tool call will result in the entire task being considered failed with severe penalties
</mandatory_completion>

<forbidden>
- Copying or maintaining English original text as-is is absolutely forbidden
- Empty translations or leaving original text unchanged is not allowed
- Adding English original text or explanations in parentheses to translated text is forbidden
- Deleting or modifying placeholders in the format [PXXX] or [NEWLINE] is absolutely forbidden.
- Omitting some items or skipping 'TranslatedItem' tool calls is absolutely forbidden
- Including ID values (T### etc.) in translations or returning only IDs as translation results is absolutely forbidden
- Including "(Context: ..." parts from the glossary in translation results is absolutely forbidden
</forbidden>
</rules>"""

CONTEXTUAL_TERMS_PROMPT_TEMPLATE = """<instructions>
You are a terminology expert. Please extract important terms that need consistent translation from the following text.
</instructions>

<glossary>
{glossary}
</glossary>

<input>
{chunk}
</input>

<task>
Extract important terms from the text and provide original ({language} translation) and context.
If a term has multiple meanings, call the 'SimpleGlossaryTerm' tool separately for each meaning.
</task>

<rules>
<required>
- Extract only important terms
- Write context concisely in less than 10 words
- You must call the 'SimpleGlossaryTerm' tool for each meaning/translation of each term.
- You must call the 'SimpleGlossaryTerm' tool for all extracted terms - absolutely no omissions allowed
</required>

<mandatory_completion>
- You must call the 'SimpleGlossaryTerm' tool for all extracted important terms without omission - absolutely no omissions allowed
- Missing even one tool call will result in the entire task being considered failed with severe penalties
</mandatory_completion>
</rules>"""

RETRY_CONTEXTUAL_TERMS_PROMPT_TEMPLATE = """<instructions>
You are a terminology expert. Since term extraction failed previously, please try again.
This time, you must follow the rules strictly.
</instructions>

<glossary>
{glossary}
</glossary>

<input>
{chunk}
</input>

<task>
Extract important terms from the text and provide original ({language} translation) and context.
If a term has multiple meanings, call the 'SimpleGlossaryTerm' tool separately for each meaning.
</task>

<rules>
<critical>
- This is a retry. Previously, an error occurred because null values were provided in the 'context' field.
- The 'context' field can never be null and must always have a string value.
- If it's difficult to find context, you must provide at least a simple string like "general" or "universal".
</critical>

<required>
- Extract only important terms
- Write context concisely in less than 10 words
- You must call the 'SimpleGlossaryTerm' tool for each meaning/translation of each term.
- You must call the 'SimpleGlossaryTerm' tool for all extracted terms - absolutely no omissions allowed
</required>

<mandatory_completion>
- You must call the 'SimpleGlossaryTerm' tool for all extracted important terms without omission - absolutely no omissions allowed
- Missing even one tool call will result in the entire task being considered failed with severe penalties
</mandatory_completion>
</rules>"""

FINAL_FALLBACK_PROMPT_TEMPLATE = """<instructions>
You are a translation expert. The following text previously failed translation or had missing placeholders.
This time, you must translate perfectly by following the rules strictly.
Once translation is complete, call the 'TranslatedItem' tool to record the result.
Do not return translation result directly.
Use the 'TranslatedItem' tool to return the translation result.
</instructions>

<strong_critical>
- Absolutely all output must be provided via the 'TranslatedItem' tool.
- Under no circumstances is raw output or direct translation text allowed. 
- If you do not use the tool, the task will be considered failed.
</strong_critical>

<metadata>
- Target language: {language}
- Original text ID: {text_id}
</metadata>

<input_text>
```
{original_text}
```
</input_text>

<required_placeholders>
List of placeholders that must be included in the translation. The order and count must match exactly.
{placeholders}
</required_placeholders>

<glossary>
{glossary}
</glossary>

<rules>
<critical>
- This is the final retry. Follow all rules strictly.
- The translation result must include all placeholders specified in <required_placeholders>.
- Never translate, modify, or omit placeholders.
- Maintain the order and structure of placeholders from the original text as much as possible.
- Never include the ID in the translation result.
</critical>

<forbidden>
- Do not arbitrarily add placeholders not in <required_placeholders>.
- Do not include English original text in parentheses in translations. (e.g., "마법사 (Wizard)" -> "마법사")
- Empty translations or translations identical to the original are not allowed.
- Never include the ID in the translation result.
- Including ID values (T### etc.) in translations or returning only IDs as translation results is absolutely forbidden
- Including "(Context: ..." parts from the glossary in translation results is absolutely forbidden
</forbidden>
</rules>
"""

QUALITY_REVIEW_PROMPT_TEMPLATE = """<instructions>
You are a translation quality review expert. Please review the following translations to find quality issues.
Whenever you find an issue, immediately call the 'QualityIssue' tool to record individual problems.
</instructions>

<input>
{review_text}
</input>

<review_criteria>
Translation quality review criteria:
1. Whether the original meaning is accurately conveyed
2. Whether the translation is natural and easy to read
3. Whether placeholders ([P###], [NEWLINE], etc.) are preserved
4. Whether terms and expressions are consistently translated
5. Whether there are no typos or grammatical errors
6. Whether the translation is a natural expression in {target_language}
</review_criteria>

<rules>
<required>
- Review each [T-ID] item individually
- Immediately call the 'QualityIssue' tool whenever you find a problem
- Clearly record text_id, issue_type, severity, description for each problem
- Classify severity as one of: low, medium, high
- Provide suggested_fix when possible
- After completing the review, verify that you have called the 'QualityIssue' tool for all discovered problems
</required>

<issue_types>
Main issue types:
- Mistranslation: Original meaning is incorrectly translated
- Omission: Part of the original is missing from the translation
- Unnaturalness: Translation is awkward or unnatural
- Placeholder issues: [P###], [NEWLINE], etc. are missing or modified
- Consistency issues: Same terms are translated differently
- Grammar errors: Spelling or grammatical mistakes
- Untranslated: Original text remains unchanged
</issue_types>

<severity_guidelines>
Severity classification criteria:
- high: Meaning distortion, placeholder omission, complete mistranslation
- medium: Awkward expressions, consistency issues, partial mistranslation
- low: Minor grammatical errors, better expression suggestions
</severity_guidelines>

<workflow>
Review process:
1. Review each translation item in order
2. Immediately call 'QualityIssue' tool when problems are found
3. After completing all item reviews, recheck for any missed problems
4. Provide a brief confirmation message even for items without problems to indicate they were reviewed
</workflow>

<mandatory_completion>
- You must review all translation items without omission
- You must call the 'QualityIssue' tool for all discovered problems
- You must complete the review process even if no problems are found
- Stopping the review work or skipping parts is forbidden
</mandatory_completion>

<examples>
Good QualityIssue call example:
- text_id: "T001"
- issue_type: "Placeholder issues"
- severity: "high"
- description: "[P001] placeholder is missing from the translation"
- suggested_fix: "Add [P001] placeholder to the original position in the translation"
</examples>
</rules>"""

QUALITY_RETRANSLATION_PROMPT_TEMPLATE = """<instructions>
You are a professional translator. The following texts have quality issues discovered in review and need retranslation.
Please provide high-quality translations by resolving the problems in each item.
For each completed translation item, call the 'TranslatedItem' tool to record the result.
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
- This is retranslation to resolve quality issues
- You must resolve the problems specified for each item
- You must accurately preserve placeholders ([P###], [NEWLINE], etc.)
- If there are suggested fixes for discovered problems, refer to them when translating
</critical>

<required>
- Never change the id
- All items must be completely translated into {target_language}
- You must accurately convey the original meaning while resolving quality issues
- Do not add English original text or explanations in parentheses when translating
- You must call the 'TranslatedItem' tool for all retranslation items
</required>

<glossary_usage>
- The "(Context: ...)" parts in the glossary are for reference only and should not be included in actual translations
- Use Context only to understand the meaning of terms, never include it in translation results
</glossary_usage>

<critical_placeholders>
- Never delete or modify placeholders in the format [PXXX] or [NEWLINE]
- These placeholders are important markers that will be restored to original content after translation
- Placeholders must remain in exactly the same position in the translated text
- Translating or replacing placeholders with other text is absolutely forbidden
</critical_placeholders>

<quality_improvement>
- Provide natural translations that accurately convey the original meaning
- Actively use the glossary for consistent terminology
- Follow grammar and spelling accurately
- Use natural expressions in {target_language}
</quality_improvement>

<mandatory_completion>
- You must translate all retranslation items without omission and call the 'TranslatedItem' tool
- Even items that had problems must be translated and results submitted
- Stopping retranslation work or skipping parts is forbidden
</mandatory_completion>

<forbidden>
- Copying or maintaining English original text as-is is absolutely forbidden
- Empty translations or leaving original text unchanged is not allowed
- Adding English original text or explanations in parentheses to translated text is forbidden
- Deleting or modifying placeholders in the format [PXXX] or [NEWLINE] is absolutely forbidden
- Omitting some items or skipping 'TranslatedItem' tool calls is absolutely forbidden
- Including ID values (T### etc.) in translations or returning only IDs as translation results is absolutely forbidden
- Including "(Context: ..." parts from the glossary in translation results is absolutely forbidden
</forbidden>
</rules>"""


def translation_prompt(language: str, glossary: str, chunk: str) -> str:
    """Returns a formatted translation prompt."""
    return TRANSLATION_PROMPT_TEMPLATE.format(
        language=language,
        glossary=glossary,
        chunk=chunk,
    )


def retry_translation_prompt(language: str, glossary: str, chunk: str) -> str:
    """Returns a formatted retry translation prompt."""
    return RETRY_TRANSLATION_PROMPT_TEMPLATE.format(
        language=language,
        glossary=glossary,
        chunk=chunk,
    )


def contextual_terms_prompt(language: str, chunk: str, glossary: str) -> str:
    """Returns a formatted contextual term extraction prompt."""
    return CONTEXTUAL_TERMS_PROMPT_TEMPLATE.format(
        language=language, chunk=chunk, glossary=glossary
    )


def retry_contextual_terms_prompt(language: str, chunk: str, glossary: str) -> str:
    """Returns a formatted contextual term extraction retry prompt."""
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
    """Returns a formatted final retry prompt."""
    return FINAL_FALLBACK_PROMPT_TEMPLATE.format(
        language=language,
        text_id=text_id,
        original_text=original_text,
        placeholders=placeholders,
        glossary=glossary,
    )


def quality_review_prompt(target_language: str, review_text: str) -> str:
    """Returns a formatted quality review prompt."""
    return QUALITY_REVIEW_PROMPT_TEMPLATE.format(
        target_language=target_language,
        review_text=review_text,
    )


def quality_retranslation_prompt(
    target_language: str, glossary: str, retry_info: str, formatted_items: str
) -> str:
    """Returns a formatted quality-based retranslation prompt."""
    return QUALITY_RETRANSLATION_PROMPT_TEMPLATE.format(
        target_language=target_language,
        glossary=glossary,
        retry_info=retry_info,
        formatted_items=formatted_items,
    )
