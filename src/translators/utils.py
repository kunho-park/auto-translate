from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

import regex as re

from .models import GlossaryEntry, TermMeaning

logger = logging.getLogger(__name__)

__all__ = [
    "RequestDelayManager",
    "PlaceholderManager",
    "TokenOptimizer",
    "is_korean_text",
]


def is_korean_text(text: str) -> bool:
    """텍스트가 한글인지 확인하는 함수"""
    if not text or not isinstance(text, str):
        return False

    # 한글 문자 범위: 가-힣 (완성형 한글)
    korean_char_count = sum(1 for char in text if "가" <= char <= "힣")

    # 전체 문자 중 한글 문자 비율이 30% 이상이면 한글 텍스트로 판단
    total_chars = len([char for char in text if char.isalpha()])
    if total_chars == 0:
        return False

    korean_ratio = korean_char_count / total_chars
    return korean_ratio >= 0.3


class RequestDelayManager:
    """글로벌 요청 간격을 보장하는 비동기 딜레이 관리자.

    여러 코루틴이 동시에 API 요청을 시도해도 최소 `delay_ms` 만큼의 간격을 확보합니다.
    1) 각 요청 전에 `wait()` 를 호출합니다.
    2) 내부에서 마지막 요청 시각을 체크해 부족한 시간을 `await asyncio.sleep()` 으로 채웁니다.
    """

    def __init__(self, delay_ms: int):
        self.delay_seconds = max(delay_ms / 1000.0, 0.0)
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0

    async def wait(self) -> None:  # noqa: D401 – imperative mood is fine
        """다음 요청까지 필요한 만큼 대기한다."""
        if self.delay_seconds <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.delay_seconds:
                await asyncio.sleep(self.delay_seconds - elapsed)
            # 요청 직전 시간을 기록
            self._last_request_time = time.monotonic()


