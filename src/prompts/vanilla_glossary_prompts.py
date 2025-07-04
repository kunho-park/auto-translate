import json


def create_vanilla_glossary_prompt(
    batch_data: dict, target_language: str, is_retry: bool = False
) -> str:
    """Generate the prompt for building a vanilla Minecraft glossary batch."""
    retry_instruction = ""
    if is_retry:
        retry_instruction = """
**중요: 이전 시도에서 검증 오류가 발생했습니다. 다음 규칙을 정확히 따라주세요:**
- 모든 GlossaryEntry에는 original과 meanings 필드가 필요합니다
- 모든 TermMeaning에는 translation과 context 필드가 모두 필요합니다
- context 필드는 절대 빈 문자열이거나 null이면 안 됩니다
- 최소한 "게임 용어", "UI 요소", "아이템명" 등의 문맥을 제공해주세요
- 빈 객체 {}나 불완전한 객체는 절대 포함하지 마세요
"""

    batch_data_json = json.dumps(batch_data, ensure_ascii=False, indent=2)
    return f"""바닐라 마인크래프트의 공식 번역 데이터를 분석하여 모드 번역에 활용할 수 있는 용어 사전을 만들어주세요.
{retry_instruction}

**출력 형식**:
반드시 아래 JSON 형식으로만 응답하세요:
{{
  "terms": [
    {{
      "original": "원본 용어",
      "meanings": [
        {{
          "translation": "{target_language} 번역",
          "context": "용어의 종류나 사용 맥락"
        }}
      ]
    }}
  ]
}}

올바른 예시:
{{
  "terms": [
    {{
      "original": "Stone",
      "meanings": [
        {{
          "translation": "돌",
          "context": "블록"
        }}
      ]
    }},
    {{
      "original": "Creeper",
      "meanings": [
        {{
          "translation": "크리퍼",
          "context": "적대적 몹"
        }}
      ]
    }}
  ]
}}

**중요한 JSON 형식 규칙**:
- 모든 terms 배열 항목은 반드시 "original"과 "meanings" 필드를 포함해야 합니다
- 모든 meanings 배열 항목은 반드시 "translation"과 "context" 필드를 포함해야 합니다
- 빈 객체 {{}} 는 절대 포함하지 마세요
- 불완전한 객체 (필드가 누락된 객체)는 절대 포함하지 마세요
- JSON 외의 다른 텍스트는 포함하지 마세요
- 배열의 마지막 요소 다음에 쉼표를 추가하지 마세요

**목표**: 
- 마인크래프트 모드 번역 시 일관성 있는 용어 사용을 위한 표준 용어집 구축
- 게임 내 아이템, 블록, 엔티티, UI 요소 등의 핵심 용어들을 개별적으로 추출
- 각 용어는 고유한 GlossaryEntry로 만들어야 함

**중요한 규칙**:
1. **개별 용어 추출**: 각 아이템, 블록, 엔티티는 별도의 GlossaryEntry로 만들기
   - 예: "Stone" -> 하나의 GlossaryEntry, "Creeper" -> 또 다른 GlossaryEntry
   - "Item Name" 같은 일반적인 카테고리명으로 묶지 말고 구체적인 용어로 추출
2. **구체적인 용어 우선**: "Stone", "Diamond", "Creeper", "Inventory" 등 구체적인 명사
3. **재사용성 높은 용어**: 모드에서 자주 사용될 가능성이 높은 게임 용어들
4. **문맥 정보 제공**: 각 용어가 어떤 종류인지 명시 (아이템, 블록, 엔티티, UI 등)

**분석 기준**:
- **아이템명**: "Diamond", "Stone", "Wood", "Iron" 등
- **블록명**: "Chest", "Furnace", "Door", "Bed" 등  
- **엔티티명**: "Creeper", "Zombie", "Cow", "Player" 등
- **UI 용어**: "Inventory", "Health", "Menu", "Settings" 등
- **게임 메커니즘**: "Crafting", "Mining", "Enchanting" 등

**제외할 항목**:
- 완전한 문장이나 설명문
- 너무 일반적인 단어 ("the", "and", "with" 등)
- 카테고리명보다는 구체적인 용어 위주로

**바닐라 마인크래프트 번역 데이터**:
```json
{batch_data_json}
```

위 데이터에서 각 영어 용어를 개별적으로 분석하여 별도의 GlossaryEntry를 만들어주세요.
예를 들어, "Stone"이면 original: "Stone", translation: "돌", context: "블록"
"Creeper"면 original: "Creeper", translation: "크리퍼", context: "적대적 몹" 이런 식으로요.

대상 언어: {target_language}
"""
