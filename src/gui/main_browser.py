"""
메인 모드팩 브라우저 GUI
"""

import json
import logging
import os
import webbrowser

import flet as ft

from ..localization.messages import get_message, set_language
from .components import create_modpack_card

logger = logging.getLogger(__name__)


class ModpackBrowser:
    def __init__(self, page: ft.Page):
        self.page = page
        self.modpacks = []
        self.selected_modpack = None
        self.current_view = "main"  # "main" or "detail"
        self.current_language = "ko"  # Default language

        # UI components
        self.modpack_grid = None
        self.theme_button = None
        self.language_dropdown = None
        self.search_field = None
        self.filtered_modpacks = []
        self.main_content = None
        self.detail_content = None

        # 번역 페이지 콜백
        self.on_translation_start = None

        # Setup page
        self.setup_page()
        self.build_main_ui()

        # Load modpacks after page is ready
        self.page.on_resize = self.on_page_resize

    def setup_page(self):
        """Configure page settings"""
        set_language(self.current_language)

        self.page.title = get_message("gui.app_title")
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 1200
        self.page.window_height = 800
        self.page.padding = 20
        self.page.scroll = ft.ScrollMode.AUTO

    def build_main_ui(self):
        """Build the main UI (modpack browser)"""
        # Language dropdown
        self.language_dropdown = ft.Dropdown(
            label=get_message("gui.button.language"),
            options=[
                ft.dropdown.Option(key="en", text=get_message("gui.language.english")),
                ft.dropdown.Option(key="ko", text=get_message("gui.language.korean")),
            ],
            value=self.current_language,
            on_change=self.on_language_change,
            width=150,
        )

        # Theme toggle button
        self.theme_button = ft.IconButton(
            icon=ft.Icons.LIGHT_MODE,
            tooltip=get_message("gui.button.theme_toggle"),
            on_click=self.toggle_theme,
        )

        # Search field
        self.search_field = ft.TextField(
            hint_text=get_message("gui.search_hint"),
            prefix_icon=ft.Icons.SEARCH,
            on_change=self.on_search_change,
            width=300,
        )

        # Modpack grid view
        self.modpack_grid = ft.GridView(
            expand=True,
            runs_count=0,  # Auto-fit based on width
            max_extent=220,  # Increased width for better layout
            child_aspect_ratio=0.65,  # Height/Width ratio adjusted for new card height
            spacing=20,
            run_spacing=20,
        )

        # Main layout - full width now
        self.main_content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            get_message("gui.title_main"),
                            size=32,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(expand=True),  # Spacer
                        self.search_field,
                        ft.Container(width=15),  # Spacing
                        self.language_dropdown,
                        ft.Container(width=15),  # Spacing
                        self.theme_button,
                    ]
                ),
                ft.Divider(),
                ft.Container(
                    content=self.modpack_grid,
                    expand=True,
                    border_radius=10,
                    padding=15,
                ),
            ],
            expand=True,
            spacing=10,
        )

        self.page.add(
            ft.Container(
                content=self.main_content,
                expand=True,
            )
        )

    async def on_page_resize(self, e):
        """Handle page resize events"""
        pass

    async def load_modpacks(self):
        """Load modpacks asynchronously by running the blocking part in an executor."""
        success, message = await self.page.loop.run_in_executor(
            None, self._load_modpacks_blocking
        )
        if success:
            await self.update_modpack_grid()
        else:
            await self.show_error_async(message)

    def _load_modpacks_blocking(self):
        """Load modpacks synchronously (blocking). This should only perform I/O and data processing."""
        curseforge_path = os.path.join(
            os.path.expanduser("~"), "curseforge", "minecraft", "Instances"
        )
        logger.info(f"Scanning for modpacks in: {curseforge_path}")

        if not os.path.exists(curseforge_path):
            logger.warning(f"Directory not found: {curseforge_path}")
            return (
                False,
                "모드팩 디렉토리를 찾을 수 없습니다.\nCurseForge 설치 경로를 확인해주세요.",
            )

        modpacks_loaded = 0
        self.modpacks.clear()
        for dir_name in os.listdir(curseforge_path):
            modpack_path = os.path.join(curseforge_path, dir_name)
            if not os.path.isdir(modpack_path):
                continue

            modpack_info = self.parse_modpack_data(modpack_path)
            if modpack_info:
                self.modpacks.append(modpack_info)
                modpacks_loaded += 1

        # Set filtered modpacks to all modpacks initially
        self.filtered_modpacks = self.modpacks.copy()

        logger.info(f"Finished scanning. Loaded {modpacks_loaded} modpacks.")

        if modpacks_loaded == 0:
            return (
                False,
                "모드팩을 찾을 수 없습니다.\nCurseForge 설치 경로를 확인해주세요.",
            )

        return True, ""

    async def toggle_theme(self, e):
        """Toggle between light and dark theme"""
        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.theme_button.icon = ft.Icons.DARK_MODE
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
            self.theme_button.icon = ft.Icons.LIGHT_MODE
        self.page.update()

    async def on_search_change(self, e):
        """Handle search input change"""
        search_term = e.control.value.lower()

        # Filter modpacks based on search term
        if search_term:
            self.filtered_modpacks = [
                modpack
                for modpack in self.modpacks
                if search_term in modpack.get("name", "").lower()
                or search_term in modpack.get("author", "").lower()
            ]
        else:
            self.filtered_modpacks = self.modpacks.copy()

        # Update grid
        await self.update_modpack_grid()

    async def update_modpack_grid(self):
        """Update the modpack grid with filtered results"""
        self.modpack_grid.controls.clear()

        for modpack_info in self.filtered_modpacks:
            card = create_modpack_card(modpack_info, self.show_modpack_detail)
            self.modpack_grid.controls.append(card)

        self.page.update()

    async def on_language_change(self, e):
        """Handle language change"""
        new_language = e.control.value
        if new_language != self.current_language:
            self.current_language = new_language
            set_language(new_language)

            # Update page title
            self.page.title = get_message("gui.app_title")

            # Rebuild UI based on current view
            if self.current_view == "main":
                self.page.clean()
                self.build_main_ui()
                await self.update_modpack_grid()
            else:
                self.page.clean()
                self.build_detail_ui()

            self.page.update()

    def parse_modpack_data(self, instance_dir):
        """Parse modpack data from manifest.json and minecraftinstance.json"""
        modpack_info = {}

        # Try manifest.json first (contains reliable modpack info)
        manifest_path = os.path.join(instance_dir, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)

                modpack_info["name"] = manifest_data.get("name", "Unknown")
                modpack_info["author"] = manifest_data.get("author", "Unknown")
                modpack_info["modpack_version"] = manifest_data.get(
                    "version", "Unknown"
                )
                modpack_info["version"] = manifest_data.get("minecraft", {}).get(
                    "version", "Unknown"
                )
                modpack_info["path"] = instance_dir
                modpack_info["thumbnail_url"] = ""
                modpack_info["website_url"] = ""
                modpack_info["last_updated"] = "Unknown"

                logger.info(
                    f"Parsed manifest.json for {modpack_info['name']}: author={modpack_info['author']}, version={modpack_info['modpack_version']}"
                )

            except Exception as e:
                logger.error(f"Error parsing manifest.json in {instance_dir}: {e}")

        # Complement with minecraftinstance.json for additional info
        instance_json_path = os.path.join(instance_dir, "minecraftinstance.json")
        if os.path.exists(instance_json_path):
            try:
                with open(instance_json_path, "r", encoding="utf-8") as f:
                    instance_data = json.load(f)

                # Use instance name if manifest name is not available or is Unknown
                if not modpack_info.get("name") or modpack_info["name"] == "Unknown":
                    modpack_info["name"] = instance_data.get("name", "Unknown")

                # Get additional info from installedModpack if available
                installed_modpack = instance_data.get("installedModpack")
                if installed_modpack:
                    # Only override if we don't have better info from manifest
                    if modpack_info.get("author") == "Unknown" or not modpack_info.get(
                        "author"
                    ):
                        modpack_info["author"] = installed_modpack.get(
                            "author", modpack_info.get("author", "Unknown")
                        )

                    # Get thumbnail and website from installed modpack
                    modpack_info["thumbnail_url"] = installed_modpack.get(
                        "thumbnailUrl", ""
                    )
                    modpack_info["website_url"] = installed_modpack.get(
                        "websiteUrl", ""
                    )

                    # Parse last updated
                    installed_file = installed_modpack.get("installedFile")
                    if installed_file:
                        modpack_info["last_updated"] = installed_file.get(
                            "fileDate", "Unknown"
                        )

                # Get minecraft version from baseModLoader if not available
                if (
                    not modpack_info.get("version")
                    or modpack_info["version"] == "Unknown"
                ):
                    base_mod_loader = instance_data.get("baseModLoader")
                    if base_mod_loader:
                        modpack_info["version"] = base_mod_loader.get(
                            "minecraftVersion", "Unknown"
                        )

                logger.info(
                    f"Enhanced with minecraftinstance.json for {modpack_info['name']}"
                )

            except Exception as e:
                logger.error(
                    f"Error parsing minecraftinstance.json in {instance_dir}: {e}"
                )

        # Fallback if no files were successfully parsed
        if not modpack_info:
            # Extract folder name as last resort
            folder_name = os.path.basename(instance_dir)
            modpack_info = {
                "name": folder_name,
                "author": "Unknown",
                "modpack_version": "Unknown",
                "version": "Unknown",
                "path": instance_dir,
                "thumbnail_url": "",
                "website_url": "",
                "last_updated": "Unknown",
            }
            logger.warning(
                f"No parseable files found for {folder_name}, using folder name"
            )

        return modpack_info

    def show_modpack_detail(self, modpack_info):
        """Show modpack detail page"""
        self.selected_modpack = modpack_info
        self.current_view = "detail"
        # Run the async UI update in the background
        self.page.run_task(self._show_modpack_detail_async)

    async def _show_modpack_detail_async(self):
        """Async part of showing modpack detail page"""
        # Clear the current page
        self.page.clean()

        # Build detail page
        self.build_detail_ui()
        self.page.update()

    def build_detail_ui(self):
        """Build the detail page UI"""
        modpack_info = self.selected_modpack

        # Language dropdown for detail page
        language_dropdown = ft.Dropdown(
            label=get_message("gui.button.language"),
            options=[
                ft.dropdown.Option(key="en", text=get_message("gui.language.english")),
                ft.dropdown.Option(key="ko", text=get_message("gui.language.korean")),
            ],
            value=self.current_language,
            on_change=self.on_language_change,
            width=150,
        )

        # Header with back button
        header = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip=get_message("gui.button.back"),
                    on_click=self.go_back_to_main,
                ),
                ft.Text(
                    modpack_info.get("name", "Unknown"),
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    expand=True,
                ),
                language_dropdown,
                ft.Container(width=15),  # Spacing
                self.theme_button,
            ]
        )

        # Modpack image
        thumbnail_url = modpack_info.get("thumbnail_url", "")
        if thumbnail_url and thumbnail_url.startswith("http"):
            try:
                modpack_image = ft.Image(
                    src=thumbnail_url,
                    width=300,
                    height=300,
                    fit=ft.ImageFit.COVER,
                    border_radius=15,
                )
            except:
                modpack_image = ft.Icon(
                    ft.Icons.EXTENSION,
                    size=150,
                )
        else:
            modpack_image = ft.Icon(
                ft.Icons.EXTENSION,
                size=150,
            )

        # Modpack details
        details_column = ft.Column(
            [
                ft.Text(
                    get_message("gui.section.modpack_info"),
                    size=24,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(),
                ft.Text(
                    f"{get_message('gui.label.author')}: {modpack_info.get('author', 'Unknown')}",
                    size=16,
                ),
                ft.Text(
                    f"{get_message('gui.label.modpack_version')}: {modpack_info.get('modpack_version', 'Unknown')}",
                    size=16,
                ),
                ft.Text(
                    f"{get_message('gui.label.minecraft_version')}: {modpack_info.get('version', 'Unknown')}",
                    size=16,
                ),
                ft.Text(
                    f"{get_message('gui.label.last_updated')}: {modpack_info.get('last_updated', 'Unknown')}",
                    size=16,
                ),
                ft.Container(height=20),
                ft.Text(
                    get_message("gui.label.path"),
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    modpack_info.get("path", "Unknown"),
                    size=14,
                    selectable=True,
                ),
            ],
            spacing=8,
        )

        # Action buttons
        actions = ft.Column(
            [
                ft.Container(height=20),
                ft.ElevatedButton(
                    get_message("gui.button.start_translation"),
                    icon=ft.Icons.TRANSLATE,
                    on_click=self.start_translation,
                    width=200,
                    height=50,
                ),
            ]
        )

        # Add website button if available
        if modpack_info.get("website_url"):
            actions.controls.insert(
                1,
                ft.ElevatedButton(
                    get_message("gui.button.visit_website"),
                    icon=ft.Icons.OPEN_IN_NEW,
                    on_click=self.open_website,
                    width=200,
                    height=50,
                ),
            )

        # Main content layout
        content = ft.Column(
            [
                header,
                ft.Divider(),
                ft.Row(
                    [
                        ft.Container(
                            content=modpack_image,
                            padding=20,
                        ),
                        ft.Container(
                            content=details_column,
                            expand=True,
                            padding=20,
                        ),
                        ft.Container(
                            content=actions,
                            padding=20,
                        ),
                    ],
                    expand=True,
                ),
            ],
            expand=True,
            spacing=10,
        )

        self.detail_content = ft.Container(
            content=content,
            padding=25,
            expand=True,
        )

        self.page.add(self.detail_content)

    async def go_back_to_main(self, e):
        """Go back to main modpack browser"""
        self.current_view = "main"

        # Clear the current page
        self.page.clean()

        # Rebuild main UI
        self.build_main_ui()

        # Restore modpack grid
        await self.update_modpack_grid()

        self.page.update()

    async def open_website(self, e):
        """Open modpack website asynchronously."""
        if self.selected_modpack and self.selected_modpack.get("website_url"):
            await self.page.loop.run_in_executor(
                None, webbrowser.open, self.selected_modpack["website_url"]
            )

    async def start_translation(self, e):
        """Start translation process"""
        if self.selected_modpack and self.on_translation_start:
            # 번역 페이지로 이동
            await self.on_translation_start(self.selected_modpack)

    async def show_error_async(self, message):
        """Show error message in a snackbar."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.colors.ERROR,
        )
        self.page.snack_bar.open = True
        self.page.update()

    def set_translation_callback(self, callback):
        """번역 시작 콜백 설정"""
        self.on_translation_start = callback
