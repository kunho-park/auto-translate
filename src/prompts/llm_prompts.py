"""
LLM Prompt Templates for GPT-5 (XML Structure)
Optimized for game localization workflow with GPT-5 best practices.
"""

# Translation Prompt - Optimized for GPT-5
TRANSLATION_PROMPT_TEMPLATE = """<role>
Expert translator specializing in game localization for sandbox and RPG genres.
Task: Translate English text into natural {language} while maintaining game context.
</role>

<planning_phase>
Before translating, create an internal plan:
1. Count the total items to translate
2. Identify complex terms requiring glossary reference
3. Note placeholder patterns and positions
4. Consider genre-specific language conventions
</planning_phase>

<translation_workflow>
<step phase="analyze">
Read each text to understand meaning, context, and game-specific nuances.
</step>

<step phase="glossary_check">
Reference the provided glossary for consistent terminology.
</step>

<step phase="translate">
Create natural {language} translations following local gaming conventions.
</step>

<step phase="placeholder_validation">
Ensure placeholders ([PXXX], [NEWLINE], [S숫자]) remain unchanged and correctly positioned.
</step>

<step phase="review">
Check for natural flow and gaming context appropriateness.
</step>

<step phase="submit">
Use TranslationResult tool with all translated items in one call.
</step>
</translation_workflow>

<glossary>
{glossary}
</glossary>

<input_text>
{chunk}
</input_text>

<translation_guidelines>
<quality_standards>
- Accuracy: Preserve original meaning and game mechanics
- Naturalness: Use fluent {language} gaming terminology
- Consistency: Apply glossary terms uniformly
- Completeness: Translate all provided items
</quality_standards>

<placeholder_rules>
Placeholders are functional game elements:
- Maintain exact format: [PXXX], [NEWLINE], [S숫자]
- Preserve count and relative positions
- Example: "Item [P001] gives [P002] points" → "아이템 [P001]은 [P002] 포인트를 줍니다"
</placeholder_rules>

<style_preferences>
- Integrate translations naturally without parenthetical English
- Translate proper nouns when they have clear meaning in {language}
- Preserve only actual player usernames (e.g., "Steve", "Alex")
- Adapt game terminology to local gaming culture
- NEVER use square brackets [] around translated terms - translate them naturally into the text
- Avoid marking translated terms with any special formatting or brackets
</style_preferences>

<natural_translation_examples>
CORRECT: "보스 몬스터는 일반 몬스터보다 어렵습니다"
INCORRECT: "[보스] [몬스터]는 일반 [몬스터]보다 어렵습니다"

CORRECT: "철 검을 제작하려면 철 주괴가 필요합니다"
INCORRECT: "[철] [검]을 제작하려면 [철] [주괴]가 필요합니다"
</natural_translation_examples>

<tool_usage>
TranslationResult accepts a list of TranslatedItem objects.
Submit all translations in a single tool call for efficiency.
Each item needs: id (string) and translated (string) fields.
</tool_usage>
</translation_guidelines>"""

# Retry Translation Prompt - Simplified for GPT-5
RETRY_TRANSLATION_PROMPT_TEMPLATE = """<role>
Expert translator retrying a previously failed translation.
Focus: Identify and correct the specific issue that caused failure.
</role>

<self_reflection>
Common failure causes to check:
- Placeholder count or order mismatch
- Incomplete item processing
- Glossary term inconsistency
- Tool usage errors
- Using square brackets around translated terms (avoid this)

Review the original attempt and identify the likely issue before proceeding.
</self_reflection>

<retry_workflow>
<step phase="diagnose">
Analyze what likely caused the previous failure, focusing on placeholders and completeness.
</step>

<step phase="reprocess">
Translate all items with extra attention to the identified issue.
</step>

<step phase="validate">
Double-check placeholder integrity and item count.
</step>

<step phase="submit">
Use TranslationResult tool with all corrected translations.
</step>
</retry_workflow>

<glossary>
{glossary}
</glossary>

<input_text>
{chunk}
</input_text>

<retry_guidelines>
<placeholder_verification>
Placeholders are the most common failure point.
Verify each placeholder ([PXXX], [NEWLINE], [S숫자]) is:
- Present in the translation
- Unmodified in format
- In semantically correct position
</placeholder_verification>

<natural_translation_reminder>
Do NOT use square brackets around translated game terms.
Translate terms naturally into the sentence flow.
Only preserve placeholders like [P001], [NEWLINE], [S숫자] which are functional elements.
</natural_translation_reminder>

<completeness_check>
Ensure all items from input are processed and submitted.
The tool expects all translations in one call.
</completeness_check>
</retry_guidelines>"""

