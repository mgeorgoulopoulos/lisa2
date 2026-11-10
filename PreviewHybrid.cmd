@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m lisa2.preview --run runs/hybrid-gouraud
