@echo off
cd /d "%~dp0"
echo Starting Play Palace v11 Client...
echo.
.venv\Scripts\python.exe client.py
if errorlevel 1 (
    echo.
    echo Error: Client failed to start.
    echo Check that dependencies are installed: .venv\Scripts\pip.exe install -e .
)
pause