# Contextual Terms Extraction - Streamlined for GPT-5
CONTEXTUAL_TERMS_PROMPT_TEMPLATE = """<role>
Terminology expert extracting key terms for translation consistency.
Focus: Identify game-specific terms needing consistent translation.
</role>

<extraction_strategy>
Prioritize terms that are:
- Game mechanics (items, skills, locations)
- Recurring UI elements
- Lore-specific names
- Technical gameplay terms
</extraction_strategy>

<workflow>
<step phase="scan">
Read the complete text to identify all candidate terms.
</step>

<step phase="categorize">
Classify terms by type: Item, Block, Mob, Skill, Location, UI Element, etc.
</step>

<step phase="translate">
Provide standard {language} translations including for proper nouns.
</step>

<step phase="structure">
Create GlossaryEntry objects with appropriate TermMeaning contexts.
CRITICAL: Each TermMeaning MUST include both 'translation' and 'context' fields.
</step>

<step phase="submit">
Call Glossary tool once with all extracted terms.
</step>
</workflow>

<existing_glossary>
{glossary}
</existing_glossary>

<input_text>
{chunk}
</input_text>

<extraction_guidelines>
<term_selection>
Focus on nouns, proper nouns, and game-specific verbs.
Skip generic words unless they have special game meaning.
Include terms likely to appear multiple times in the mod.
</term_selection>

<context_definition>
Provide concise, descriptive contexts like:
- "Crafting Material"
- "Boss Enemy"
- "Combat Skill"
- "Menu Option"
</context_definition>

<tool_usage>
Use Glossary tool with GlossaryEntry objects.
Each entry contains the term and its TermMeaning variations.
MANDATORY: Every TermMeaning object must have both 'translation' and 'context' fields filled.
Submit all terms in one tool call.
</tool_usage>
</extraction_guidelines>"""

# Retry Contextual Terms - Recovery approach for GPT-5
RETRY_CONTEXTUAL_TERMS_PROMPT_TEMPLATE = """<role>
Terminology expert retrying term extraction after previous failure.
Focus: Ensure all relevant terms are extracted with valid contexts and translations.
</role>

<failure_analysis>
Previous attempts typically fail due to:
- Missing 'translation' field in TermMeaning objects
- Missing or empty context fields
- Incomplete term processing (stopping too early)
- Invalid tool call structure
Review the input comprehensively this time.
</failure_analysis>

<retry_workflow>
<step phase="comprehensive_scan">
Read the entire text thoroughly to identify ALL game-specific terms.
</step>

<step phase="validate_structure">
Ensure every term has BOTH translation and context fields populated.
CRITICAL: TermMeaning requires 'translation' field - this is mandatory.
</step>

<step phase="complete_extraction">
Process every relevant term found, not just the first few.
</step>

<step phase="structure_properly">
Create valid GlossaryEntry objects with complete TermMeaning contexts.
Each TermMeaning MUST have:
- translation: The {language} translation of the term
- context: A descriptive context string
</step>

<step phase="submit_all">
Call Glossary tool once with all extracted terms.
</step>
</retry_workflow>

<existing_glossary>
{glossary}
</existing_glossary>

<input_text>
{chunk}
</input_text>

<retry_guidelines>
<mandatory_fields>
Every TermMeaning object MUST include:
- translation: The actual {language} translation (REQUIRED)
- context: Non-empty descriptive string (REQUIRED)
</mandatory_fields>

<context_requirements>
Every term needs a valid, non-empty context string.
Acceptable general contexts if specific ones are unclear:
- "General Term"
- "Game Concept" 
- "UI Element"
- "Game Feature"
</context_requirements>

<completeness_check>
Ensure comprehensive extraction:
- Items and equipment
- Locations and areas
- Characters and mobs
- Skills and abilities
- UI and system terms
- Mod-specific features
</completeness_check>

<tool_structure>
GlossaryEntry requires:
- original: The original English term
- meanings: List of TermMeaning objects, each with:
  - translation: {language} translation (MANDATORY FIELD)
  - context: Non-empty descriptive string (MANDATORY FIELD)
</tool_structure>
</retry_guidelines>"""

