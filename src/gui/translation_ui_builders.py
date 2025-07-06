"""
번역 페이지 UI 컴포넌트 빌더들
"""

import json
from pathlib import Path
from typing import Callable, Dict

import flet as ft

from src.localization import tr
from src.translators.llm_manager import LLMManager
from src.utils.env_manager import EnvManager

from .components import create_setting_row


class TranslationUIBuilders:
    """번역 페이지 UI 빌더 클래스"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.llm_manager = LLMManager()
        self.env_manager = EnvManager()

        # 모델 관련 상태
        self.available_models = {}
        self.current_provider = None
        self.current_model = None

        # 용어집 경로
        self.glossary_path = Path("./glossary.json")

    def build_header(self, modpack_info: Dict, on_back_callback: Callable):
        """헤더 구성"""
        return ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip=tr(
                        "gui.tooltip.back_browser", "모드팩 브라우저로 돌아가기"
                    ),
                    on_click=on_back_callback,
                ),
                ft.Text(
                    f"{tr('gui.header.translation_progress', '번역 진행')} - {modpack_info.get('name', 'Unknown')}",
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Text(
                        f"{tr('gui.label.path', '경로')}: {modpack_info.get('path', 'Unknown')}",
                        size=12,
                        color=ft.Colors.GREY_600,
                    ),
                ),
            ],
            spacing=10,
        )

    def build_settings_panel(self, settings: Dict, update_setting_callback: Callable):
        """설정 패널 구성"""

        # 제공업체 선택 드롭다운
        provider_options = []
        for provider_id in self.llm_manager.get_available_providers():
            provider_info = self.llm_manager.get_provider_info(provider_id)
            provider_options.append(
                ft.dropdown.Option(provider_id, provider_info.get("name", provider_id))
            )

        provider_dropdown = ft.Dropdown(
            label=tr("gui.label.llm_provider", "LLM 제공업체"),
            options=provider_options,
            value=settings.get("llm_provider", "gemini"),
            on_change=lambda e: self._on_provider_change(e, update_setting_callback),
            expand=True,
        )

        # 모델 선택 드롭다운 (처음에는 비어있음)
        model_dropdown = ft.Dropdown(
            label=tr("gui.label.llm_model", "번역 모델"),
            options=[],
            value=settings.get("llm_model", ""),
            on_change=lambda e: update_setting_callback("llm_model", e.control.value),
            expand=True,
        )

        # API 키 입력 필드
        api_key_field = ft.TextField(
            label=tr("gui.label.api_key", "API 키"),
            password=True,
            can_reveal_password=True,
            value=self._get_current_api_key(settings.get("llm_provider", "gemini")),
            on_change=lambda e: self._on_api_key_change(
                e, settings.get("llm_provider", "gemini")
            ),
            expand=True,
        )

        # 모델 새로고침 버튼
        refresh_models_button = ft.ElevatedButton(
            text=tr("gui.button.refresh_models", "모델 목록 새로고침"),
            icon=ft.Icons.REFRESH,
            on_click=lambda e: self._refresh_models(
                provider_dropdown.value, model_dropdown
            ),
            expand=True,
        )

        # 초기 모델 로드
        self.page.run_task(
            self._load_initial_models, provider_dropdown.value, model_dropdown
        )

        # 상태 저장 (나중에 참조용)
        self.provider_dropdown = provider_dropdown
        self.model_dropdown = model_dropdown
        self.api_key_field = api_key_field

        # 슬라이더 값 표시를 위한 Text 위젯들
        temperature_text = ft.Text(
            f"{settings['temperature']:.1f}", size=12, color=ft.Colors.BLUE
        )
        max_tokens_text = ft.Text(
            f"{settings['max_tokens_per_chunk']}", size=12, color=ft.Colors.BLUE
        )
        concurrent_text = ft.Text(
            f"{settings['max_concurrent_requests']}", size=12, color=ft.Colors.BLUE
        )
        delay_text = ft.Text(
            f"{settings['delay_between_requests_ms']}ms", size=12, color=ft.Colors.BLUE
        )
        retries_text = ft.Text(
            f"{settings['max_retries']}", size=12, color=ft.Colors.BLUE
        )

        final_fallback_text = ft.Text(
            f"{settings['final_fallback_max_retries']}", size=12, color=ft.Colors.BLUE
        )

        quality_retries_text = ft.Text(
            f"{settings['max_quality_retries']}", size=12, color=ft.Colors.BLUE
        )

        temperature_slider = ft.Slider(
            min=0.0,
            max=1.0,
            value=settings["temperature"],
            divisions=10,
            on_change=lambda e: self._update_temperature(
                e, update_setting_callback, temperature_text
            ),
            expand=True,
        )

        max_tokens_slider = ft.Slider(
            min=1000,
            max=4000,
            value=settings["max_tokens_per_chunk"],
            divisions=6,
            on_change=lambda e: self._update_max_tokens(
                e, update_setting_callback, max_tokens_text
            ),
            expand=True,
        )

        concurrent_requests_slider = ft.Slider(
            min=1,
            max=100,
            value=settings["max_concurrent_requests"],
            divisions=99,
            on_change=lambda e: self._update_concurrent(
                e, update_setting_callback, concurrent_text
            ),
            expand=True,
        )

        delay_slider = ft.Slider(
            min=100,
            max=2000,
            value=settings["delay_between_requests_ms"],
            divisions=19,
            on_change=lambda e: self._update_delay(
                e, update_setting_callback, delay_text
            ),
            expand=True,
        )

        max_retries_slider = ft.Slider(
            min=0,
            max=10,
            value=settings["max_retries"],
            divisions=10,
            on_change=lambda e: self._update_retries(
                e, update_setting_callback, retries_text
            ),
            expand=True,
        )

        final_fallback_slider = ft.Slider(
            min=0,
            max=10,
            value=settings["final_fallback_max_retries"],
            divisions=10,
            on_change=lambda e: (
                update_setting_callback(
                    "final_fallback_max_retries", int(e.control.value)
                ),
                setattr(final_fallback_text, "value", f"{int(e.control.value)}"),
                self.page.update(),
            ),
            expand=True,
        )

        quality_retries_slider = ft.Slider(
            min=0,
            max=10,
            value=settings["max_quality_retries"],
            divisions=10,
            on_change=lambda e: (
                update_setting_callback("max_quality_retries", int(e.control.value)),
                setattr(quality_retries_text, "value", f"{int(e.control.value)}"),
                self.page.update(),
            ),
            expand=True,
        )

        # 체크박스들
        checkboxes = ft.Column(
            [
                ft.Checkbox(
                    label=tr("gui.checkbox.use_glossary", "용어집 사용"),
                    value=settings["use_glossary"],
                    on_change=lambda e: update_setting_callback(
                        "use_glossary", e.control.value
                    ),
                ),
                ft.Checkbox(
                    label=tr("gui.checkbox.create_backup", "원본 파일 백업"),
                    value=settings["create_backup"],
                    on_change=lambda e: update_setting_callback(
                        "create_backup", e.control.value
                    ),
                ),
                ft.Checkbox(
                    label=tr("gui.checkbox.enable_packaging", "패키징 활성화"),
                    value=settings["enable_packaging"],
                    on_change=lambda e: update_setting_callback(
                        "enable_packaging", e.control.value
                    ),
                ),
                ft.Checkbox(
                    label=tr("gui.checkbox.enable_quality_review", "품질 검토 활성화"),
                    value=settings["enable_quality_review"],
                    on_change=lambda e: update_setting_callback(
                        "enable_quality_review", e.control.value
                    ),
                ),
            ],
            spacing=8,
        )

        # ------------------------------------------------------------------
        # Glossary info
        # ------------------------------------------------------------------
        glossary_count = self._get_glossary_word_count()
        glossary_count_text = ft.Text(
            f"{tr('gui.glossary.count', '단어 수')}: {glossary_count}", size=12
        )
        glossary_reset_button = ft.TextButton(
            tr("gui.button.reset_glossary", "사전 초기화"),
            icon=ft.Icons.DELETE_FOREVER,
            on_click=lambda e: self._reset_glossary(glossary_count_text),
        )

        glossary_row = ft.Row(
            [
                glossary_count_text,
                glossary_reset_button,
            ]
        )

        # ------------------------------------------------------------------
        # Recommendations message
        # ------------------------------------------------------------------
        recommendation_text = ft.Text(
            tr(
                "gui.message.recommended_settings",
                "추천 설정 → Temperature 0.1~0.3, 동시 요청 3~5, 최대 토큰 2000~3000",
            ),
            size=11,
            color=ft.Colors.GREY_600,
        )

        settings_content = ft.Column(
            [
                ft.Text(
                    tr("gui.text.translation_settings", "번역 설정"),
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=10),
                create_setting_row(
                    tr("gui.label.provider", "제공업체"), provider_dropdown
                ),
                create_setting_row(tr("gui.label.model", "모델"), model_dropdown),
                create_setting_row(tr("gui.label.api_key", "API 키"), api_key_field),
                create_setting_row(
                    tr("gui.button.refresh_models", "모델 새로고침"),
                    refresh_models_button,
                ),
                ft.Container(height=10),
                self._create_slider_row(
                    tr("gui.slider.temperature", "창의성 (Temperature)"),
                    temperature_slider,
                    temperature_text,
                ),
                self._create_slider_row(
                    tr("gui.slider.max_tokens", "청크당 최대 토큰"),
                    max_tokens_slider,
                    max_tokens_text,
                ),
                self._create_slider_row(
                    tr("gui.slider.concurrent_requests", "동시 요청 수"),
                    concurrent_requests_slider,
                    concurrent_text,
                ),
                self._create_slider_row(
                    tr("gui.slider.delay_between_requests", "요청 간 지연"),
                    delay_slider,
                    delay_text,
                ),
                self._create_slider_row(
                    tr("gui.slider.max_retries", "최대 재시도 횟수"),
                    max_retries_slider,
                    retries_text,
                ),
                self._create_slider_row(
                    tr("gui.slider.final_fallback_max_retries", "최종 대체 재시도"),
                    final_fallback_slider,
                    final_fallback_text,
                ),
                self._create_slider_row(
                    tr("gui.slider.max_quality_retries", "품질 검토 재시도"),
                    quality_retries_slider,
                    quality_retries_text,
                ),
                ft.Container(height=10),
                ft.Text(
                    tr("gui.text.additional_options", "추가 옵션"),
                    size=16,
                    weight=ft.FontWeight.BOLD,
                ),
                checkboxes,
                ft.Divider(),
                glossary_row,
                recommendation_text,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        )

        return ft.Card(
            content=ft.Container(
                content=settings_content,
                padding=15,
            ),
            elevation=3,
        )

    def build_progress_panel(self):
        """진행 상황 패널 구성"""
        # 진행률 표시
        main_progress_bar = ft.ProgressBar(
            value=0,
            height=20,
            color=ft.Colors.BLUE,
            bgcolor=ft.Colors.GREY_300,
        )

        progress_text = ft.Text(
            "대기 중...",
            size=16,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )

        progress_detail = ft.Text(
            "번역을 시작하려면 시작 버튼을 클릭하세요.",
            size=12,
            color=ft.Colors.GREY_600,
            text_align=ft.TextAlign.CENTER,
        )

        # 상태 정보
        status_info = ft.Column(
            [
                ft.Text("현재 단계: 대기 중", size=12),
                ft.Text("경과 시간: 00:00:00", size=12),
                ft.Text("시작 시간: 미시작", size=12),
            ]
        )

        progress_content = ft.Column(
            [
                ft.Container(
                    content=ft.Text(
                        "번역 진행 상황", size=18, weight=ft.FontWeight.BOLD
                    ),
                    padding=ft.padding.only(bottom=10),
                ),
                ft.Container(
                    content=progress_text,
                    padding=ft.padding.only(bottom=5),
                ),
                ft.Container(
                    content=main_progress_bar,
                    padding=ft.padding.only(bottom=10),
                ),
                ft.Container(
                    content=progress_detail,
                    padding=ft.padding.only(bottom=15),
                ),
                ft.Divider(),
                ft.Container(
                    content=status_info,
                    padding=ft.padding.only(top=10),
                ),
            ]
        )

        progress_container = ft.Card(
            content=ft.Container(
                content=progress_content,
                padding=15,
            ),
            elevation=3,
        )

        return (
            progress_container,
            main_progress_bar,
            progress_text,
            progress_detail,
            status_info,
        )

    def build_log_panel(
        self, clear_logs_callback: Callable, save_logs_callback: Callable
    ):
        """로그 패널 구성 (최대 높이 제한)"""
        # 로그 표시 영역 (최대 높이 제한하여 스크롤)
        log_container = ft.ListView(
            height=500,  # 최대 높이 500px로 제한
            spacing=1,
            auto_scroll=True,
            padding=ft.padding.all(5),
        )

        # 로그 컨트롤
        log_controls = ft.Row(
            [
                ft.Text("번역 로그", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.CLEAR,
                    tooltip="로그 지우기",
                    on_click=clear_logs_callback,
                    icon_size=16,
                ),
                ft.IconButton(
                    icon=ft.Icons.SAVE,
                    tooltip="로그 저장",
                    on_click=save_logs_callback,
                    icon_size=16,
                ),
            ],
            spacing=5,
        )

        log_content = ft.Column(
            [
                log_controls,
                ft.Divider(height=1),
                ft.Container(
                    content=log_container,
                    height=530,  # 컨테이너도 고정 높이
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    border_radius=5,
                    padding=3,
                ),
            ],
            spacing=5,
            tight=True,  # 공간 효율적으로 사용
        )

        log_panel = ft.Card(
            content=ft.Container(
                content=log_content,
                padding=15,
                height=600,  # 카드 전체 높이 고정
            ),
            elevation=3,
        )

        return log_panel, log_container

    def build_control_panel(
        self,
        start_callback: Callable,
        stop_callback: Callable,
        is_translating: bool = False,
    ):
        """컨트롤 패널 구성"""
        start_button = ft.ElevatedButton(
            "번역 시작",
            icon=ft.Icons.PLAY_ARROW,
            on_click=start_callback,
            disabled=is_translating,
            width=120,
            height=40,
        )

        stop_button = ft.ElevatedButton(
            "번역 중지",
            icon=ft.Icons.STOP,
            on_click=stop_callback,
            disabled=not is_translating,
            width=120,
            height=40,
            color=ft.Colors.RED,
        )

        status_text = ft.Text("준비됨", size=14, color=ft.Colors.GREEN)

        control_buttons = ft.Row(
            [
                start_button,
                stop_button,
                ft.Container(expand=True),
                status_text,
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        return control_buttons, start_button, stop_button, status_text

    def build_main_layout(
        self, header, settings_panel, progress_panel, log_panel, control_panel
    ):
        """메인 레이아웃 구성"""
        # 메인 컨텐츠 (3열 레이아웃 - 1:2:1 비율)
        content = ft.Row(
            [
                # 왼쪽: 설정 패널 (비율 1)
                ft.Container(
                    content=settings_panel,
                    expand=1,
                    padding=10,
                ),
                # 중간: 진행 상황 (비율 2)
                ft.Container(
                    content=progress_panel,
                    expand=2,
                    padding=10,
                ),
                # 오른쪽: 로그 (비율 1, 높이 제한)
                ft.Container(
                    content=log_panel,
                    expand=1,
                    padding=10,
                ),
            ],
            expand=True,
            spacing=10,
        )

        # 전체 레이아웃
        main_layout = ft.Column(
            [
                header,
                ft.Divider(),
                ft.Container(
                    content=content,
                    expand=True,
                ),
                ft.Divider(),
                control_panel,
            ],
            expand=True,
            spacing=10,
        )

        return ft.Container(
            content=main_layout,
            padding=20,
            expand=True,
        )

    def update_control_buttons_state(
        self, start_button, stop_button, status_text, is_translating: bool
    ):
        """컨트롤 버튼 상태 업데이트"""
        start_button.disabled = is_translating
        stop_button.disabled = not is_translating

        if is_translating:
            status_text.value = "번역 중..."
            status_text.color = ft.Colors.ORANGE
        else:
            status_text.value = "준비됨"
            status_text.color = ft.Colors.GREEN

        self.page.update()

    def show_confirmation_dialog(
        self, title: str, content: str, on_confirm: Callable, on_cancel: Callable = None
    ):
        """확인 다이얼로그 표시"""

        def close_dialog():
            if hasattr(self.page, "dialog") and self.page.dialog:
                self.page.dialog.open = False
                self.page.update()

        def handle_confirm(e):
            close_dialog()
            if on_confirm:
                on_confirm()

        def handle_cancel(e):
            close_dialog()
            if on_cancel:
                on_cancel()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(content),
            actions=[
                ft.TextButton("취소", on_click=handle_cancel),
                ft.TextButton("확인", on_click=handle_confirm),
            ],
        )

        # 다이얼로그 열기
        try:
            if hasattr(self.page, "open"):
                self.page.open(dialog)
            else:
                self.page.dialog = dialog
                dialog.open = True
                self.page.update()
        except Exception as e:
            print(f"다이얼로그 열기 실패: {e}")

    def create_status_chip(self, text: str, color: ft.Colors, icon: str = None):
        """상태 칩 생성"""
        content = [ft.Text(text, size=12, color=ft.Colors.WHITE)]
        if icon:
            content.insert(0, ft.Icon(icon, size=16, color=ft.Colors.WHITE))

        return ft.Container(
            content=ft.Row(content, spacing=5, tight=True),
            bgcolor=color,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=12,
        )

    def create_info_card(self, title: str, value: str, icon: str = None):
        """정보 카드 생성"""
        content = [
            ft.Text(title, size=12, color=ft.Colors.GREY_600),
            ft.Text(value, size=16, weight=ft.FontWeight.BOLD),
        ]

        if icon:
            content.insert(0, ft.Icon(icon, size=24, color=ft.Colors.BLUE))

        return ft.Card(
            content=ft.Container(
                content=ft.Column(content, spacing=5),
                padding=10,
                width=120,
            ),
            elevation=2,
        )

    def _get_current_api_key(self, provider_id: str) -> str:
        """현재 제공업체의 API 키 조회"""
        return self.env_manager.get_api_key(provider_id) or ""

    def _on_api_key_change(self, e, provider_id: str):
        """API 키 변경 시 처리"""
        api_key = e.control.value
        if api_key.strip():
            self.env_manager.set_api_key(provider_id, api_key.strip())
            self.env_manager.save_env_file()

    def _on_provider_change(self, e, update_setting_callback: Callable):
        """제공업체 변경 시 처리"""
        provider_id = e.control.value
        update_setting_callback("llm_provider", provider_id)

        # API 키 필드 업데이트
        if hasattr(self, "api_key_field"):
            self.api_key_field.value = self._get_current_api_key(provider_id)
            self.api_key_field.update()

        # 모델 목록 초기화하고 새로 로드
        if hasattr(self, "model_dropdown"):
            self.model_dropdown.options = []
            self.model_dropdown.value = ""
            self.model_dropdown.update()

            # 새 제공업체의 모델 로드
            self.page.run_task(
                self._load_models_for_provider, provider_id, self.model_dropdown
            )

    async def _load_initial_models(self, provider_id: str, model_dropdown: ft.Dropdown):
        """초기 모델 목록 로드"""
        await self._load_models_for_provider(provider_id, model_dropdown)

    async def _load_models_for_provider(
        self, provider_id: str, model_dropdown: ft.Dropdown
    ):
        """특정 제공업체의 모델 목록 로드"""
        try:
            models = await self.llm_manager.get_available_models(provider_id)

            # 드롭다운 옵션 업데이트
            options = []
            for model in models:
                options.append(ft.dropdown.Option(model["id"], f"{model['id']}"))

            model_dropdown.options = options
            if options:
                model_dropdown.value = options[0].key  # 첫 번째 모델을 기본 선택
            model_dropdown.update()

            # 사용 가능한 모델 캐시에 저장
            self.available_models[provider_id] = models

        except Exception as e:
            print(f"모델 로드 실패 ({provider_id}): {e}")
            model_dropdown.options = [ft.dropdown.Option("", f"모델 로드 실패: {e}")]
            model_dropdown.update()

    def _refresh_models(self, provider_id: str, model_dropdown: ft.Dropdown):
        """모델 목록 새로고침"""
        if provider_id:
            self.page.run_task(
                self._load_models_for_provider, provider_id, model_dropdown
            )

    def _create_slider_row(self, label: str, slider: ft.Slider, value_text: ft.Text):
        """슬라이더와 값 표시를 포함한 행 생성"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(label, size=14, weight=ft.FontWeight.W_500),
                            ft.Container(expand=True),
                            value_text,
                        ]
                    ),
                    slider,
                ],
                spacing=5,
            ),
            padding=ft.padding.symmetric(vertical=8),
        )

    def _update_temperature(self, e, update_setting_callback, value_text: ft.Text):
        """Temperature 슬라이더 값 업데이트"""
        value = round(e.control.value, 1)
        value_text.value = f"{value:.1f}"
        value_text.update()
        update_setting_callback("temperature", value)

    def _update_max_tokens(self, e, update_setting_callback, value_text: ft.Text):
        """Max tokens 슬라이더 값 업데이트"""
        value = int(e.control.value)
        value_text.value = f"{value}"
        value_text.update()
        update_setting_callback("max_tokens_per_chunk", value)

    def _update_concurrent(self, e, update_setting_callback, value_text: ft.Text):
        """동시 요청수 슬라이더 값 업데이트"""
        value = int(e.control.value)
        value_text.value = f"{value}"
        value_text.update()
        update_setting_callback("max_concurrent_requests", value)

    def _update_delay(self, e, update_setting_callback, value_text: ft.Text):
        """지연 시간 슬라이더 값 업데이트"""
        value = int(e.control.value)
        value_text.value = f"{value}ms"
        value_text.update()
        update_setting_callback("delay_between_requests_ms", value)

    def _update_retries(self, e, update_setting_callback, value_text: ft.Text):
        """재시도 횟수 슬라이더 값 업데이트"""
        value = int(e.control.value)
        value_text.value = f"{value}"
        value_text.update()
        update_setting_callback("max_retries", value)

    def _get_glossary_word_count(self) -> int:
        """현재 glossary.json 단어 수를 반환"""
        try:
            if self.glossary_path.exists():
                with open(self.glossary_path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    if isinstance(data, dict):
                        return len(data)
                    if isinstance(data, list):
                        return len(data)
        except Exception:
            pass
        return 0

    def _reset_glossary(self, count_text: ft.Text):
        """용어집 초기화 (파일 삭제/비우기)"""
        try:
            if self.glossary_path.exists():
                self.glossary_path.write_text("{}", encoding="utf-8")
            # UI 업데이트
            count_text.value = f"{tr('gui.glossary.count', '단어 수')}: 0"
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(
                    tr("gui.message.glossary_cleared", "용어집이 초기화되었습니다.")
                ),
                bgcolor=ft.colors.GREEN,
            )
            self.page.snack_bar.open = True
            self.page.update()
        except Exception as err:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(str(err)),
                bgcolor=ft.colors.ERROR,
            )
            self.page.snack_bar.open = True
            self.page.update()
