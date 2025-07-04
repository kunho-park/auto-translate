#!/usr/bin/env python3
"""
Flet GUI Launcher for Auto-Translate Modpack Browser
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import and run the Flet GUI using the new main.py structure
import flet as ft

from src.main import main

if __name__ == "__main__":
    print("🚀 Starting Flet Modpack Browser...")
    ft.app(target=main, assets_dir="assets")
