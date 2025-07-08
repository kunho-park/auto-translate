"""
토큰 사용량 추적을 위한 콜백 핸들러 모듈
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class TokenCountingHandler(BaseCallbackHandler):
    """토큰 사용량을 추적하는 콜백 핸들러"""

    def __init__(self):
        self.reset_counts()

    def reset_counts(self):
        """토큰 카운트 초기화"""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.provider_counts = {}  # 제공업체별 토큰 카운트

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 호출 완료 시 토큰 사용량 추적"""
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]

            # 토큰 카운트 업데이트
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)

            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            self.total_tokens += total_tokens

            # 제공업체별 카운트 (추가 정보가 있는 경우)
            model_name = response.llm_output.get("model_name", "unknown")
            if model_name not in self.provider_counts:
                self.provider_counts[model_name] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }

            self.provider_counts[model_name]["prompt_tokens"] += prompt_tokens
            self.provider_counts[model_name]["completion_tokens"] += completion_tokens
            self.provider_counts[model_name]["total_tokens"] += total_tokens

            logger.debug(
                f"토큰 사용량 - 프롬프트: {prompt_tokens}, "
                f"완료: {completion_tokens}, 총: {total_tokens}"
            )

    def get_token_summary(self) -> Dict[str, Any]:
        """토큰 사용량 요약 반환"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "provider_counts": self.provider_counts.copy(),
        }


class UniversalTokenCountingHandler(BaseCallbackHandler):
    """모든 제공업체에 대응하는 범용 토큰 카운팅 핸들러

    Args:
        update_callback: 토큰 카운트가 변경될 때마다 호출될 콜백 함수.
            콜백에는 `get_token_summary()` 결과 딕셔너리가 전달됩니다.
    """

    def __init__(self, update_callback: Optional[callable] = None):
        self.update_callback = update_callback
        self.reset_counts()

    def reset_counts(self):
        """토큰 카운트 초기화"""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.provider_counts = {}
        self.call_count = 0

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 호출 완료 시 토큰 사용량 추적 (모든 generation 집계)"""
        self.call_count += 1

        try:
            total_prompt = 0
            total_completion = 0
            found_tokens_in_generations = False

            # 1. 최신 방식: 모든 generation의 `usage_metadata` 순회 및 합산
            if response.generations:
                for gen_list in response.generations:
                    for gen in gen_list:
                        if (
                            hasattr(gen, "message")
                            and hasattr(gen.message, "usage_metadata")
                            and gen.message.usage_metadata
                        ):
                            usage_metadata = gen.message.usage_metadata
                            total_prompt += usage_metadata.get(
                                "input_tokens", 0
                            ) or usage_metadata.get("prompt_tokens", 0)
                            total_completion += usage_metadata.get(
                                "output_tokens", 0
                            ) or usage_metadata.get("completion_tokens", 0)
                            found_tokens_in_generations = True

            if found_tokens_in_generations:
                total = total_prompt + total_completion
                usage_dict = {
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_completion,
                    "total_tokens": total,
                }
                self._update_counts_from_usage(usage_dict, response.llm_output or {})
                return

            # 2. 구버전 방식: llm_output.token_usage (위에서 못 찾은 경우)
            if response.llm_output and "token_usage" in response.llm_output:
                token_usage_data = response.llm_output["token_usage"]
                prompt = token_usage_data.get(
                    "input_tokens", 0
                ) or token_usage_data.get("prompt_tokens", 0)
                completion = token_usage_data.get(
                    "output_tokens", 0
                ) or token_usage_data.get("completion_tokens", 0)
                total = token_usage_data.get("total_tokens", 0)

                if total == 0:
                    total = prompt + completion

                usage_dict = {
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "total_tokens": total,
                }

                self._update_counts_from_usage(usage_dict, response.llm_output or {})
                return

            # 토큰 정보를 찾지 못한 경우
            if self.call_count <= 5 or self.call_count % 50 == 0:
                logger.warning(
                    f"토큰 사용량 정보를 찾을 수 없습니다. 호출 #{self.call_count}"
                )

        except Exception as e:
            logger.error(f"토큰 카운팅 중 오류 발생 (호출 #{self.call_count}): {e}")
            if self.call_count <= 2:
                logger.debug(f"예외 발생 시 응답 구조: {vars(response)}")

        # 성공 로그 (호출 빈도 줄임)
        if self.call_count <= 3:
            logger.info(
                f"토큰 추적 성공 #{self.call_count}: "
                f"입력={self.prompt_tokens}, 출력={self.completion_tokens} -> 총 {self.total_tokens:,}"
            )
        elif self.call_count % 50 == 0:
            logger.info(
                f"토큰 사용량 누적 ({self.call_count}회) - 총 {self.total_tokens:,} 토큰"
            )

    def _update_counts_from_usage(self, token_usage: Dict, llm_output: Dict):
        """토큰 사용량으로 카운트 업데이트"""
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        total_tokens = token_usage.get("total_tokens", 0)

        # total_tokens가 0이면 계산
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens

        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens

        # 제공업체별 카운트
        model_name = llm_output.get("model_name", "unknown")
        if model_name not in self.provider_counts:
            self.provider_counts[model_name] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

        provider_count = self.provider_counts[model_name]
        provider_count["prompt_tokens"] += prompt_tokens
        provider_count["completion_tokens"] += completion_tokens
        provider_count["total_tokens"] += total_tokens

        # 실시간 콜백 실행 (예외는 무시하여 흐름 방해 방지)
        if self.update_callback:
            try:
                self.update_callback(self.get_token_summary())
            except Exception as cb_err:
                logger.debug(f"토큰 업데이트 콜백 오류 무시: {cb_err}")

    def get_token_summary(self) -> Dict[str, Any]:
        """토큰 사용량 요약 반환"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "provider_counts": self.provider_counts.copy(),
            "call_count": self.call_count,
        }

    def get_formatted_summary(self) -> str:
        """포맷된 토큰 사용량 요약 반환"""
        summary = self.get_token_summary()

        text = "📊 토큰 사용량 요약\n"
        text += f"🔤 입력 토큰: {summary['prompt_tokens']:,}\n"
        text += f"✍️ 출력 토큰: {summary['completion_tokens']:,}\n"
        text += f"📈 총 토큰: {summary['total_tokens']:,}\n"
        text += f"🔄 API 호출 횟수: {summary['call_count']}\n"

        if summary["provider_counts"]:
            text += "\n📋 모델별 상세:\n"
            for model, counts in summary["provider_counts"].items():
                text += f"  • {model}: {counts['total_tokens']:,} 토큰\n"

        return text
