@echo off
cd /d D:\AI-Agent

call .venv\Scripts\activate.bat

start "" http://localhost:8765

python ai_tool/run_chat_ui.py

pause