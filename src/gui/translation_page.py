"""
번역 진행 페이지 GUI (모듈화된 버전)
"""

import logging
from typing import Callable, Dict

import flet as ft

from .translation_controller import TranslationController
from .translation_dialogs import (
    TranslationCompletionDialog,
)
from .translation_logger import TranslationLogger
from .translation_progress import TranslationProgressManager
from .translation_ui_builders import TranslationUIBuilders

logger = logging.getLogger(__name__)


class TranslationPage:
    """번역 페이지 메인 클래스 (모듈화된 버전)"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.selected_modpack = None
        self.current_language = "ko"

        # 모듈들 초기화
        self.controller = TranslationController(page)
        self.logger = TranslationLogger(page)
        self.progress_manager = TranslationProgressManager(
            page, self.logger.add_log_message
        )
        self.ui_builders = TranslationUIBuilders(page)
        self.completion_dialog = TranslationCompletionDialog(
            page, self.logger.add_log_message
        )

        # UI 컴포넌트들
        self.start_button = None
        self.stop_button = None
        self.status_text = None

        # 콜백
        self.on_back_to_browser = None

        # 컨트롤러에 콜백 설정
        self._setup_controller_callbacks()

    def set_modpack(self, modpack_info: Dict):
        """선택된 모드팩 설정"""
        self.selected_modpack = modpack_info
        self.controller.set_modpack(modpack_info)
        logger.info(f"번역 대상 모드팩 설정: {modpack_info.get('name', 'Unknown')}")

    def set_back_callback(self, callback: Callable):
        """뒤로가기 콜백 설정"""
        self.on_back_to_browser = callback

    def _setup_controller_callbacks(self):
        """컨트롤러 콜백들 설정"""
        self.controller.set_callbacks(
            progress_callback=self.progress_manager.update_progress,
            completion_callback=self.completion_dialog.show_completion_dialog,
            log_callback=self.logger.add_log_message,
            ui_update_callback=self._update_ui_state,
            token_update_callback=self.progress_manager.update_token_usage,
        )

    def build_ui(self):
        """번역 페이지 UI 구성"""
        if not self.selected_modpack:
            return

        # 페이지 정리
        self.page.clean()

        # 헤더 구성
        header = self.ui_builders.build_header(
            self.selected_modpack, self._on_back_clicked
        )

        # 설정 패널 구성
        settings_panel = self.ui_builders.build_settings_panel(
            self.controller.get_settings(), self.controller.update_setting
        )

        # 진행률 패널 구성
        (
            progress_container,
            main_progress_bar,
            progress_text,
            progress_detail,
            status_info,
        ) = self.ui_builders.build_progress_panel()

        # 토큰 사용량 표시 패널 구성
        token_usage_panel = self.ui_builders.build_token_usage_panel()

        # 진행률 매니저에 UI 컴포넌트 연결 (토큰 사용량 표시 포함)
        self.progress_manager.set_ui_components(
            main_progress_bar,
            progress_text,
            progress_detail,
            status_info,
            token_usage_panel,
        )

        # 로그 패널 구성
        log_panel, log_container = self.ui_builders.build_log_panel(
            self._clear_logs, self._save_logs
        )

        # 로거에 로그 컨테이너 연결
        self.logger.set_log_container(log_container)

        # 컨트롤 패널 구성
        control_panel, start_button, stop_button, status_text = (
            self.ui_builders.build_control_panel(
                self._start_translation,
                self._stop_translation,
                self.controller.is_translating,
            )
        )

        # 컨트롤 버튼들 저장
        self.start_button = start_button
        self.stop_button = stop_button
        self.status_text = status_text

        # 메인 레이아웃 구성 (토큰 사용량 패널 추가)
        main_layout = self.ui_builders.build_main_layout(
            header,
            settings_panel,
            progress_container,
            token_usage_panel,
            log_panel,
            control_panel,
        )

        # 페이지에 추가
        self.page.add(main_layout)
        self.page.update()

        # 초기 로그 및 GUI 로그 핸들러 설정
        self.logger.add_initial_logs(self.selected_modpack.get("name", "Unknown"))
        self.logger.setup_gui_log_handler()

    def _start_translation(self, e):
        """번역 시작"""
        # 설정 유효성 검사
        is_valid, message = self.controller.validate_settings()
        if not is_valid:
            self.logger.add_log_message("ERROR", f"설정 오류: {message}")
            return

        self.logger.add_log_message("INFO", "번역 시작...")
        self.progress_manager.start_translation()
        self.progress_manager.start_time_tracker(lambda: self.controller.is_translating)

        # 컨트롤러에서 번역 시작
        self.controller.start_translation()

    def _stop_translation(self, e):
        """번역 중지"""
        if not self.controller.is_translating:
            self.logger.add_log_message("WARNING", "진행 중인 번역이 없습니다")
            return

        self.logger.add_log_message("INFO", "번역 중지 요청...")
        self.controller.stop_translation()

    def _update_ui_state(self, is_translating: bool):
        """UI 상태 업데이트"""
        if self.start_button and self.stop_button and self.status_text:
            self.ui_builders.update_control_buttons_state(
                self.start_button, self.stop_button, self.status_text, is_translating
            )

    def _clear_logs(self, e):
        """로그 지우기"""
        self.logger.clear_logs()

    def _save_logs(self, e):
        """로그 저장"""
        modpack_name = (
            self.selected_modpack.get("name", "Unknown")
            if self.selected_modpack
            else "Unknown"
        )
        self.logger.save_logs(modpack_name)

    def _on_back_clicked(self, e):
        """뒤로가기 버튼 클릭"""
        if self.controller.is_translating:
            # 번역 중이면 확인 다이얼로그 표시
            self.ui_builders.show_confirmation_dialog(
                "번역 진행 중",
                "번역이 진행 중입니다. 정말로 나가시겠습니까?",
                self._force_back,
                None,
            )
        else:
            # 번역 중이 아니면 바로 돌아가기
            if self.on_back_to_browser:
                self.page.run_task(self._back_to_browser_async)

    def _force_back(self):
        """강제로 뒤로가기 (번역 중지하고)"""
        self.controller.stop_translation()
        if self.on_back_to_browser:
            self.page.run_task(self._back_to_browser_async)

    async def _back_to_browser_async(self):
        """브라우저로 돌아가기 - 비동기"""
        # 정리 작업
        self.logger.cleanup_log_handler()
        self.progress_manager.reset_progress()
        self.controller.reset_controller()

        if self.on_back_to_browser:
            await self.on_back_to_browser()

    def get_translation_status(self) -> Dict:
        """번역 상태 정보 반환"""
        controller_status = self.controller.get_translation_status()
        log_summary = self.logger.get_log_summary()

        return {
            **controller_status,
            "log_summary": log_summary,
        }

    def get_estimated_cost(self) -> Dict:
        """예상 비용 반환"""
        return self.controller.get_estimated_cost()

    def cleanup(self):
        """페이지 정리"""
        try:
            if self.controller.is_translating:
                self.controller.stop_translation()

            self.logger.cleanup_log_handler()
            self.progress_manager.reset_progress()
            self.controller.reset_controller()

            logger.info("번역 페이지 정리 완료")
        except Exception as e:
            logger.error(f"페이지 정리 중 오류: {e}")

    def __del__(self):
        """소멸자"""
        try:
            self.cleanup()
        except:
            pass  # 소멸자에서는 예외를 무시
