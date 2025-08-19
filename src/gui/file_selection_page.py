"""
번역 파일 선택 페이지 GUI
"""

import logging
import math
from typing import Callable, Dict, List

import flet as ft

from src.modpack.load import ModpackLoader

logger = logging.getLogger(__name__)


class FileSelectionPage:
    """번역할 파일을 선택하는 페이지"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.selected_modpack = None
        self.files_data: List[Dict] = []
        self.filtered_files_data: List[Dict] = []
        self.loader: ModpackLoader = None
        self.search_query = ""

        # 페이지네이션 관련
        self.items_per_page = 50
        self.current_page = 1
        self.total_pages = 1

        # UI 컴포넌트
        self.datatable: ft.DataTable = None
        self.select_all_checkbox: ft.Checkbox = None
        self.select_all_glossary_checkbox: ft.Checkbox = None
        self.start_translation_button: ft.ElevatedButton = None
        self.progress_ring: ft.ProgressRing = ft.ProgressRing(visible=False)
        self.status_text: ft.Text = ft.Text("파일을 스캔하고 있습니다...")
        self.search_field: ft.TextField = None
        self.page_info_text: ft.Text = None
        self.prev_page_button: ft.IconButton = None
        self.next_page_button: ft.IconButton = None
        self.page_size_dropdown: ft.Dropdown = None

        # 콜백
        self.on_start_translation: Callable[
            [ModpackLoader, List[str], List[str]], None
        ] = None
        self.on_back: Callable[[], None] = None

    def set_modpack(self, modpack_info: Dict):
        """선택된 모드팩 정보 설정"""
        self.selected_modpack = modpack_info
        self.loader = ModpackLoader(modpack_info["path"], target_lang="ko_kr")

    def set_callbacks(self, on_start: Callable, on_back: Callable):
        """콜백 함수 설정"""
        self.on_start_translation = on_start
        self.on_back = on_back

    def build_ui(self):
        """페이지 UI 빌드"""
        self.page.clean()

        self.select_all_checkbox = ft.Checkbox(
            label="번역 전체 선택/해제", value=True, on_change=self._toggle_all_files
        )
        self.select_all_glossary_checkbox = ft.Checkbox(
            label="사전 생성 전체 선택/해제",
            value=False,
            on_change=self._toggle_all_glossary,
        )
        self.start_translation_button = ft.ElevatedButton(
            "선택한 파일 번역", on_click=self._start_translation_clicked, disabled=True
        )

        self.search_field = ft.TextField(
            label="파일 검색",
            hint_text="파일명 또는 경로로 검색...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_changed,
            expand=True,
        )

        self.page_size_dropdown = ft.Dropdown(
            label="페이지 크기",
            value="50",
            options=[
                ft.dropdown.Option("25"),
                ft.dropdown.Option("50"),
                ft.dropdown.Option("100"),
                ft.dropdown.Option("200"),
            ],
            on_change=self._on_page_size_changed,
            width=120,
        )

        self.datatable = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("번역")),
                ft.DataColumn(ft.Text("사전")),
                ft.DataColumn(ft.Text("파일 이름")),
                ft.DataColumn(ft.Text("경로")),
                ft.DataColumn(ft.Text("카테고리")),
            ],
            rows=[],
            expand=True,
        )

        # 페이지네이션 컨트롤
        self.prev_page_button = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip="이전 페이지",
            on_click=self._prev_page,
            disabled=True,
        )

        self.next_page_button = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip="다음 페이지",
            on_click=self._next_page,
            disabled=True,
        )

        self.page_info_text = ft.Text("페이지 1 / 1")

        header = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda e: self.on_back() if self.on_back else None,
                ),
                ft.Text(
                    f"번역 파일 선택: {self.selected_modpack.get('name', 'Unknown')}",
                    style=ft.TextThemeStyle.HEADLINE_SMALL,
                ),
            ]
        )

        search_row = ft.Row(
            [
                self.search_field,
                ft.IconButton(
                    icon=ft.Icons.CLEAR,
                    tooltip="검색 초기화",
                    on_click=self._clear_search,
                ),
                self.page_size_dropdown,
            ]
        )

        controls = ft.Row(
            [
                self.select_all_checkbox,
                self.select_all_glossary_checkbox,
                ft.Container(expand=True),  # Spacer
                self.start_translation_button,
            ]
        )

        pagination_row = ft.Row(
            [
                self.prev_page_button,
                self.page_info_text,
                self.next_page_button,
                ft.Container(expand=True),  # Spacer
                self.status_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        main_layout = ft.Column(
            [
                header,
                search_row,
                controls,
                ft.Divider(),
                ft.Row([self.progress_ring]),
                pagination_row,
                ft.Container(content=self.datatable, expand=True),
            ],
            expand=True,
        )

        self.page.add(main_layout)
        self.page.update()

        # UI 빌드 후 파일 스캔 시작
        self.page.run_task(self._scan_files)

    async def _scan_files(self):
        """백그라운드에서 번역 가능 파일 스캔"""
        self.progress_ring.visible = True
        self.page.update()

        try:
            # ModpackLoader를 사용하여 파일 스캔
            self.files_data = await self.page.loop.run_in_executor(
                None, self.loader.scan_translatable_files
            )
            self.filtered_files_data = self.files_data.copy()
            self._update_pagination()
            self._update_status_text()
            # DataTable 채우기
            self._populate_datatable()
        except Exception as e:
            logger.error(f"파일 스캔 중 오류 발생: {e}")
            self.status_text.value = f"오류: {e}"
        finally:
            self.progress_ring.visible = False
            self._update_button_state()
            self.page.update()

    def _on_search_changed(self, e: ft.ControlEvent):
        """검색어 변경 시 호출"""
        self.search_query = e.control.value.lower().strip()
        self._filter_files()
        self.current_page = 1  # 검색 시 첫 페이지로 이동
        self._update_pagination()
        self._populate_datatable()

    def _clear_search(self, e: ft.ControlEvent):
        """검색 초기화"""
        self.search_field.value = ""
        self.search_query = ""
        self._filter_files()
        self.current_page = 1
        self._update_pagination()
        self._populate_datatable()
        self.page.update()

    def _on_page_size_changed(self, e: ft.ControlEvent):
        """페이지 크기 변경 시 호출"""
        self.items_per_page = int(e.control.value)
        self.current_page = 1
        self._update_pagination()
        self._populate_datatable()

    def _prev_page(self, e: ft.ControlEvent):
        """이전 페이지로 이동"""
        if self.current_page > 1:
            self.current_page -= 1
            self._update_pagination()
            self._populate_datatable()

    def _next_page(self, e: ft.ControlEvent):
        """다음 페이지로 이동"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._update_pagination()
            self._populate_datatable()

    def _update_pagination(self):
        """페이지네이션 정보 업데이트"""
        total_items = len(self.filtered_files_data)
        self.total_pages = max(1, math.ceil(total_items / self.items_per_page))

        # 현재 페이지가 총 페이지 수를 초과하지 않도록 조정
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages

        # 버튼 상태 업데이트
        if self.prev_page_button:
            self.prev_page_button.disabled = self.current_page <= 1
        if self.next_page_button:
            self.next_page_button.disabled = self.current_page >= self.total_pages

        # 페이지 정보 텍스트 업데이트
        if self.page_info_text:
            self.page_info_text.value = (
                f"페이지 {self.current_page} / {self.total_pages}"
            )

    def _update_status_text(self):
        """상태 텍스트 업데이트"""
        if self.search_query:
            self.status_text.value = (
                f"{len(self.filtered_files_data)}개 파일 "
                f"(전체 {len(self.files_data)}개 중)"
            )
        else:
            self.status_text.value = f"{len(self.files_data)}개의 번역 가능한 파일"

    def _filter_files(self):
        """검색어에 따라 파일 목록 필터링"""
        if not self.search_query:
            self.filtered_files_data = self.files_data.copy()
        else:
            self.filtered_files_data = [
                file_data
                for file_data in self.files_data
                if (
                    self.search_query in file_data["file_name"].lower()
                    or self.search_query in file_data["relative_path"].lower()
                    or self.search_query in file_data["category"].lower()
                )
            ]

        self._update_status_text()

    def _get_current_page_data(self):
        """현재 페이지에 표시할 데이터 반환"""
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        return self.filtered_files_data[start_idx:end_idx]

    def _populate_datatable(self):
        """스캔된 파일 데이터로 DataTable 채우기"""
        current_page_data = self._get_current_page_data()

        # 카테고리별로 그룹화
        grouped_files = {}
        for file_data in current_page_data:
            category = file_data["category"]
            if category not in grouped_files:
                grouped_files[category] = []
            grouped_files[category].append(file_data)

        self.datatable.rows.clear()
        for category, files in sorted(grouped_files.items()):
            # 카테고리 헤더 행 추가
            category_checkbox = ft.Checkbox(
                data=category,
                on_change=self._toggle_category,
                value=True,
            )
            category_glossary_checkbox = ft.Checkbox(
                data=category,
                on_change=self._toggle_category_glossary,
                value=False,
            )
            self.datatable.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(category_checkbox),
                        ft.DataCell(category_glossary_checkbox),
                        ft.DataCell(
                            ft.Text(
                                f"{category} ({len(files)}개)",
                                weight=ft.FontWeight.BOLD,
                            )
                        ),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                    ],
                )
            )

            # 파일 행 추가
            for file_data in files:
                checkbox = ft.Checkbox(
                    value=file_data.get("selected", True),
                    data=file_data,
                    on_change=self._file_selection_changed,
                )
                glossary_checkbox = ft.Checkbox(
                    value=file_data.get("glossary_selected", False),
                    data=file_data,
                    on_change=self._file_glossary_selection_changed,
                )
                self.datatable.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(checkbox),
                            ft.DataCell(glossary_checkbox),
                            ft.DataCell(ft.Text(file_data["file_name"])),
                            ft.DataCell(ft.Text(file_data["relative_path"])),
                            ft.DataCell(ft.Text(file_data["category"])),
                        ]
                    )
                )
        self._update_category_checkboxes()
        self.page.update()

    def _file_selection_changed(self, e: ft.ControlEvent):
        """개별 파일 번역 체크박스 변경 시 호출"""
        e.control.data["selected"] = e.control.value
        self._update_button_state()
        self._update_category_checkboxes()
        self._update_global_checkboxes()

    def _file_glossary_selection_changed(self, e: ft.ControlEvent):
        """개별 파일 사전 생성 체크박스 변경 시 호출"""
        e.control.data["glossary_selected"] = e.control.value
        self._update_category_checkboxes()
        self._update_global_checkboxes()

    def _toggle_all_files(self, e: ft.ControlEvent):
        """'번역 전체 선택' 체크박스 변경 시 호출 - 전체 파일에 적용"""
        is_selected = e.control.value
        # 전체 파일 데이터에 적용
        for file_data in self.filtered_files_data:
            file_data["selected"] = is_selected

        # 현재 페이지의 UI 체크박스들도 업데이트
        for row in self.datatable.rows:
            checkbox = row.cells[0].content
            if (
                isinstance(checkbox, ft.Checkbox)
                and checkbox.data
                and isinstance(checkbox.data, dict)
            ):
                checkbox.value = is_selected

        self._update_button_state()
        self._update_category_checkboxes()
        self.page.update()

    def _toggle_all_glossary(self, e: ft.ControlEvent):
        """'사전 생성 전체 선택' 체크박스 변경 시 호출 - 전체 파일에 적용"""
        is_selected = e.control.value
        # 전체 파일 데이터에 적용
        for file_data in self.filtered_files_data:
            file_data["glossary_selected"] = is_selected

        # 현재 페이지의 UI 체크박스들도 업데이트
        for row in self.datatable.rows:
            if len(row.cells) > 1:
                glossary_checkbox = row.cells[1].content
                if (
                    isinstance(glossary_checkbox, ft.Checkbox)
                    and glossary_checkbox.data
                    and isinstance(glossary_checkbox.data, dict)
                ):
                    glossary_checkbox.value = is_selected

        self._update_category_checkboxes()
        self.page.update()

    def _toggle_category(self, e: ft.ControlEvent):
        """카테고리 헤더 번역 체크박스 변경 시 호출 - 전체 파일 중 해당 카테고리에 적용"""
        category = e.control.data
        is_selected = e.control.value

        # 전체 파일 데이터 중 해당 카테고리에 적용
        for file_data in self.filtered_files_data:
            if file_data.get("category") == category:
                file_data["selected"] = is_selected

        # 현재 페이지의 UI 체크박스들도 업데이트
        for row in self.datatable.rows:
            checkbox = row.cells[0].content
            if (
                isinstance(checkbox, ft.Checkbox)
                and checkbox.data
                and isinstance(checkbox.data, dict)
                and checkbox.data.get("category") == category
            ):
                checkbox.value = is_selected

        self._update_button_state()
        self._update_global_checkboxes()
        self.page.update()

    def _toggle_category_glossary(self, e: ft.ControlEvent):
        """카테고리 헤더 사전 생성 체크박스 변경 시 호출 - 전체 파일 중 해당 카테고리에 적용"""
        category = e.control.data
        is_selected = e.control.value

        # 전체 파일 데이터 중 해당 카테고리에 적용
        for file_data in self.filtered_files_data:
            if file_data.get("category") == category:
                file_data["glossary_selected"] = is_selected

        # 현재 페이지의 UI 체크박스들도 업데이트
        for row in self.datatable.rows:
            if len(row.cells) > 1:
                glossary_checkbox = row.cells[1].content
                if (
                    isinstance(glossary_checkbox, ft.Checkbox)
                    and glossary_checkbox.data
                    and isinstance(glossary_checkbox.data, dict)
                    and glossary_checkbox.data.get("category") == category
                ):
                    glossary_checkbox.value = is_selected

        self._update_global_checkboxes()
        self.page.update()

    def _update_button_state(self):
        """'번역 시작' 버튼 상태 업데이트"""
        selected_count = sum(
            1 for file_data in self.files_data if file_data.get("selected")
        )
        self.start_translation_button.disabled = selected_count == 0
        self.page.update()

    def _update_global_checkboxes(self):
        """전역 체크박스 상태 업데이트 (전체 선택/해제 체크박스들)"""
        # 번역 전체 선택 체크박스 상태 업데이트
        total_files = len(self.filtered_files_data)
        selected_files = sum(
            1 for file_data in self.filtered_files_data if file_data.get("selected")
        )

        if selected_files == 0:
            self.select_all_checkbox.value = False
            self.select_all_checkbox.tristate = False
        elif selected_files == total_files:
            self.select_all_checkbox.value = True
            self.select_all_checkbox.tristate = False
        else:
            self.select_all_checkbox.value = None
            self.select_all_checkbox.tristate = True

        # 사전 생성 전체 선택 체크박스 상태 업데이트
        glossary_selected_files = sum(
            1
            for file_data in self.filtered_files_data
            if file_data.get("glossary_selected")
        )

        if glossary_selected_files == 0:
            self.select_all_glossary_checkbox.value = False
            self.select_all_glossary_checkbox.tristate = False
        elif glossary_selected_files == total_files:
            self.select_all_glossary_checkbox.value = True
            self.select_all_glossary_checkbox.tristate = False
        else:
            self.select_all_glossary_checkbox.value = None
            self.select_all_glossary_checkbox.tristate = True

    def _update_category_checkboxes(self):
        """카테고리 헤더 체크박스 상태 업데이트"""
        category_status = {}  # category -> (total, selected, glossary_selected)

        # 현재 페이지의 파일들에 대해서만 집계
        current_page_data = self._get_current_page_data()
        for file_data in current_page_data:
            category = file_data["category"]
            if category not in category_status:
                category_status[category] = {
                    "total": 0,
                    "selected": 0,
                    "glossary_selected": 0,
                }
            category_status[category]["total"] += 1
            if file_data.get("selected"):
                category_status[category]["selected"] += 1
            if file_data.get("glossary_selected"):
                category_status[category]["glossary_selected"] += 1

        # 카테고리 헤더 체크박스 업데이트
        for row in self.datatable.rows:
            checkbox = row.cells[0].content
            glossary_checkbox = row.cells[1].content if len(row.cells) > 1 else None

            if (
                isinstance(checkbox, ft.Checkbox)
                and checkbox.data
                and isinstance(checkbox.data, str)
            ):
                category = checkbox.data
                stats = category_status.get(category)
                if stats:
                    # 번역 체크박스 상태 업데이트
                    if stats["selected"] == 0:
                        checkbox.value = False
                        checkbox.tristate = False
                    elif stats["selected"] == stats["total"]:
                        checkbox.value = True
                        checkbox.tristate = False
                    else:
                        checkbox.value = None  # 중간 상태
                        checkbox.tristate = True

                    # 사전 생성 체크박스 상태 업데이트
                    if isinstance(glossary_checkbox, ft.Checkbox):
                        if stats["glossary_selected"] == 0:
                            glossary_checkbox.value = False
                            glossary_checkbox.tristate = False
                        elif stats["glossary_selected"] == stats["total"]:
                            glossary_checkbox.value = True
                            glossary_checkbox.tristate = False
                        else:
                            glossary_checkbox.value = None  # 중간 상태
                            glossary_checkbox.tristate = True
        self.page.update()

    def _start_translation_clicked(self, e: ft.ControlEvent):
        """'선택한 파일 번역' 버튼 클릭 시 호출"""
        selected_paths = [
            file_data["full_path"]
            for file_data in self.files_data
            if file_data.get("selected")
        ]
        selected_glossary_paths = [
            file_data["full_path"]
            for file_data in self.files_data
            if file_data.get("glossary_selected")
        ]
        if self.on_start_translation:
            self.page.run_task(
                self.on_start_translation,
                self.loader,
                selected_paths,
                selected_glossary_paths,
            )
