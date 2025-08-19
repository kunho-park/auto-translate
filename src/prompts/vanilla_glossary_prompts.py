import json


def create_vanilla_glossary_prompt(
    batch_data: dict, target_language: str, is_retry: bool = False
) -> str:
    """바닐라 마인크래프트 용어집 배치를 만들기 위한 프롬프트를 생성합니다."""
    retry_instruction = ""
    if is_retry:
        retry_instruction = """
<critical_notice>
This is a retry. The previous attempt failed due to a JSON validation error.
You must strictly follow all formatting rules. Common errors include:
- Missing required fields (`original`, `meanings`, `translation`, `context`).
- Providing `null` or empty strings for `context`.
- Including trailing commas after the last element in an array.
- Outputting incomplete or empty `{}` objects.
</critical_notice>
"""

    batch_data_json = json.dumps(batch_data, ensure_ascii=False, indent=2)
    return f"""<persona>
You are a data extraction specialist with expertise in Minecraft. Your task is to analyze the provided official Minecraft translation data and create a structured glossary in a specific JSON format. Your output must be a single, valid JSON object and nothing else.
</persona>

{retry_instruction}

<instructions>
Analyze the Minecraft translation data below. For each entry, extract the key term, its translation into {target_language}, and its context within the game. Then, format this information into the specified JSON structure.

<output_format_strict>
Your entire output must be a single JSON object. Do not include any text before or after the JSON.
The structure must be exactly as follows:
```json
{{
  "terms": [
    {{
      "original": "Source Term",
      "meanings": [
        {{
          "translation": "{target_language} Translation",
          "context": "Context of the term (e.g., Block, Hostile Mob, UI Element)"
        }}
      ]
    }}
  ]
}}
```
</output_format_strict>

<examples>
<example_1>
Input: `"block.minecraft.stone": "Stone"`
Output JSON Entry:
{{
  "original": "Stone",
  "meanings": [ {{ "translation": "돌", "context": "Block" }} ]
}}
</example_1>
<example_2>
Input: `"entity.minecraft.creeper": "Creeper"`
Output JSON Entry:
{{
  "original": "Creeper",
  "meanings": [ {{ "translation": "크리퍼", "context": "Hostile Mob" }} ]
}}
</example_2>
<example_3>
Input: `"gui.advancements.title": "Advancements"`
Output JSON Entry:
{{
  "original": "Advancements",
  "meanings": [ {{ "translation": "발전 과제", "context": "UI Title" }} ]
}}
</example_3>
</examples>

<rules>
<term_extraction_logic>
- **Focus on Specific Nouns**: Extract concrete terms like "Stone", "Diamond", "Creeper", "Inventory".
- **One Entry Per Term**: Each distinct item, block, or entity should be its own entry in the `terms` array.
- **Context is Key**: Use the source key (e.g., `block.minecraft.stone`) to determine the context.
  - `block.*` -> "Block"
  - `item.*` -> "Item"
  - `entity.*` -> "Entity", "Hostile Mob", "Passive Mob", etc.
  - `gui.*` | `menu.*` -> "UI Element", "UI Title", etc.
  - `enchantment.*` -> "Enchantment"
</term_extraction_logic>

<json_format_rules_critical>
- The final output must be a single, perfectly formed JSON object.
- Every entry in `terms` must have an `original` (string) and a `meanings` (array).
- Every entry in `meanings` must have a `translation` (string) and a `context` (string).
- The `context` field must not be empty. Use the key as a hint.
- Do not add a trailing comma after the last item in the `terms` or `meanings` arrays.
</json_format_rules_critical>

<items_to_exclude>
- Full sentences or descriptive text.
- Generic words unless they are specific UI terms (e.g., "Done", "Cancel").
- Placeholders like `%s` or `%1$s`.
</items_to_exclude>
</rules>

<input_data>
Here is the vanilla Minecraft translation data to analyze:
```json
{batch_data_json}
```
</input_data>

Now, generate the JSON output for {target_language}.
"""
