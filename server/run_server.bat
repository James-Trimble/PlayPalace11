@echo off
echo Starting Play Palace v11 Server...
echo.
uv sync
uv run python main.py
pause