# Final Fallback - Focused approach for GPT-5
FINAL_FALLBACK_PROMPT_TEMPLATE = """<role>
Senior localization expert handling edge cases with complex placeholders.
This is a precision task requiring perfect placeholder preservation.
</role>

<problem_analysis>
Previous attempts failed likely due to complex placeholder arrangements.
The challenge: maintain exact placeholder sequence while creating natural translation.
</problem_analysis>

<precision_workflow>
<step phase="map_structure">
Map the semantic role of each placeholder in the original text.
</step>

<step phase="translate_segments">
Translate text segments between placeholders.
</step>

<step phase="reconstruct">
Rebuild the complete sentence with placeholders in correct positions.
</step>

<step phase="verify">
Cross-check against the required_placeholders list.
</step>

<step phase="submit">
Call TranslatedItem tool with the verified result.
</step>
</precision_workflow>

<item_details>
<text_id>{text_id}</text_id>
<original>{original_text}</original>
<required_placeholders>{placeholders}</required_placeholders>
</item_details>

<glossary>
{glossary}
</glossary>

<fallback_rules>
<primary_objective>
The translation succeeds only if placeholders match the required list exactly.
Natural language quality is secondary to placeholder accuracy.
</primary_objective>

<translation_approach>
Translate all content including proper nouns to {language}.
Exception: Actual Minecraft player usernames remain in English.
Do NOT use square brackets around translated terms - only preserve functional placeholders.
</translation_approach>
</fallback_rules>"""

# Quality Review - Balanced approach for GPT-5
QUALITY_REVIEW_PROMPT_TEMPLATE = """<role>
Quality assurance specialist reviewing game localization.
Objective: Systematically identify translation issues for improvement.
</role>

<review_methodology>
Evaluate translations across multiple dimensions:
- Semantic accuracy
- Language fluency
- Technical correctness (placeholders)
- Terminology consistency
- Cultural appropriateness
- Natural integration (no unnecessary brackets around terms)
</review_methodology>

<review_workflow>
<step phase="inventory">
Count and list all items to review.
</step>

<step phase="evaluate">
Assess each translation against quality criteria.
</step>

<step phase="document">
Record issues with specific details and severity.
</step>

<step phase="suggest">
Provide improvement suggestions where applicable.
</step>

<step phase="submit">
Call QualityReview tool with complete findings.
</step>
</review_workflow>

<review_input>
{review_text}
</review_input>

<quality_criteria>
<accuracy>
Does the translation preserve game mechanics and meaning?
</accuracy>

<fluency>
Is the {target_language} natural for gaming context?
Are terms integrated naturally without unnecessary brackets?
</fluency>

<technical>
Are placeholders ([P###], [NEWLINE], [S숫자]) perfectly preserved?
</technical>

<consistency>
Are glossary terms applied uniformly?
</consistency>

<completeness>
Is all content translated (except player usernames)?
</completeness>
</quality_criteria>

<issue_classification>
<types>
- Mistranslation: Core meaning error
- Unnatural: Awkward phrasing or unnecessary brackets around terms
- Placeholder: Missing or altered placeholder
- Consistency: Glossary term mismatch
- Omission: Missing content
- Grammar: Language errors
- Untranslated: Original language retained inappropriately
- Formatting: Unnecessary brackets around translated terms
</types>

<severity_levels>
- high: Game-breaking or meaning-altering
- medium: Noticeable quality issues
- low: Minor polish needed
</severity_levels>
</issue_classification>

<reporting_format>
Each issue needs:
- text_id: Item identifier
- issue_type: Classification from types list
- severity: Impact level
- description: Clear explanation
- suggested_fix: Proposed correction (optional)
</reporting_format>"""

