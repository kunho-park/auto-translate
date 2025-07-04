"""
메인 애플리케이션 진입점

GUI 모듈들을 통합하여 모드팩 번역기를 실행합니다.
"""

import logging
import os
import sys

import flet as ft

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.gui import ModpackBrowser, TranslationPage

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MainApp:
    """메인 애플리케이션 클래스"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.current_view = "browser"

        # GUI 컴포넌트들
        self.browser = ModpackBrowser(page)
        self.translation_page = TranslationPage(page)

        # 콜백 설정
        self.browser.set_translation_callback(self.show_translation_page)
        self.translation_page.set_back_callback(self.show_browser_page)

    async def show_translation_page(self, modpack_info):
        """번역 페이지로 이동"""
        logger.info(f"번역 페이지로 이동: {modpack_info.get('name', 'Unknown')}")

        self.current_view = "translation"
        self.translation_page.set_modpack(modpack_info)
        self.translation_page.build_ui()

    async def show_browser_page(self):
        """브라우저 페이지로 돌아가기"""
        logger.info("브라우저 페이지로 돌아가기")

        self.current_view = "browser"

        # 페이지 정리
        self.page.clean()

        # 브라우저 UI 재구성
        self.browser.build_main_ui()

        # 모드팩 그리드 업데이트
        await self.browser.update_modpack_grid()


async def main(page: ft.Page):
    """메인 애플리케이션 진입점"""
    # 앱 초기화
    app = MainApp(page)

    # 모드팩 로딩 시작
    await app.browser.load_modpacks()


# Flet 권장사항에 따라 앱 실행
if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
