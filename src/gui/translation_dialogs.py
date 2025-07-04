"""
번역 완료 다이얼로그 관련 기능들
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import Callable

import flet as ft


class TranslationCompletionDialog:
    """번역 완료 다이얼로그 관리 클래스"""

    def __init__(self, page: ft.Page, add_log_callback: Callable[[str, str], None]):
        self.page = page
        self.add_log_message = add_log_callback

    def show_completion_dialog(self, output_dir: str, translated_count: int):
        """번역 완료 다이얼로그 표시"""
        try:
            print("=== 번역 완료 다이얼로그 표시 시작 ===")

            self.add_log_message(
                "SUCCESS",
                f"🎉 번역 완료! 총 {translated_count:,}개 항목이 번역되었습니다",
            )

            # 생성된 파일들 확인
            generated_files = self._get_generated_files(output_dir)

            # 다이얼로그 컨텐츠 생성
            dialog_content = self._build_dialog_content(
                output_dir, translated_count, generated_files
            )

            # 액션 버튼들 생성
            actions = self._build_dialog_actions(output_dir, generated_files)

            # 완료 다이얼로그 생성
            completion_dialog = ft.AlertDialog(
                modal=True,
                open=True,  # 명시적으로 열기 상태 설정
                title=ft.Text("🎉 번역 완료", size=18, weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=dialog_content,
                    width=500,
                    height=280,
                ),
                actions=actions,
                actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                on_dismiss=lambda e: print("완료 다이얼로그가 닫혔습니다"),
            )

            # 다이얼로그 열기
            self._open_dialog(completion_dialog)

            self.add_log_message("SUCCESS", "번역 완료 다이얼로그가 표시되었습니다")

        except Exception as e:
            self._handle_dialog_error(e, output_dir, translated_count)

    def _get_generated_files(self, output_dir: str) -> list:
        """생성된 파일들 목록 반환"""
        generated_files = []

        # 메인 번역 파일들 확인
        main_translation_file = os.path.join(output_dir, "modpack_translation.json")
        if os.path.exists(main_translation_file):
            generated_files.append(("번역 결과 파일", main_translation_file))
            self.add_log_message(
                "INFO", f"✅ 번역 파일 생성됨: {main_translation_file}"
            )

        mapping_file = main_translation_file.replace(".json", "_mapping.json")
        if os.path.exists(mapping_file):
            generated_files.append(("매핑 파일", mapping_file))
            self.add_log_message("INFO", f"✅ 매핑 파일 생성됨: {mapping_file}")

        stats_file = main_translation_file.replace(".json", "_stats.json")
        if os.path.exists(stats_file):
            generated_files.append(("통계 파일", stats_file))
            self.add_log_message("INFO", f"✅ 통계 파일 생성됨: {stats_file}")

        # 패키징 결과 확인
        packaging_output = Path(output_dir).parent / "packaging_output"
        if packaging_output.exists():
            # 실제 생성된 파일명 찾기 (언어에 관계없이)
            resourcepack_zip = None
            modpack_zip = None

            # 리소스팩 파일 찾기 (패턴: *_*_리소스팩.zip)
            for file_path in packaging_output.glob("*_*_리소스팩.zip"):
                resourcepack_zip = file_path
                break

            # 모드팩 파일 찾기 (패턴: *_*_덮어쓰기.zip)
            for file_path in packaging_output.glob("*_*_덮어쓰기.zip"):
                modpack_zip = file_path
                break

            if resourcepack_zip and resourcepack_zip.exists():
                generated_files.append(("리소스팩 (압축)", str(resourcepack_zip)))
                self.add_log_message("INFO", f"✅ 리소스팩 생성됨: {resourcepack_zip}")

            if modpack_zip and modpack_zip.exists():
                generated_files.append(("모드팩 (압축)", str(modpack_zip)))
                self.add_log_message(
                    "INFO", f"✅ 모드팩 압축파일 생성됨: {modpack_zip}"
                )

        # 출력 경로 로그
        self.add_log_message("INFO", f"📁 출력 위치: {output_dir}")

        return generated_files

    def _build_dialog_content(
        self, output_dir: str, translated_count: int, generated_files: list
    ) -> ft.Column:
        """다이얼로그 컨텐츠 구성"""
        # 파일 목록 생성
        if not generated_files:
            file_list_content = [
                ft.Container(
                    content=ft.Text(
                        "생성된 파일이 없습니다.", size=12, color=ft.Colors.ORANGE
                    ),
                    padding=ft.padding.symmetric(vertical=5),
                )
            ]
        else:
            file_list_content = []
            for file_type, file_path in generated_files:
                file_list_content.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.FILE_PRESENT,
                                    size=16,
                                    color=ft.Colors.GREEN,
                                ),
                                ft.Text(
                                    f"{file_type}: {Path(file_path).name}",
                                    size=12,
                                    expand=True,
                                ),
                            ]
                        ),
                        padding=ft.padding.symmetric(vertical=2),
                    )
                )

        return ft.Column(
            [
                # 성공 아이콘과 메시지
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_OUTLINE,
                                size=48,
                                color=ft.Colors.GREEN,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        "번역 완료!",
                                        size=24,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.GREEN,
                                    ),
                                    ft.Text(
                                        f"총 {translated_count:,}개 항목이 번역되었습니다.",
                                        size=14,
                                    ),
                                ],
                                expand=True,
                                spacing=5,
                            ),
                        ],
                        spacing=15,
                    ),
                    padding=ft.padding.only(bottom=10),
                ),
                ft.Divider(),
                # 파일 목록
                ft.Text("생성된 파일들:", size=14, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Column(
                        file_list_content,
                        spacing=3,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    height=100,
                    padding=10,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    border_radius=5,
                ),
                # 출력 경로
                ft.Container(
                    content=ft.Text(
                        f"출력 위치: {output_dir}",
                        size=11,
                        color=ft.Colors.GREY_600,
                    ),
                    padding=ft.padding.only(top=5),
                ),
            ],
            spacing=8,
            tight=True,
        )

    def _build_dialog_actions(self, output_dir: str, generated_files: list) -> list:
        """다이얼로그 액션 버튼들 구성"""
        actions = []

        # 클로저를 위한 변수 고정
        output_dir_fixed = output_dir

        # 패키징 결과가 있으면 패키징 폴더 열기 버튼 추가
        packaging_output = Path(output_dir).parent / "packaging_output"
        if packaging_output.exists():
            actions.append(
                ft.TextButton(
                    "패키징 결과 폴더",
                    icon=ft.Icons.ARCHIVE,
                    on_click=lambda e,
                    path=output_dir_fixed: self._open_packaging_folder_and_close(path),
                )
            )

        # 번역 파일 폴더 열기 버튼
        actions.append(
            ft.TextButton(
                "번역 파일 폴더",
                icon=ft.Icons.FOLDER_OPEN,
                on_click=lambda e,
                path=output_dir_fixed: self._open_output_folder_and_close(path),
            )
        )

        # 확인 버튼
        actions.append(
            ft.TextButton(
                "확인",
                on_click=lambda e: self._close_completion_dialog(),
            )
        )

        return actions

    def _open_dialog(self, dialog: ft.AlertDialog):
        """다이얼로그 열기 (Flet 공식 방식 우선)"""
        print("다이얼로그 열기 시작...")
        open_error = None
        old_error = None

        try:
            # 방법 1: page.open() 시도 (Flet 공식 권장 방식)
            if hasattr(self.page, "open"):
                self.page.open(dialog)
                self.page.dialog = dialog  # page.open 사용 시 dialog 참조 저장
                print("page.open() 방식으로 다이얼로그 열기 성공")
                return
            else:
                print("page.open() 메서드가 없음")
                raise AttributeError("page.open() 메서드가 없음")
        except Exception as e:
            open_error = e
            print(f"page.open() 실패: {e}")

        try:
            # 방법 2: 기존 방식 시도 (page.dialog 사용)
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()
            print("기존 방식으로 다이얼로그 열기 성공")
        except Exception as e:
            old_error = e
            print(f"기존 방식도 실패: {e}")
            raise Exception(
                f"모든 다이얼로그 열기 방식 실패: page.open() -> {open_error}, page.dialog -> {old_error}"
            )

        print("다이얼로그 열기 완료!")

    def _close_completion_dialog(self):
        """완료 다이얼로그 닫기 (Flet 공식 방식 우선)"""
        try:
            print("완료 다이얼로그 닫기 시도")

            # 방법 1: page.close() 시도 (Flet 공식 권장 방식)
            if (
                hasattr(self.page, "close")
                and hasattr(self.page, "dialog")
                and self.page.dialog
            ):
                try:
                    self.page.close(self.page.dialog)
                    print("page.close() 방식으로 다이얼로그 닫기 성공")
                    self.add_log_message("INFO", "완료 다이얼로그가 닫혔습니다")
                    return
                except Exception as close_error:
                    print(f"page.close() 실패: {close_error}")

            # 방법 2: open=False 방식 시도 (공식 문서 기준)
            if hasattr(self.page, "dialog") and self.page.dialog:
                try:
                    self.page.dialog.open = False
                    self.page.update()
                    print("open=False 방식으로 다이얼로그 닫기 성공")
                    self.add_log_message("INFO", "완료 다이얼로그가 닫혔습니다")
                    return
                except Exception as open_false_error:
                    print(f"open=False 방식 실패: {open_false_error}")

            # 방법 3: 강제 참조 제거 시도
            try:
                if hasattr(self.page, "dialog"):
                    if self.page.dialog:
                        self.page.dialog.open = False
                    self.page.dialog = None  # 다이얼로그 참조 완전히 제거

                self.page.update()
                print("강제 참조 제거 방식으로 다이얼로그 닫기 성공")
                self.add_log_message("INFO", "완료 다이얼로그가 닫혔습니다")
                return
            except Exception as force_error:
                print(f"강제 참조 제거 실패: {force_error}")

            # 방법 4: overlay 방식 시도 (마지막 수단)
            if hasattr(self.page, "overlay") and self.page.overlay:
                try:
                    # overlay에서 AlertDialog 타입 찾아서 제거
                    dialogs_to_remove = []
                    for item in self.page.overlay:
                        if isinstance(item, ft.AlertDialog):
                            dialogs_to_remove.append(item)

                    for dialog in dialogs_to_remove:
                        self.page.overlay.remove(dialog)

                    if dialogs_to_remove:
                        self.page.update()
                        print("overlay에서 AlertDialog 제거 완료")
                        self.add_log_message("INFO", "완료 다이얼로그가 닫혔습니다")
                        return
                    else:
                        print("overlay에 AlertDialog가 없음")

                except Exception as overlay_error:
                    print(f"overlay 방식 실패: {overlay_error}")

            print("모든 다이얼로그 닫기 방식 실패")
            self.add_log_message(
                "WARNING", "다이얼로그 닫기에 실패했습니다. 수동으로 닫아주세요."
            )

        except Exception as e:
            print(f"다이얼로그 닫기 실패: {e}")
            self.add_log_message("ERROR", f"다이얼로그 닫기 오류: {e}")

    def _open_output_folder_and_close(self, output_dir: str):
        """출력 폴더 열기 후 다이얼로그 닫기"""
        self._open_folder(output_dir)
        self._close_completion_dialog()

    def _open_packaging_folder_and_close(self, output_dir: str):
        """패키징 폴더 열기 후 다이얼로그 닫기"""
        try:
            packaging_dir = str(Path(output_dir).parent / "packaging_output")
            if os.path.exists(packaging_dir):
                self._open_folder(packaging_dir)
                self.add_log_message("SUCCESS", f"패키징 폴더 열기: {packaging_dir}")
            else:
                self.add_log_message("WARNING", "패키징 폴더가 존재하지 않습니다.")
        except Exception as e:
            self.add_log_message("ERROR", f"패키징 폴더 열기 실패: {e}")
        finally:
            self._close_completion_dialog()

    def _open_folder(self, folder_path: str):
        """폴더를 시스템 탐색기로 열기"""
        try:
            print(f"폴더 열기 시도: {folder_path}")

            # 폴더가 실제로 존재하는지 확인
            if not os.path.exists(folder_path):
                error_msg = f"폴더가 존재하지 않습니다: {folder_path}"
                print(error_msg)
                self.add_log_message("ERROR", error_msg)
                return

            if platform.system() == "Windows":
                try:
                    subprocess.run(f'explorer "{folder_path}"', shell=True, check=True)
                except subprocess.CalledProcessError:
                    try:
                        os.startfile(folder_path)
                        print("os.startfile로 폴더 열기 성공")
                    except Exception as startfile_error:
                        print(f"os.startfile도 실패: {startfile_error}")
                        parent_dir = os.path.dirname(folder_path)
                        subprocess.run(
                            f'explorer /select,"{folder_path}"', shell=True, check=False
                        )
                        print("상위 폴더에서 선택하는 방식으로 실행")
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", folder_path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", folder_path], check=True)

            self.add_log_message(
                "SUCCESS", f"📁 탐색기로 폴더 열기 완료: {folder_path}"
            )
            print("폴더 열기 성공")

        except Exception as e:
            print(f"폴더 열기 실패: {e}")
            self.add_log_message(
                "WARNING", f"폴더 열기 명령어 오류 (폴더는 열렸을 수 있음): {e}"
            )

            # 대안으로 상위 폴더라도 열어보기
            try:
                parent_dir = os.path.dirname(folder_path)
                if os.path.exists(parent_dir):
                    if platform.system() == "Windows":
                        os.startfile(parent_dir)
                    self.add_log_message(
                        "INFO", f"📁 대신 상위 폴더를 열었습니다: {parent_dir}"
                    )
            except Exception as fallback_error:
                print(f"상위 폴더 열기도 실패: {fallback_error}")
                self.add_log_message("ERROR", f"폴더 열기 완전 실패: {fallback_error}")

    def _handle_dialog_error(
        self, error: Exception, output_dir: str, translated_count: int
    ):
        """다이얼로그 표시 실패 시 처리"""
        error_msg = f"완료 다이얼로그 표시 실패: {error}"
        print(f"ERROR: {error_msg}")
        import traceback

        print(f"트레이스백: {traceback.format_exc()}")

        self.add_log_message("ERROR", error_msg)

        # 대체 방법으로 스낵바 표시
        try:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"번역 완료! {translated_count:,}개 항목 번역됨"),
                action="확인",
                action_color=ft.Colors.GREEN,
            )
            self.page.snack_bar.open = True
            self.page.update()
            print("대체 스낵바 표시됨")
        except Exception as snack_error:
            print(f"스낵바 표시도 실패: {snack_error}")
            # 최후의 수단으로 로그만 출력
            self.add_log_message(
                "SUCCESS",
                f"번역 완료! 총 {translated_count:,}개 항목이 번역되었습니다",
            )
            self.add_log_message("INFO", f"출력 위치: {output_dir}")