# Quality Retranslation - Iterative improvement for GPT-5
QUALITY_RETRANSLATION_PROMPT_TEMPLATE = """<role>
Senior localization expert fixing flagged translation issues.
Task: Correct specific problems while maintaining overall quality.
</role>

<correction_strategy>
For each flagged item:
1. Understand the specific issue
2. Preserve what works in the current translation
3. Fix the identified problem
4. Verify no regression occurs
</correction_strategy>

<correction_workflow>
<step phase="analyze">
Review issue descriptions and suggested fixes.
</step>

<step phase="correct">
Apply targeted fixes addressing specific problems.
</step>

<step phase="preserve">
Maintain correct elements from original translation.
</step>

<step phase="validate">
Ensure fixes don't introduce new issues.
</step>

<step phase="submit">
Call TranslationResult with all corrected items.
</step>
</correction_workflow>

<glossary>
{glossary}
</glossary>

<items_to_fix>
{formatted_items}
</items_to_fix>

<correction_guidelines>
<id_preservation>
Maintain exact text IDs from input (T001, T002, etc.).
ID matching is essential for system processing.
</id_preservation>

<fix_priorities>
Address the reported issue type specifically:
- Placeholder issues: Restore correct placeholder sequence
- Unnatural phrasing: Improve fluency while keeping accuracy
- Untranslated content: Provide proper {target_language} translation
- Consistency issues: Apply correct glossary terms
- Formatting issues: Remove unnecessary brackets around translated terms
</fix_priorities>

<quality_maintenance>
Corrected translations should be in natural {target_language}.
Avoid reverting to English when fixing issues.
Translate all proper nouns except player usernames.
Do NOT use square brackets around translated game terms.
</quality_maintenance>

<tool_usage>
Submit all corrections via TranslationResult tool.
Include all items in a single tool call.
</tool_usage>
</correction_guidelines>"""


# Function definitions remain the same but with cleaner docstrings
def translation_prompt(language: str, glossary: str, chunk: str) -> str:
    """Generate a translation prompt optimized for GPT-5."""
    return TRANSLATION_PROMPT_TEMPLATE.format(
        language=language,
        glossary=glossary,
        chunk=chunk,
    )


def retry_translation_prompt(language: str, glossary: str, chunk: str) -> str:
    """Generate a retry translation prompt for failed attempts."""
    return RETRY_TRANSLATION_PROMPT_TEMPLATE.format(
        language=language,
        glossary=glossary,
        chunk=chunk,
    )


def contextual_terms_prompt(language: str, chunk: str, glossary: str) -> str:
    """Generate a term extraction prompt for glossary building."""
    return CONTEXTUAL_TERMS_PROMPT_TEMPLATE.format(
        language=language, chunk=chunk, glossary=glossary
    )


def retry_contextual_terms_prompt(language: str, chunk: str, glossary: str) -> str:
    """Generate a retry prompt for term extraction."""
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
    """Generate a final fallback prompt for complex cases."""
    return FINAL_FALLBACK_PROMPT_TEMPLATE.format(
        language=language,
        text_id=text_id,
        original_text=original_text,
        placeholders=placeholders,
        glossary=glossary,
    )


def quality_review_prompt(target_language: str, review_text: str) -> str:
    """Generate a quality review prompt for translation validation."""
    return QUALITY_REVIEW_PROMPT_TEMPLATE.format(
        target_language=target_language,
        review_text=review_text,
    )


def quality_retranslation_prompt(
    target_language: str, glossary: str, retry_info: str, formatted_items: str
) -> str:
    """Generate a retranslation prompt for quality improvements."""
    return QUALITY_RETRANSLATION_PROMPT_TEMPLATE.format(
        target_language=target_language,
        glossary=glossary,
        retry_info=retry_info,
        formatted_items=formatted_items,
    )
