"""
EverFlow — Entry point.
Run: python main.py
Or double-click the packaged EverFlow.app / EverFlow.exe
"""
import sys
import os

# Ensure the project root is on sys.path regardless of how the app is launched.
# This is required for both development (python main.py) and
# PyInstaller-packaged builds.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix for PyInstaller windowed mode (console=False):
# Uvicorn and other libraries may crash if sys.stdout/stderr are None.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

from src.app import EverFlowApp


if __name__ == "__main__":
    app = EverFlowApp()
    app.run()