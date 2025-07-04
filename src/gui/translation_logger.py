"""
번역 로그 관리 모듈
"""

import logging
import time
from datetime import datetime

import flet as ft


class TranslationLogger:
    """번역 로그 관리 클래스"""

    def __init__(self, page: ft.Page):
        self.page = page

        # 로그 관련
        self.log_messages = []
        self.max_log_messages = 100  # 로그 수 제한

        # UI 컴포넌트들 (외부에서 설정)
        self.log_container = None
        self.gui_log_handler = None

    def set_log_container(self, log_container: ft.ListView):
        """로그 컨테이너 설정"""
        self.log_container = log_container

    def setup_gui_log_handler(self):
        """GUI 로그 핸들러 설정"""
        # 기존 핸들러 제거 (중복 방지)
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, GUILogHandler):
                root_logger.removeHandler(handler)

        # 새로운 GUI 로그 핸들러 추가
        self.gui_log_handler = GUILogHandler(self.add_log_message)
        self.gui_log_handler.setLevel(logging.INFO)  # INFO 레벨 이상만 표시

        # 로그 포맷 설정
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        self.gui_log_handler.setFormatter(formatter)

        # 루트 로거에 추가
        root_logger.addHandler(self.gui_log_handler)

    def cleanup_log_handler(self):
        """로그 핸들러 제거 (메모리 누수 방지)"""
        try:
            if self.gui_log_handler:
                root_logger = logging.getLogger()
                root_logger.removeHandler(self.gui_log_handler)
                self.add_log_message("INFO", "로그 핸들러가 제거되었습니다")
        except Exception as e:
            print(f"로그 핸들러 제거 실패: {e}")

    def add_log_message(self, level: str, message: str):
        """로그 메시지 추가"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            level_upper = level.upper()
            log_entry = f"[{timestamp}] {level_upper}: {message}"

            # 디버깅용 콘솔 출력 (레벨에 따라 제한)
            if level_upper in ["ERROR", "WARNING", "SUCCESS"]:
                print(f"GUI LOG: {log_entry}")

            # 색상 설정 (레벨별로 다양화)
            color = ft.Colors.WHITE
            if level_upper == "ERROR":
                color = ft.Colors.RED_400
            elif level_upper == "WARNING":
                color = ft.Colors.ORANGE_400
            elif level_upper == "SUCCESS":
                color = ft.Colors.GREEN_400
            elif level_upper == "INFO":
                color = ft.Colors.LIGHT_BLUE_400
            elif level_upper == "DEBUG":
                color = ft.Colors.GREY_500
            else:
                color = ft.Colors.WHITE

            # 로그 메시지 생성 (줄바꿈 지원)
            log_text = ft.Text(
                log_entry,
                size=10,  # 더 작게
                color=color,
                selectable=True,
                text_align=ft.TextAlign.LEFT,
                width=360,  # 너비 제한으로 자동 줄바꿈
                no_wrap=False,  # 줄바꿈 허용
            )

            # 로그 컨테이너에 추가
            if self.log_container:
                self.log_messages.append(log_entry)

                # 최대 메시지 수 제한 (더 효율적으로)
                if len(self.log_messages) > self.max_log_messages:
                    # 오래된 메시지들 제거 (한 번에 많이 제거)
                    items_to_remove = 30
                    for _ in range(items_to_remove):
                        if self.log_messages:
                            self.log_messages.pop(0)
                        if len(self.log_container.controls) > 0:
                            self.log_container.controls.pop(0)

                self.log_container.controls.append(
                    ft.Container(
                        content=log_text,
                        padding=ft.padding.symmetric(vertical=2, horizontal=4),
                        width=380,  # 컨테이너 너비 고정
                        # height 제거 - 내용에 따라 자동 조정
                    )
                )

                # 자동 스크롤 (더 부드럽게)
                try:
                    if hasattr(self.log_container, "scroll_to"):
                        self.log_container.scroll_to(offset=-1, duration=50)
                except:
                    pass

                # UI 업데이트 (빈도 제한)
                try:
                    # 중요한 메시지나 5개마다 한 번씩만 UI 업데이트
                    if (
                        level_upper in ["ERROR", "WARNING", "SUCCESS"]
                        or len(self.log_container.controls) % 5 == 0
                    ):
                        self.page.update()
                except Exception:
                    # UI 업데이트 오류는 무시 (로그가 더 중요)
                    pass
        except Exception as e:
            print(f"로그 메시지 추가 오류: {e}")

    def clear_logs(self):
        """로그 지우기"""
        if self.log_container:
            self.log_container.controls.clear()
            self.log_messages.clear()
            self.page.update()
            self.add_log_message("INFO", "로그가 지워졌습니다.")

    def save_logs(self, modpack_name: str = "Unknown"):
        """로그 저장"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"translation_log_{timestamp}.txt"

            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"번역 로그 - {modpack_name}\n")
                f.write(f"저장 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                for message in self.log_messages:
                    f.write(message + "\n")

            self.add_log_message("INFO", f"로그가 저장되었습니다: {log_file}")

        except Exception as error:
            self.add_log_message("ERROR", f"로그 저장 실패: {error}")

    def get_log_summary(self) -> dict:
        """로그 요약 정보 반환"""
        summary = {
            "total_messages": len(self.log_messages),
            "error_count": 0,
            "warning_count": 0,
            "success_count": 0,
            "info_count": 0,
        }

        for message in self.log_messages:
            if "ERROR:" in message:
                summary["error_count"] += 1
            elif "WARNING:" in message:
                summary["warning_count"] += 1
            elif "SUCCESS:" in message:
                summary["success_count"] += 1
            elif "INFO:" in message:
                summary["info_count"] += 1

        return summary

    def add_initial_logs(self, modpack_name: str):
        """초기 로그 메시지들 추가"""
        self.add_log_message("INFO", "번역 페이지가 초기화되었습니다.")
        self.add_log_message("INFO", f"모드팩: {modpack_name}")
        self.add_log_message("INFO", "설정을 확인하고 번역 시작 버튼을 클릭하세요.")


class GUILogHandler(logging.Handler):
    """GUI에 로그를 전달하는 핸들러 (개선된 버전)"""

    def __init__(self, add_log_callback):
        super().__init__()
        self.add_log_callback = add_log_callback
        self._in_emit = False  # 무한 루프 방지
        self._last_messages = {}  # 중복 메시지 방지
        self._message_count = {}  # 메시지 카운트
        self._last_emit_time = time.time()

    def emit(self, record):
        try:
            # 무한 루프 방지
            if self._in_emit:
                return

            # 너무 빈번한 호출 방지 (100ms 제한)
            current_time = time.time()
            if current_time - self._last_emit_time < 0.1:
                return
            self._last_emit_time = current_time

            self._in_emit = True

            # GUI 관련 로그는 제외
            if record.name.startswith("src.gui") or record.name.startswith("flet"):
                return

            level = record.levelname.upper()
            message = self.format(record)

            # 중복 메시지 체크 및 카운팅
            message_key = f"{record.name}:{record.levelname}:{record.getMessage()}"

            if message_key in self._last_messages:
                # 중복 메시지인 경우 카운트만 증가
                self._message_count[message_key] = (
                    self._message_count.get(message_key, 1) + 1
                )

                # 10개마다 한 번씩만 표시
                if self._message_count[message_key] % 10 == 0:
                    count_message = f"{message} (x{self._message_count[message_key]})"
                    self.add_log_callback(level, count_message)
            else:
                # 새로운 메시지
                self._last_messages[message_key] = message
                self._message_count[message_key] = 1
                self.add_log_callback(level, message)

                # 메시지 히스토리 정리 (100개 이상이면 오래된 것 제거)
                if len(self._last_messages) > 100:
                    # 가장 오래된 50개 제거
                    keys_to_remove = list(self._last_messages.keys())[:50]
                    for key in keys_to_remove:
                        self._last_messages.pop(key, None)
                        self._message_count.pop(key, None)

        except Exception:
            # 로그 전달 실패는 무시 (무한 루프 방지)
            pass
        finally:
            self._in_emit = False
