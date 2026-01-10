"""
다중 API 키 관리 다이얼로그 모듈

여러 API 키를 추가, 제거, 테스트하고 상태를 모니터링할 수 있는 GUI 컴포넌트
"""

import logging
from typing import Callable, Optional

import flet as ft

from src.localization import tr
from src.translators.llm_manager import LLMManager
from src.translators.multi_llm_manager import MultiLLMManager

logger = logging.getLogger(__name__)


class MultiAPIKeysDialog:
    """다중 API 키 관리 다이얼로그"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.multi_llm_manager = MultiLLMManager()
        self.llm_manager = LLMManager()
        self.dialog = None
        self.keys_container = None
        self.refresh_callback = None

        # 임시 입력 필드들
        self.key_name_field = None
        self.key_provider_dropdown = None
        self.key_model_dropdown = None
        self.key_value_field = None

    def create_dialog(
        self, refresh_callback: Optional[Callable] = None
    ) -> ft.AlertDialog:
        """다중 API 키 관리 다이얼로그 생성"""
        self.refresh_callback = refresh_callback

        # 키 목록 컨테이너
        self.keys_container = ft.Column(
            controls=[], spacing=10, scroll=ft.ScrollMode.AUTO, height=400
        )

        # 새 키 추가 입력 필드들
        self.key_name_field = ft.TextField(
            label=tr("gui.label.key_name", "키 이름"),
            hint_text="예: gemini-key-1",
            width=200,
        )

        self.key_provider_dropdown = ft.Dropdown(
            label=tr("gui.label.key_provider", "제공업체"),
            options=[
                ft.dropdown.Option("openai", "OpenAI"),
                ft.dropdown.Option("gemini", "Google Gemini"),
                ft.dropdown.Option("claude", "Anthropic Claude"),
                ft.dropdown.Option("deepseek", "DeepSeek"),
                ft.dropdown.Option("grok", "Grok"),
                ft.dropdown.Option("ollama", "Ollama"),
            ],
            value="gemini",
            width=200,
            on_change=self._on_provider_change,
        )

        self.key_model_dropdown = ft.Dropdown(
            label=tr("gui.label.key_model", "모델"), options=[], width=200
        )

        self.key_value_field = ft.TextField(
            label=tr("gui.label.key_value", "API 키 값"),
            password=True,
            can_reveal_password=True,
            width=400,
        )

        # 초기 모델 목록 로드
        self.page.run_task(self._load_models_for_provider, "gemini")

        # 새 키 추가 섹션
        add_key_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        tr("gui.button.add_api_key", "API 키 추가"),
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Row(
                        [
                            self.key_name_field,
                            self.key_provider_dropdown,
                            self.key_model_dropdown,
                        ],
                        spacing=10,
                    ),
                    ft.Row(
                        [
                            self.key_value_field,
                            ft.ElevatedButton(
                                text=tr("gui.button.add_api_key", "추가"),
                                icon=ft.Icons.ADD,
                                on_click=self._add_api_key,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Divider(),
                ],
                spacing=10,
            ),
            padding=10,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )

        # 기존 키 목록 섹션
        keys_section = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                tr("gui.dialog.multi_api_keys", "다중 API 키 관리"),
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="새로고침",
                                on_click=self._refresh_keys_list,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self.keys_container,
                ],
                spacing=10,
            ),
            padding=10,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )

        # 도움말 텍스트
        help_text = ft.Text(
            tr(
                "gui.text.multi_api_keys_help",
                "💡 팁: 여러 API 키를 등록하면 할당량 제한 시 자동으로 다른 키로 전환됩니다.",
            ),
            size=12,
            color=ft.Colors.BLUE_GREY,
        )

        # 상태 표시 레이블 (키 테스트 결과 표시용)
        self.test_status_label = ft.Text("", size=12, color=ft.Colors.GREEN)

        # 다이얼로그 생성
        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(tr("gui.dialog.multi_api_keys", "다중 API 키 관리")),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            tr(
                                "gui.dialog.multi_api_keys_subtitle",
                                "여러 API 키를 등록하여 할당량 제한을 우회하고 번역 속도를 향상시킬 수 있습니다.",
                            )
                        ),
                        help_text,
                        ft.Divider(),
                        add_key_section,
                        self.test_status_label,
                        keys_section,
                        # 키 테스트 상태 표시
                    ],
                    spacing=15,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=700,
                height=700,
            ),
            actions=[
                ft.TextButton(
                    text=tr("gui.button.cancel", "닫기"), on_click=self._close_dialog
                )
            ],
        )

        # 기존 키 목록 로드
        self._refresh_keys_list()

        return self.dialog

    def _on_provider_change(self, e):
        """제공업체 변경 시 모델 목록 업데이트"""
        provider = e.control.value
        self.page.run_task(self._load_models_for_provider, provider)

    async def _load_models_for_provider(self, provider: str):
        """제공업체의 모델 목록 로드"""
        try:
            # TextField에 입력된 임시 API 키로 환경변수 설정 (모델 목록 조회용)
            api_key = self.key_value_field.value.strip()
            if api_key:
                self.llm_manager.set_api_key(provider, api_key)

            models = await self.llm_manager.get_available_models(provider)

            # 모델 드롭다운 업데이트
            self.key_model_dropdown.options = [
                ft.dropdown.Option(model["id"], model["name"]) for model in models
            ]

            # 첫 번째 모델 선택
            if models:
                self.key_model_dropdown.value = models[0]["id"]

            # 드롭다운이 페이지에 추가되어 있는지 확인 후 업데이트
            if self.key_model_dropdown.page is not None:
                self.key_model_dropdown.update()

        except Exception as e:
            logger.error(f"모델 목록 로드 실패: {e}")
            self.key_model_dropdown.options = []
            # 드롭다운이 페이지에 추가되어 있는지 확인 후 업데이트
            if self.key_model_dropdown.page is not None:
                self.key_model_dropdown.update()

    def _add_api_key(self, e):
        """새 API 키 추가"""
        try:
            key_name = self.key_name_field.value.strip()
            provider = self.key_provider_dropdown.value
            model = self.key_model_dropdown.value
            api_key = self.key_value_field.value.strip()

            # 유효성 검사
            if not key_name:
                self._show_error(
                    tr("gui.error.key_name_required", "키 이름을 입력해주세요.")
                )
                return

            if not api_key:
                self._show_error(
                    tr("gui.error.key_value_required", "API 키 값을 입력해주세요.")
                )
                return

            # 중복 키 이름 확인
            if key_name in self.multi_llm_manager.get_api_keys():
                self._show_error(
                    tr("gui.error.key_already_exists", "이미 존재하는 키 이름입니다.")
                )
                return

            # API 키 추가
            self.multi_llm_manager.add_api_key(key_name, provider, model, api_key)

            # 입력 필드 초기화
            self.key_name_field.value = ""
            self.key_value_field.value = ""

            # 키 목록 새로고침
            self._refresh_keys_list()

            # 성공 메시지
            self._show_success(tr("gui.message.key_added", "API 키가 추가되었습니다."))

            # 페이지 업데이트
            self.page.update()

        except Exception as ex:
            logger.error(f"API 키 추가 실패: {ex}")
            self._show_error(f"API 키 추가 실패: {ex}")

    def _remove_api_key(self, key_id: str):
        """API 키 제거"""
        try:
            self.multi_llm_manager.remove_api_key(key_id)
            self._refresh_keys_list()
            self._show_success(
                tr("gui.message.key_removed", "API 키가 제거되었습니다.")
            )
        except Exception as ex:
            logger.error(f"API 키 제거 실패: {ex}")
            self._show_error(f"API 키 제거 실패: {ex}")

    def _test_api_key(self, key_id: str):
        """API 키 테스트"""
        # Debug log to confirm test trigger
        print(f"DEBUG: _test_api_key called for {key_id}")
        self.page.run_task(self._test_api_key_async, key_id)

    async def _test_api_key_async(self, key_id: str):
        """API 키 비동기 테스트"""
        # Debug log to confirm async test start
        print(f"DEBUG: _test_api_key_async starting for {key_id}")
        # 키 테스트 수행
        try:
            client = await self.multi_llm_manager.get_client(key_id)
            if client:
                # 실제 API 호출을 통해 키 유효성 검사
                try:
                    # 간단한 테스트 요청 (ping)
                    await client.ainvoke("ping")
                    msg = tr("gui.message.key_test_success", "API 키 테스트 성공")
                    self.test_status_label.value = msg
                    self.test_status_label.color = ft.Colors.GREEN
                except Exception as call_ex:
                    logger.error(f"API 키 테스트 호출 오류: {call_ex}")
                    msg = tr(
                        "gui.message.key_test_failed",
                        "API 키 테스트 실패",
                        error=str(call_ex),
                    )
                    self.test_status_label.value = msg
                    self.test_status_label.color = ft.Colors.RED
            else:
                msg = tr("gui.message.key_test_failed", "API 키 테스트 실패")
                self.test_status_label.value = msg
                self.test_status_label.color = ft.Colors.RED
        except Exception as ex:
            logger.error(f"API 키 테스트 실패: {ex}")
            msg = tr("gui.message.key_test_failed", error=str(ex))
            self.test_status_label.value = msg
            self.test_status_label.color = ft.Colors.RED
        # 결과 표시 및 리스트 갱신
        self._refresh_keys_list()
        self.test_status_label.update()
        self.page.update()

    def _reset_key_failures(self, key_id: str):
        """API 키 실패 카운트 리셋"""
        try:
            self.multi_llm_manager.reset_key_failures(key_id)
            self._refresh_keys_list()
            self._show_success(
                tr("gui.message.failures_reset", "실패 카운트가 초기화되었습니다.")
            )
        except Exception as ex:
            logger.error(f"실패 카운트 리셋 실패: {ex}")
            self._show_error(f"실패 카운트 리셋 실패: {ex}")

    def _refresh_keys_list(self, e=None):
        """키 목록 새로고침"""
        try:
            api_keys = self.multi_llm_manager.get_api_keys()
            self.keys_container.controls.clear()

            if not api_keys:
                self.keys_container.controls.append(
                    ft.Text("등록된 API 키가 없습니다.", size=14, color=ft.Colors.GREY)
                )
            else:
                for key_id, key_info in api_keys.items():
                    key_card = self._create_key_card(key_id, key_info)
                    self.keys_container.controls.append(key_card)

            self.page.update()

        except Exception as ex:
            logger.error(f"키 목록 새로고침 실패: {ex}")

    def _create_key_card(self, key_id: str, key_info):
        """API 키 카드 생성"""
        # 상태 표시
        status_color = ft.Colors.GREEN if key_info.is_active else ft.Colors.RED
        status_text = (
            tr("gui.status.key_active", "활성")
            if key_info.is_active
            else tr("gui.status.key_inactive", "비활성")
        )

        if key_info.failed_count >= 5:
            status_color = ft.Colors.RED
            status_text = tr("gui.status.key_failed", "실패")

        # 키 정보 표시
        key_info_text = f"{key_info.provider}/{key_info.model}"
        usage_text = f"사용: {key_info.usage_count}회"
        failures_text = f"실패: {key_info.failed_count}회"

        return ft.Container(
            content=ft.Row(
                [
                    # 키 정보
                    ft.Column(
                        [
                            ft.Text(key_id, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(key_info_text, size=12, color=ft.Colors.GREY),
                            ft.Text(
                                f"키: {key_info.key[:10]}...",
                                size=10,
                                color=ft.Colors.GREY,
                            ),
                        ],
                        spacing=2,
                    ),
                    # 상태 및 통계
                    ft.Column(
                        [
                            ft.Container(
                                content=ft.Text(
                                    status_text, size=12, color=ft.Colors.WHITE
                                ),
                                bgcolor=status_color,
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=12,
                            ),
                            ft.Text(usage_text, size=10, color=ft.Colors.GREY),
                            ft.Text(failures_text, size=10, color=ft.Colors.GREY),
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    # 액션 버튼들
                    ft.Column(
                        [
                            ft.IconButton(
                                icon=ft.Icons.PLAY_ARROW,
                                tooltip=tr("gui.button.test_api_key", "키 테스트"),
                                on_click=lambda e: self._test_api_key(key_id),
                                icon_size=16,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip=tr("gui.button.reset_failures", "실패 초기화"),
                                on_click=lambda e: self._reset_key_failures(key_id),
                                icon_size=16,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                tooltip=tr("gui.button.remove_api_key", "키 제거"),
                                on_click=lambda e: self._remove_api_key(key_id),
                                icon_color=ft.Colors.RED,
                                icon_size=16,
                            ),
                        ],
                        spacing=0,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=10,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )

    def _show_error(self, message: str):
        """에러 메시지 표시"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message), bgcolor=ft.Colors.ERROR
        )
        self.page.snack_bar.open = True
        self.page.update()

    def _show_success(self, message: str):
        """성공 메시지 표시"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message), bgcolor=ft.Colors.GREEN
        )
        self.page.snack_bar.open = True
        self.page.update()

    def _close_dialog(self, e):
        """다이얼로그 닫기"""
        self.dialog.open = False
        self.page.update()

        # 콜백 호출 (메인 UI 새로고침)
        if self.refresh_callback:
            self.refresh_callback()

    def get_multi_llm_manager(self) -> MultiLLMManager:
        """MultiLLMManager 인스턴스 반환"""
        return self.multi_llm_manager
