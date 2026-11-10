@echo off
cd /d "%~dp0"
if exist "runs\dos640\control.txt" echo run>"runs\dos640\control.txt"
".venv\Scripts\python.exe" -m lisa2.train --resume --objective rgb --mutation uniform --mutation-space world %*