class PlaceholderManager:
    """Extraction and restoration of special placeholder patterns."""

    FORMAT_CODE_PATTERN = r"[§&][0-9a-fk-or]"
    C_PLACEHOLDER_PATTERN = r"%(?:[0-9]+\$[sd]|[sd])"  # %1$s, %2$d, %s, %d 등
    ITEM_PLACEHOLDER_PATTERN = r"\$\([^)]*\)"
    JSON_PLACEHOLDER_PATTERN = r"([{\[]{1}([,:{}\[\]0-9.\-+Eaeflnr-u \n\r\t]|\".*?\")+[}\]]{1})"  # JSON 객체와 배열 모두 지원
    HTML_TAG_PATTERN = r"<[^>]*>"
    MINECRAFT_ITEM_CODE_PATTERN = (
        r"(\{[a-zA-Z_0-9]+[:.][a-zA-Z_0-9/.]+\})|"
        r"((\[[a-zA-Z_0-9]+[:.]([0-9a-zA-Z_]+([./][0-9a-zA-Z_]+)*)\])|"
        r"([a-zA-Z_0-9]+[:.]([0-9a-zA-Z_]+([./][0-9a-zA-Z_]+)*)))"
    )
    JS_TEMPLATE_LITERAL_PATTERN = r"\$\{[^}]+\}"
    SQUARE_BRACKET_TAG_PATTERN = (
        r"\[[a-zA-Z_0-9]+[:][a-zA-Z_0-9/.]+\]"  # [minecraft:stone] 형태만 매칭
    )
    LEGACY_MINECRAFT_PATTERN = r"%[a-zA-Z_][a-zA-Z0-9_]*%"  # %username% 등
    NEWLINE_PATTERN = r"\\n|\\r\\n|\\r"  # \n, \r\n, \r 개행 문자들
    LONG_SPACE_PATTERN = r" {2,}|^\s+"  # 2개 이상의 연속 공백 또는 시작 공백
    # 이미지 플레이스홀더 패턴: {image:...} 또는 {image:... width:... height:... align:...}
    IMAGE_PLACEHOLDER_PATTERN = r"\{image:[^}]+\}"
    # 페이지 구분자({@pagebreak}) 패턴 추가
    PAGEBREAK_PATTERN = r"\{@pagebreak\}"

    _PLACEHOLDER_PATTERNS: List[str] = [
        IMAGE_PLACEHOLDER_PATTERN,
        PAGEBREAK_PATTERN,
        JSON_PLACEHOLDER_PATTERN,
        NEWLINE_PATTERN,
        LONG_SPACE_PATTERN,
        C_PLACEHOLDER_PATTERN,
        FORMAT_CODE_PATTERN,
        ITEM_PLACEHOLDER_PATTERN,
        HTML_TAG_PATTERN,
        MINECRAFT_ITEM_CODE_PATTERN,
        JS_TEMPLATE_LITERAL_PATTERN,
        SQUARE_BRACKET_TAG_PATTERN,
        LEGACY_MINECRAFT_PATTERN,
        r"\{\{[^}]+\}\}",
    ]
    _INTERNAL_PLACEHOLDER_PATTERN = r"\[P\d{3,}\]"
    _INTERNAL_NEWLINE_PATTERN = r"\[NEWLINE\]"
    _INTERNAL_SPACE_PATTERN = r"\[S\d*\]"
    _placeholder_counter = 0

    @staticmethod
    def reset_counter() -> None:
        PlaceholderManager._placeholder_counter = 0

    @staticmethod
    def extract_special_patterns_from_value(
        text: str, placeholders: Dict[str, str]
    ) -> str:
        if not isinstance(text, str):
            return text

        text = PlaceholderManager._extract_newlines(text, placeholders)
        text = PlaceholderManager._extract_spaces(text, placeholders)

        matches: List[str] = []
        for pattern in PlaceholderManager._PLACEHOLDER_PATTERNS:
            if pattern in [
                PlaceholderManager.NEWLINE_PATTERN,
                PlaceholderManager.LONG_SPACE_PATTERN,
            ]:
                continue
            found_matches = re.findall(pattern, text)
            for match in found_matches:
                if isinstance(match, tuple):
                    match_str = next((g for g in match if g), match[0])
                else:
                    match_str = match
                matches.append(match_str)

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
        if not isinstance(text, str):
            return text

        newline_placeholder = "[NEWLINE]"
        text = text.replace("\\r\\n", newline_placeholder)
        text = text.replace("\\n", newline_placeholder)
        text = text.replace("\\r", newline_placeholder)
        if newline_placeholder in text:
            placeholders[newline_placeholder] = "\\n"
        return text

    @staticmethod
    def _extract_spaces(text: str, placeholders: Dict[str, str]) -> str:
        if not isinstance(text, str):
            return text

        def replace_space(match):
            original_spaces = match.group(0)
            # 원본 공백 시퀀스의 길이를 저장
            space_key = f"[S{len(original_spaces)}]"
            placeholders[space_key] = original_spaces
            return space_key

        text = re.sub(r" {2,}", replace_space, text)
        text = re.sub(r"^\s+", replace_space, text)
        return text

    @staticmethod
    def process_json_object(obj: Any, placeholders: Dict[str, str]) -> Any:
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
        text = PlaceholderManager._restore_newlines(text, placeholders)
        text = PlaceholderManager._restore_spaces(text, placeholders)
        sorted_placeholders = sorted(
            placeholders.items(),
            key=lambda item: (int(item[0][2:-1]) if item[0].startswith("[P") else -1),
            reverse=True,
        )
        for pid, original in sorted_placeholders:
            if pid in ["[NEWLINE]"] or (pid.startswith("[S") and pid.endswith("]")):
                continue
            text = text.replace(pid, original)
        return text

    @staticmethod
    def _restore_newlines(text: str, placeholders: Dict[str, str]) -> str:
        if not isinstance(text, str):
            return text
        if "[NEWLINE]" in placeholders:
            text = text.replace("[NEWLINE]", placeholders["[NEWLINE]"])
        return text

    @staticmethod
    def _restore_spaces(text: str, placeholders: Dict[str, str]) -> str:
        if not isinstance(text, str):
            return text
        # [S숫자] 형태의 모든 공백 플레이스홀더를 복원
        for placeholder_key, original_spaces in placeholders.items():
            if placeholder_key.startswith("[S") and placeholder_key.endswith("]"):
                text = text.replace(placeholder_key, original_spaces)
        return text

    @staticmethod
    def _restore_placeholders_in_string(
        text: str, sorted_placeholders: List[tuple[str, str]], newline_value: str | None
    ) -> str:
        if not isinstance(text, str):
            return text
        if newline_value and "[NEWLINE]" in text:
            text = text.replace("[NEWLINE]", newline_value)
        # [S숫자] 형태의 모든 공백 플레이스홀더를 복원
        space_placeholders = {
            k: v
            for k, v in sorted_placeholders
            if k.startswith("[S") and k.endswith("]")
        }
        for placeholder_key, original_spaces in space_placeholders.items():
            if placeholder_key in text:
                text = text.replace(placeholder_key, original_spaces)
        for pid, original in sorted_placeholders:
            if pid in text:
                text = text.replace(pid, original)
        return text

    @staticmethod
    def restore_placeholders_in_json(
        json_obj: Any,
        sorted_placeholders: List[tuple[str, str]],
        newline_value: str | None,
    ) -> Any:
        if isinstance(json_obj, dict):
            return {
                k: PlaceholderManager.restore_placeholders_in_json(
                    v, sorted_placeholders, newline_value
                )
                for k, v in json_obj.items()
            }
        elif isinstance(json_obj, (list, tuple)):
            return [
                PlaceholderManager.restore_placeholders_in_json(
                    i, sorted_placeholders, newline_value
                )
                for i in json_obj
            ]
        elif isinstance(json_obj, str):
            return PlaceholderManager._restore_placeholders_in_string(
                text=json_obj,
                sorted_placeholders=sorted_placeholders,
                newline_value=newline_value,
            )
        else:
            return json_obj

    @staticmethod
    def extract_placeholders_from_text(text: str) -> List[str]:
        if not isinstance(text, str):
            return []
        placeholders: List[str] = []
        for pattern in PlaceholderManager._PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    match_str = next((g for g in match if g), match[0])
                else:
                    match_str = match
                if match_str and match_str not in placeholders:
                    placeholders.append(match_str)
        return placeholders

    @staticmethod
    def validate_placeholder_preservation(original: str, translated: str) -> bool:
        if not isinstance(original, str) or not isinstance(translated, str):
            return True

        original_counts = PlaceholderManager._count_internal_placeholders(original)
        translated_counts = PlaceholderManager._count_internal_placeholders(translated)

        return original_counts == translated_counts

    @staticmethod
    def get_missing_placeholders(original: str, translated: str) -> List[str]:
        if not isinstance(original, str) or not isinstance(translated, str):
            return []

        original_counts = PlaceholderManager._count_internal_placeholders(original)
        translated_counts = PlaceholderManager._count_internal_placeholders(translated)

        missing = []
        all_keys = set(original_counts.keys()) | set(translated_counts.keys())

        for key in all_keys:
            original_count = original_counts.get(key, 0)
            translated_count = translated_counts.get(key, 0)
            if original_count != translated_count:
                missing.append(
                    f"{key} (expected {original_count}, found {translated_count})"
                )
        return missing

    @staticmethod
    def _count_internal_placeholders(text: str) -> Dict[str, int]:
        if not isinstance(text, str):
            return {}

        counts = {}
        # Count [P###] placeholders
        p_placeholders = re.findall(
            PlaceholderManager._INTERNAL_PLACEHOLDER_PATTERN, text
        )
        for p in p_placeholders:
            counts[p] = counts.get(p, 0) + 1

        # Count [NEWLINE]
        newline_count = len(
            re.findall(PlaceholderManager._INTERNAL_NEWLINE_PATTERN, text)
        )
        if newline_count > 0:
            counts["[NEWLINE]"] = newline_count

        # Count [S숫자] - 각 고유한 [S숫자] 플레이스홀더를 개별적으로 카운팅
        space_placeholders = re.findall(
            PlaceholderManager._INTERNAL_SPACE_PATTERN, text
        )
        for space_placeholder in space_placeholders:
            counts[space_placeholder] = counts.get(space_placeholder, 0) + 1

        return counts

    @staticmethod
    def _extract_internal_placeholders(text: str) -> List[str]:
        if not isinstance(text, str):
            return []
        placeholders = re.findall(
            PlaceholderManager._INTERNAL_PLACEHOLDER_PATTERN, text
        )
        newlines = re.findall(PlaceholderManager._INTERNAL_NEWLINE_PATTERN, text)
        spaces = re.findall(PlaceholderManager._INTERNAL_SPACE_PATTERN, text)
        return placeholders + newlines + spaces

    @staticmethod
    def is_placeholder_only(text: str) -> bool:
        """텍스트가 placeholder만으로 구성되어 있는지 확인"""
        if not isinstance(text, str):
            return False

        text = text.strip()
        if not text:
            return False

        # 모든 내부 placeholder를 제거
        temp_text = text
        temp_text = re.sub(
            PlaceholderManager._INTERNAL_PLACEHOLDER_PATTERN, "", temp_text
        )
        temp_text = re.sub(PlaceholderManager._INTERNAL_NEWLINE_PATTERN, "", temp_text)
        temp_text = re.sub(PlaceholderManager._INTERNAL_SPACE_PATTERN, "", temp_text)

        # 모든 placeholder가 제거된 후 남은 텍스트가 있는지 확인
        remaining_text = temp_text.strip()

        return len(remaining_text) == 0


