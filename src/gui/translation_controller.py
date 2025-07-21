"""
번역 작업 컨트롤러 모듈
"""

import asyncio
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

import flet as ft

from ..translators.modpack_translator import ModpackTranslator


class TranslationController:
    """번역 작업 컨트롤러 클래스"""

    def __init__(self, page: ft.Page):
        self.page = page

        # 번역 관련
        self.selected_modpack = None
        self.translator = None
        self.is_translating = False
        self.translation_task = None

        # 설정값들 (번역 영역 설정 포함)
        self.settings = {
            "llm_provider": "gemini",
            "llm_model": "gemini-2.0-flash",
            "temperature": 0.1,
            "max_tokens_per_chunk": 2000,
            "max_concurrent_requests": 35,
            "delay_between_requests_ms": 500,
            "max_retries": 10,
            "use_glossary": True,
            "create_backup": True,
            "enable_packaging": True,
            "enable_quality_review": True,
            "final_fallback_max_retries": 2,
            "max_quality_retries": 1,
            # 번역 영역 설정 (기본값: 모든 영역 활성화)
            "translate_mods": True,
            "translate_kubejs": True,
            "translate_resourcepacks": True,
            "translate_patchouli_books": True,
            "translate_ftbquests": True,
            "translate_config": True,
        }

        # 콜백들
        self.progress_callback = None
        self.completion_callback = None
        self.log_callback = None
        self.ui_update_callback = None
        self.token_update_callback = None  # 토큰 사용량 업데이트 콜백

    def set_modpack(self, modpack_info: Dict):
        """선택된 모드팩 설정"""
        self.selected_modpack = modpack_info

    def set_callbacks(
        self,
        progress_callback: Callable = None,
        completion_callback: Callable = None,
        log_callback: Callable = None,
        ui_update_callback: Callable = None,
        token_update_callback: Callable = None,
    ):
        """콜백 함수들 설정"""
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.log_callback = log_callback
        self.ui_update_callback = ui_update_callback
        self.token_update_callback = token_update_callback

    def update_setting(self, key: str, value):
        """설정값 업데이트"""
        self.settings[key] = value
        if self.log_callback:
            self.log_callback("DEBUG", f"설정 업데이트: {key} = {value}")

    def get_settings(self) -> Dict:
        """현재 설정값들 반환"""
        return self.settings.copy()

    def start_translation(
        self,
        selected_files: Optional[List[str]] = None,
        selected_glossary_files: Optional[List[str]] = None,
    ):
        """번역 시작"""
        if self.is_translating:
            if self.log_callback:
                self.log_callback("WARNING", "이미 번역이 진행 중입니다")
            return

        if self.log_callback:
            self.log_callback("INFO", "번역 시작 요청을 받았습니다")

        # Flet의 run_task를 사용하여 비동기 작업 실행
        self.page.run_task(
            self._start_translation_async,
            selected_files,
            selected_glossary_files,
        )

    async def _start_translation_async(
        self,
        selected_files: Optional[List[str]] = None,
        selected_glossary_files: Optional[List[str]] = None,
    ):
        """실제 번역 시작 로직 (비동기)"""
        if self.is_translating:
            return

        self.is_translating = True

        if self.log_callback:
            self.log_callback("INFO", "번역 작업을 초기화합니다")

        # UI 상태 업데이트
        if self.ui_update_callback:
            self.ui_update_callback(True)

        # 진행률 콜백 시작
        if self.progress_callback:
            self.progress_callback("번역 초기화 중...", 0, 0, "")

        try:
            # 번역기 초기화
            await self._initialize_translator()

            # 번역 실행
            await self._run_translation(selected_files, selected_glossary_files)

        except Exception as error:
            if self.log_callback:
                self.log_callback("ERROR", f"번역 중 오류 발생: {error}")
            if self.progress_callback:
                self.progress_callback("오류 발생", 0, 0, str(error))
        finally:
            self.is_translating = False
            if self.ui_update_callback:
                self.ui_update_callback(False)

    async def _initialize_translator(self):
        """번역기 초기화"""
        if not self.selected_modpack:
            raise ValueError("모드팩이 선택되지 않았습니다")

        if self.log_callback:
            self.log_callback("INFO", "ModpackTranslator 초기화를 시작합니다")

        # 경로 유효성 검사
        if not os.path.exists(self.selected_modpack["path"]):
            raise FileNotFoundError(
                f"모드팩 경로를 찾을 수 없습니다: {self.selected_modpack['path']}"
            )

        # 설정 로그
        if self.log_callback:
            self.log_callback("INFO", f"제공업체: {self.settings['llm_provider']}")
            self.log_callback("INFO", f"모델: {self.settings['llm_model']}")
            self.log_callback("INFO", f"Temperature: {self.settings['temperature']}")
            self.log_callback(
                "INFO", f"동시 요청 수: {self.settings['max_concurrent_requests']}"
            )

        # 번역기 인스턴스 생성
        self.translator = ModpackTranslator(
            modpack_path=self.selected_modpack["path"],
            glossary_path="./glossary.json",
            max_concurrent_requests=self.settings["max_concurrent_requests"],
            delay_between_requests_ms=self.settings["delay_between_requests_ms"],
            progress_callback=self.progress_callback,  # 진행률 콜백 전달
        )

        # 토큰 실시간 업데이트 콜백 연결
        try:
            if (
                self.token_update_callback
                and hasattr(self.translator, "translator")
                and hasattr(self.translator.translator, "token_counter")
            ):
                self.translator.translator.token_counter.update_callback = (
                    self.token_update_callback
                )
        except Exception as cb_err:
            if self.log_callback:
                self.log_callback("WARNING", f"토큰 콜백 연결 실패: {cb_err}")

        if self.log_callback:
            self.log_callback("SUCCESS", "ModpackTranslator 초기화 완료")

    async def _run_translation(
        self,
        selected_files: Optional[List[str]] = None,
        selected_glossary_files: Optional[List[str]] = None,
    ):
        """실제 번역 작업 실행"""
        # 출력 디렉토리 설정 (현재 실행 위치의 output 폴더에 저장)
        modpack_name = Path(self.selected_modpack["path"]).name
        output_dir = os.path.join(".", "output", f"{modpack_name}_korean")

        # output 디렉토리가 없으면 생성
        os.makedirs(output_dir, exist_ok=True)

        if self.log_callback:
            self.log_callback("INFO", f"출력 디렉토리: {os.path.abspath(output_dir)}")

        # 번역 태스크 생성
        self.translation_task = asyncio.create_task(
            self._execute_translation(
                output_dir, selected_files, selected_glossary_files
            )
        )

        try:
            # 번역 실행 및 결과 대기
            result = await self.translation_task

            if self.log_callback:
                self.log_callback("SUCCESS", f"번역 완료! {len(result)}개 항목 번역됨")

            # 토큰 사용량 추출 및 UI 업데이트
            if (
                hasattr(self.translator, "json_translator")
                and self.translator.json_translator
            ):
                token_usage = self.translator.json_translator.get_token_summary()
                if self.token_update_callback:
                    self.token_update_callback(token_usage)

                # 토큰 사용량 로그 출력
                if self.log_callback and token_usage:
                    formatted_summary = (
                        self.translator.json_translator.get_formatted_token_summary()
                    )
                    self.log_callback("INFO", f"토큰 사용량 요약:\n{formatted_summary}")

            if self.progress_callback:
                self.progress_callback(
                    "번역 완료", 1, 1, "모든 번역 작업이 완료되었습니다"
                )

            # 완료 콜백 호출
            if self.completion_callback:
                self.completion_callback(output_dir, len(result))

        except asyncio.CancelledError:
            if self.log_callback:
                self.log_callback("WARNING", "번역이 사용자에 의해 중지되었습니다")
            if self.progress_callback:
                self.progress_callback("중지됨", 0, 0, "번역이 중지되었습니다")
        except Exception as error:
            if self.log_callback:
                self.log_callback("ERROR", f"번역 실행 중 오류: {error}")
            if self.progress_callback:
                self.progress_callback("오류 발생", 0, 0, str(error))
            raise

    async def _execute_translation(
        self,
        output_dir: str,
        selected_files: Optional[List[str]] = None,
        selected_glossary_files: Optional[List[str]] = None,
    ):
        """번역 실행"""
        return await self.translator.run_full_translation(
            output_path=os.path.join(output_dir, "modpack_translation.json"),
            max_tokens_per_chunk=self.settings["max_tokens_per_chunk"],
            max_retries=self.settings["max_retries"],
            use_glossary=self.settings["use_glossary"],
            apply_to_files=True,
            output_dir=output_dir,
            backup_originals=self.settings["create_backup"],
            enable_packaging=self.settings["enable_packaging"],
            max_concurrent_requests=self.settings["max_concurrent_requests"],
            delay_between_requests_ms=self.settings["delay_between_requests_ms"],
            llm_provider=self.settings["llm_provider"],
            llm_model=self.settings["llm_model"],
            temperature=self.settings["temperature"],
            enable_quality_review=self.settings["enable_quality_review"],
            final_fallback_max_retries=self.settings["final_fallback_max_retries"],
            max_quality_retries=self.settings["max_quality_retries"],
            selected_files=selected_files,
            selected_glossary_files=selected_glossary_files,
        )

    def stop_translation(self):
        """번역 중지"""
        if not self.is_translating:
            if self.log_callback:
                self.log_callback("WARNING", "진행 중인 번역이 없습니다")
            return

        if self.log_callback:
            self.log_callback("INFO", "번역 중지 요청...")

        # Flet의 run_task를 사용하여 비동기 작업 실행
        self.page.run_task(self._stop_translation_async)

    async def _stop_translation_async(self):
        """실제 번역 중지 로직 (비동기)"""
        if not self.is_translating:
            return

        if self.translation_task:
            self.translation_task.cancel()

        self.is_translating = False

        if self.log_callback:
            self.log_callback("INFO", "번역이 중지되었습니다")

        if self.ui_update_callback:
            self.ui_update_callback(False)

        if self.progress_callback:
            self.progress_callback("중지됨", 0, 0, "번역이 중지되었습니다")

    def get_translation_status(self) -> Dict:
        """번역 상태 정보 반환"""
        return {
            "is_translating": self.is_translating,
            "has_modpack": self.selected_modpack is not None,
            "modpack_name": self.selected_modpack.get("name", "Unknown")
            if self.selected_modpack
            else None,
            "modpack_path": self.selected_modpack.get("path", "")
            if self.selected_modpack
            else None,
            "settings": self.settings.copy(),
        }

    def validate_settings(self) -> tuple[bool, str]:
        """설정값 유효성 검사"""
        if not self.selected_modpack:
            return False, "모드팩이 선택되지 않았습니다"

        if not os.path.exists(self.selected_modpack["path"]):
            return (
                False,
                f"모드팩 경로가 존재하지 않습니다: {self.selected_modpack['path']}",
            )

        if self.settings["max_tokens_per_chunk"] < 100:
            return False, "청크당 최대 토큰은 100 이상이어야 합니다"

        if self.settings["max_concurrent_requests"] < 1:
            return False, "동시 요청 수는 1 이상이어야 합니다"

        if self.settings["delay_between_requests_ms"] < 0:
            return False, "요청 간 지연은 0 이상이어야 합니다"

        if not (0.0 <= self.settings["temperature"] <= 1.0):
            return False, "Temperature는 0.0과 1.0 사이여야 합니다"

        if self.settings["max_retries"] < 0:
            return False, "최대 재시도 횟수는 0 이상이어야 합니다"

        return True, "설정이 유효합니다"

    def get_estimated_cost(self) -> Dict:
        """예상 비용 계산 (간단한 추정)"""
        if not self.selected_modpack:
            return {"error": "모드팩이 선택되지 않았습니다"}

        # 간단한 추정 로직 (실제로는 더 복잡해야 함)
        estimated_tokens = 10000  # 기본 추정값
        model = self.settings["model"]

        # 모델별 토큰 당 비용 (USD, 2024년 기준 추정)
        token_costs = {
            "gpt-4o-mini": 0.00015 / 1000,  # $0.15 per 1M tokens
            "gpt-4o": 0.005 / 1000,  # $5 per 1M tokens
            "gpt-4-turbo": 0.01 / 1000,  # $10 per 1M tokens
            "gpt-3.5-turbo": 0.0015 / 1000,  # $1.5 per 1M tokens
        }

        cost_per_token = token_costs.get(model, 0.001 / 1000)
        estimated_cost = estimated_tokens * cost_per_token

        return {
            "model": model,
            "estimated_tokens": estimated_tokens,
            "estimated_cost_usd": round(estimated_cost, 4),
            "estimated_cost_krw": round(estimated_cost * 1300, 0),  # 환율 1300원 가정
            "note": "이는 대략적인 추정값입니다",
        }

    def reset_controller(self):
        """컨트롤러 초기화"""
        if self.is_translating:
            self.stop_translation()

        self.selected_modpack = None
        self.translator = None
        self.translation_task = None

        if self.log_callback:
            self.log_callback("INFO", "번역 컨트롤러가 초기화되었습니다")
