"""
공통 GUI 컴포넌트들
"""

import flet as ft


def create_modpack_card(modpack_info, on_click):
    """모드팩 정보를 표시하는 카드 생성"""
    name_text = modpack_info.get("name", "N/A")
    author_text = f"by {modpack_info.get('author', 'N/A')}"
    version_text = modpack_info.get("version", "")

    # 이미지 컨테이너 - 썸네일을 로드하거나 기본 아이콘을 표시
    thumbnail_url = modpack_info.get("thumbnail_url", "")
    if thumbnail_url and thumbnail_url.startswith("http"):
        try:
            # 네트워크 이미지 사용 시도
            image_content = ft.Image(
                src=thumbnail_url,
                width=180,
                height=180,
                fit=ft.ImageFit.COVER,
                border_radius=8,
            )
        except:
            # 실패 시 기본 아이콘으로 대체
            image_content = ft.Icon(
                ft.Icons.EXTENSION,
                size=60,
            )
    else:
        # 기본 아이콘
        image_content = ft.Icon(
            ft.Icons.EXTENSION,
            size=60,
        )

    image_container = ft.Container(
        content=image_content,
        width=180,
        height=180,
        border_radius=10,
        alignment=ft.alignment.center,
    )

    card = ft.GestureDetector(
        content=ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        image_container,
                        ft.Container(height=8),  # 간격
                        # 모드팩 이름 - 길이 제한으로 넘침 방지
                        ft.Container(
                            content=ft.Text(
                                name_text[:30] + "..."
                                if len(name_text) > 30
                                else name_text,
                                size=14,
                                weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                                tooltip=modpack_info.get("name", "N/A"),
                            ),
                            width=180,
                            padding=4,
                        ),
                        # 작성자 - 길이 제한으로 넘침 방지
                        ft.Container(
                            content=ft.Text(
                                author_text[:25] + "..."
                                if len(author_text) > 25
                                else author_text,
                                size=12,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            width=180,
                            padding=2,
                        ),
                        # 버전 정보
                        ft.Container(
                            content=ft.Text(
                                version_text[:20] + "..."
                                if len(version_text) > 20
                                else version_text,
                                size=11,
                                color=ft.Colors.BLUE,
                                text_align=ft.TextAlign.CENTER,
                                weight=ft.FontWeight.W_500,
                            ),
                            width=180,
                            padding=2,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                padding=15,
                width=200,
                height=300,  # 고정 높이로 일관성 유지
            ),
            elevation=2,
        ),
        on_tap=lambda _: on_click(modpack_info),
    )

    return card


def create_progress_card(title, current, total, color=ft.Colors.BLUE):
    """진행 상황을 표시하는 카드 생성"""
    progress_value = current / total if total > 0 else 0

    return ft.Card(
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        title,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=8),
                    ft.ProgressBar(
                        value=progress_value,
                        color=color,
                        height=8,
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        f"{current} / {total}",
                        size=14,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            padding=15,
            width=200,
        ),
        elevation=2,
    )


def create_setting_row(label, control):
    """설정 행 생성"""
    return ft.Row(
        [
            ft.Container(
                content=ft.Text(
                    label,
                    size=14,
                    weight=ft.FontWeight.W_500,
                ),
                width=150,
            ),
            ft.Container(
                content=control,
                expand=True,
            ),
        ],
        spacing=10,
    )
