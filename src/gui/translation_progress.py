"""
번역 진행률 관리 모듈
"""

import asyncio
import time
from datetime import datetime
from typing import Callable

import flet as ft


class TranslationProgressManager:
    """번역 진행률 관리 클래스"""

    def __init__(self, page: ft.Page, add_log_callback: Callable[[str, str], None]):
        self.page = page
        self.add_log_message = add_log_callback

        # 번역 상태
        self.translation_stats = {
            "collected_files": 0,
            "total_files": 0,
            "translated_entries": 0,
            "total_entries": 0,
            "current_step": "대기 중",
            "start_time": None,
            "elapsed_time": "00:00:00",
        }

        # 진행률 업데이트용
        self.last_progress_update = 0
        self.progress_update_interval = 10  # 10초마다 진행률 요약

        # UI 컴포넌트들 (외부에서 설정)
        self.main_progress_bar = None
        self.progress_text = None
        self.progress_detail = None
        self.status_info = None

    def set_ui_components(
        self, main_progress_bar, progress_text, progress_detail, status_info
    ):
        """UI 컴포넌트들 설정"""
        self.main_progress_bar = main_progress_bar
        self.progress_text = progress_text
        self.progress_detail = progress_detail
        self.status_info = status_info

    def start_translation(self):
        """번역 시작 시 상태 초기화"""
        self.translation_stats["start_time"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.translation_stats["current_step"] = "번역 초기화 중..."
        self.translation_stats["collected_files"] = 0
        self.translation_stats["total_files"] = 0
        self.translation_stats["translated_entries"] = 0
        self.translation_stats["total_entries"] = 0

        self.add_log_message(
            "INFO", f"번역 시작 시간: {self.translation_stats['start_time']}"
        )
        self.update_progress_display()

    def update_progress(
        self, step: str, current: int = 0, total: int = 0, detail: str = ""
    ):
        """진행률 업데이트 콜백 함수 (번역기에서 호출)"""
        try:
            # UI 업데이트 빈도 제한 (JAR 파일 처리 시 너무 자주 호출됨)
            current_time = time.time()
            if hasattr(self, "_last_ui_update"):
                if current_time - self._last_ui_update < 1.0:  # 1초에 한 번만 업데이트
                    return
            self._last_ui_update = current_time

            self.translation_stats["current_step"] = step

            # 단계별 진행률 계산 (간소화)
            step_lower = step.lower()
            progress_value = 0.1  # 기본값

            if any(keyword in step_lower for keyword in ["스캔", "검색", "수집"]):
                progress_value = 0.2
            elif any(keyword in step_lower for keyword in ["jar", "처리"]):
                if total > 0:
                    progress_value = 0.2 + (current / total * 0.3)
                else:
                    progress_value = 0.4
            elif any(keyword in step_lower for keyword in ["추출", "데이터"]):
                if total > 0:
                    progress_value = 0.5 + (current / total * 0.2)
                else:
                    progress_value = 0.6
            elif any(keyword in step_lower for keyword in ["번역"]):
                if total > 0:
                    progress_value = 0.7 + (current / total * 0.3)
                else:
                    progress_value = 0.8
            elif "완료" in step_lower:
                progress_value = 1.0

            # Progress bar 업데이트 (안전하게)
            try:
                if self.main_progress_bar:
                    self.main_progress_bar.value = min(progress_value, 1.0)

                if self.progress_text:
                    percentage = int(progress_value * 100)
                    self.progress_text.value = f"진행률: {percentage}%"

                if self.progress_detail:
                    if total > 0:
                        self.progress_detail.value = f"{step}: {current}/{total}"
                    else:
                        self.progress_detail.value = step

                # 안전한 UI 업데이트
                self.page.update()

            except Exception:
                # UI 업데이트 오류는 무시 (로그에 출력하지 않음)
                pass

            # 중요한 진행 상황만 로그에 추가 (빈도 줄이기)
            if any(keyword in step_lower for keyword in ["완료", "시작", "실패"]):
                if detail:
                    self.add_log_message("INFO", detail)
                else:
                    self.add_log_message("INFO", step)

        except Exception:
            # 진행률 콜백 오류는 무시 (번역 진행에 영향 없음)
            pass

    def update_progress_display(self):
        """진행률 표시 업데이트"""
        try:
            # 전체 진행률 계산
            total_progress = 0.0

            if self.translation_stats["total_files"] > 0:
                file_progress = (
                    self.translation_stats["collected_files"]
                    / self.translation_stats["total_files"]
                )
                total_progress += file_progress * 0.3  # 파일 수집 30%

            if self.translation_stats["total_entries"] > 0:
                entry_progress = (
                    self.translation_stats["translated_entries"]
                    / self.translation_stats["total_entries"]
                )
                total_progress += entry_progress * 0.7  # 번역 작업 70%

            # Progress bar 업데이트
            if self.main_progress_bar:
                self.main_progress_bar.value = min(total_progress, 1.0)

            # 진행률 텍스트 업데이트
            if self.progress_text:
                percentage = int(total_progress * 100)
                self.progress_text.value = f"진행률: {percentage}%"

            # 상세 정보 업데이트
            if self.progress_detail:
                detail_parts = []
                if self.translation_stats["total_files"] > 0:
                    detail_parts.append(
                        f"파일: {self.translation_stats['collected_files']}/{self.translation_stats['total_files']}"
                    )
                if self.translation_stats["total_entries"] > 0:
                    detail_parts.append(
                        f"번역: {self.translation_stats['translated_entries']}/{self.translation_stats['total_entries']}"
                    )

                if detail_parts:
                    self.progress_detail.value = " | ".join(detail_parts)
                else:
                    self.progress_detail.value = self.translation_stats["current_step"]

            # 상태 정보 업데이트
            if self.status_info:
                self.status_info.controls[
                    0
                ].value = f"현재 단계: {self.translation_stats['current_step']}"
                self.status_info.controls[
                    1
                ].value = f"경과 시간: {self.translation_stats['elapsed_time']}"
                self.status_info.controls[
                    2
                ].value = (
                    f"시작 시간: {self.translation_stats['start_time'] or '미시작'}"
                )

            # 안전한 UI 업데이트
            try:
                self.page.update()
            except Exception as ui_error:
                print(f"UI 업데이트 오류: {ui_error}")
        except Exception as e:
            print(f"진행률 업데이트 오류: {e}")

    def show_completion_status(
        self, translated_count: int, file_count: int, output_dir: str
    ):
        """완료 상태 표시 (진행률 영역에 배너 표시)"""
        try:
            if self.progress_text:
                self.progress_text.value = "🎉 번역 완료!"
                self.progress_text.color = ft.Colors.GREEN
                self.progress_text.size = 20

            if self.progress_detail:
                self.progress_detail.value = (
                    f"총 {translated_count:,}개 항목 번역 | {file_count}개 파일 생성"
                )
                self.progress_detail.color = ft.Colors.GREEN
                self.progress_detail.size = 14

            if self.main_progress_bar:
                self.main_progress_bar.value = 1.0  # 100% 완료
                self.main_progress_bar.color = ft.Colors.GREEN

            # 상태 정보 업데이트
            if self.status_info:
                self.status_info.controls[0].value = "현재 단계: ✅ 번역 완료"
                self.status_info.controls[0].color = ft.Colors.GREEN

                # 폴더 열기 버튼 추가
                if len(self.status_info.controls) < 4:
                    self.status_info.controls.append(
                        ft.ElevatedButton(
                            "📁 결과 폴더 열기",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=lambda e: self._open_output_folder(output_dir),
                            bgcolor=ft.Colors.GREEN,
                            color=ft.Colors.WHITE,
                            height=35,
                        )
                    )

            self.page.update()
            print("완료 배너 표시 완료")

        except Exception as e:
            print(f"완료 배너 표시 오류: {e}")

    def start_time_tracker(self, is_translating_callback: Callable[[], bool]):
        """시간 추적 시작"""

        async def update_time_async():
            start_time = time.time()
            while is_translating_callback():
                elapsed = time.time() - start_time
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                self.translation_stats["elapsed_time"] = (
                    f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                )

                # UI 업데이트 (안전하게)
                try:
                    if self.status_info:
                        # 상태 정보 업데이트
                        self.status_info.controls[
                            1
                        ].value = f"경과 시간: {self.translation_stats['elapsed_time']}"

                        # 안전한 UI 업데이트
                        self.page.update()
                except Exception as e:
                    print(f"시간 추적 UI 업데이트 오류: {e}")
                    break

                await asyncio.sleep(1)

        # Flet의 page.run_task()를 사용하여 async 태스크 실행
        self.page.run_task(update_time_async)

    def reset_progress(self):
        """진행률 초기화"""
        self.translation_stats = {
            "collected_files": 0,
            "total_files": 0,
            "translated_entries": 0,
            "total_entries": 0,
            "current_step": "대기 중",
            "start_time": None,
            "elapsed_time": "00:00:00",
        }

        # UI 초기화
        if self.main_progress_bar:
            self.main_progress_bar.value = 0
            self.main_progress_bar.color = ft.Colors.BLUE

        if self.progress_text:
            self.progress_text.value = "대기 중..."
            self.progress_text.color = None
            self.progress_text.size = 16

        if self.progress_detail:
            self.progress_detail.value = "번역을 시작하려면 시작 버튼을 클릭하세요."
            self.progress_detail.color = ft.Colors.GREY_600
            self.progress_detail.size = 12

        if self.status_info:
            self.status_info.controls[
                0
            ].value = f"현재 단계: {self.translation_stats['current_step']}"
            self.status_info.controls[0].color = None
            self.status_info.controls[
                1
            ].value = f"경과 시간: {self.translation_stats['elapsed_time']}"
            self.status_info.controls[
                2
            ].value = f"시작 시간: {self.translation_stats['start_time'] or '미시작'}"

            # 폴더 열기 버튼 제거
            if len(self.status_info.controls) > 3:
                self.status_info.controls = self.status_info.controls[:3]

        try:
            self.page.update()
        except Exception as e:
            print(f"진행률 초기화 UI 업데이트 오류: {e}")

    def _open_output_folder(self, output_dir: str):
        """출력 폴더를 윈도우 탐색기로 열기"""
        try:
            import os
            import platform
            import subprocess

            print(f"폴더 열기 시도: {output_dir}")

            # 폴더가 실제로 존재하는지 확인
            if not os.path.exists(output_dir):
                error_msg = f"폴더가 존재하지 않습니다: {output_dir}"
                print(error_msg)
                self.add_log_message("ERROR", error_msg)
                return

            if platform.system() == "Windows":
                try:
                    subprocess.run(f'explorer "{output_dir}"', shell=True, check=True)
                except subprocess.CalledProcessError:
                    try:
                        os.startfile(output_dir)
                        print("os.startfile로 폴더 열기 성공")
                    except Exception as startfile_error:
                        print(f"os.startfile도 실패: {startfile_error}")
                        parent_dir = os.path.dirname(output_dir)
                        subprocess.run(
                            f'explorer /select,"{output_dir}"', shell=True, check=False
                        )
                        print("상위 폴더에서 선택하는 방식으로 실행")
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", output_dir], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", output_dir], check=True)

            self.add_log_message("SUCCESS", f"📁 탐색기로 폴더 열기 완료: {output_dir}")
            print("폴더 열기 성공")

        except Exception as e:
            print(f"폴더 열기 실패: {e}")
            self.add_log_message(
                "WARNING", f"폴더 열기 명령어 오류 (폴더는 열렸을 수 있음): {e}"
            )
