@echo off
setlocal
cd /d "%~dp0"

:: ── Activate virtual environment if one exists ─────────────────────────
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: ── Ensure dependencies are installed ──────────────────────────────────
python -c "import customtkinter, pynput" >nul 2>&1
if errorlevel 1 (
    echo Installing requirements...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install requirements. Make sure Python is in PATH.
        pause
        exit /b 1
    )
)

:: ── Launch without a console window ────────────────────────────────────
:: pythonw.exe is the windowless Python interpreter on Windows.
:: Fall back to python if pythonw is not available.
where pythonw >nul 2>&1
if errorlevel 1 (
    start "" python main.py
) else (
    start "" pythonw main.py
)

endlocal