class TokenOptimizer:
    """Helpers for ID substitution and token-count heuristics."""

    _id_counter = 0

    @staticmethod
    def reset_id_counter() -> None:
        TokenOptimizer._id_counter = 0

    @staticmethod
    def format_chunk_for_llm(chunk: List[Dict[str, str]]) -> str:
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
        if not meanings:
            return meanings
        original_count = len(meanings)
        seen_translations = set()
        deduplicated: List[TermMeaning] = []
        for meaning in meanings:
            translation_key = meaning.translation.lower().strip()
            if translation_key not in seen_translations:
                seen_translations.add(translation_key)
                deduplicated.append(meaning)
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
        existing_translations = {
            meaning.translation.lower().strip() for meaning in existing_meanings
        }
        merged_meanings = existing_meanings.copy()
        for new_meaning in new_meanings:
            translation_key = new_meaning.translation.lower().strip()
            if translation_key not in existing_translations:
                merged_meanings.append(new_meaning)
                existing_translations.add(translation_key)
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
            TokenOptimizer._id_counter += 1
            text_id = f"T{TokenOptimizer._id_counter:03d}"
            id_map[text_id] = json_obj
            return text_id
        return json_obj

    @staticmethod
    def replace_text_with_ids_selective(
        json_obj: Any, id_map: Dict[str, str], existing_translations: Dict[str, str]
    ) -> Any:
        """기존 번역이 있는 항목은 번역으로 직접 대체하고, 없는 항목만 ID로 처리"""
        if isinstance(json_obj, dict):
            return {
                k: TokenOptimizer.replace_text_with_ids_selective(
                    v, id_map, existing_translations
                )
                for k, v in json_obj.items()
            }
        if isinstance(json_obj, list):
            return [
                TokenOptimizer.replace_text_with_ids_selective(
                    i, id_map, existing_translations
                )
                for i in json_obj
            ]
        if isinstance(json_obj, str) and json_obj.strip():
            text = json_obj.strip()

            # placeholder만으로 구성된 텍스트는 번역하지 않음
            if PlaceholderManager.is_placeholder_only(text):
                logger.debug(f"Placeholder만으로 구성된 텍스트 건너뛰기: '{text}'")
                return json_obj

            # 이미 한글로 번역된 텍스트인지 확인
            if is_korean_text(text):
                # 이미 한글 텍스트면 그대로 반환 (번역 불필요)
                return json_obj

            # 이미 번역된 항목이 있는지 체크
            if text in existing_translations:
                # 이미 번역된 텍스트가 있으면 해당 번역을 직접 반환
                return existing_translations[text]
            else:
                # 번역이 없으면 ID로 처리 (번역 대상)
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
                # ID 패턴(T###)과 placeholder만으로 구성된 텍스트 제외
                if not re.match(
                    r"^T\d{3,}$", obj
                ) and not PlaceholderManager.is_placeholder_only(obj):
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
