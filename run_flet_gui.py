import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import flet as ft

from src.main import main

if __name__ == "__main__":
    print("🚀 Starting Flet Modpack Browser...")
    ft.app(target=main, assets_dir="assets")
