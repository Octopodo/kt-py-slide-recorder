@echo off
setlocal
cd /d "%~dp0"

:: ── 1. Create virtual environment if it does not exist ─────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to create virtual environment. Make sure Python is in PATH.
        pause
        exit /b 1
    )
)

:: ── 2. Activate virtual environment ────────────────────────────────────
call .venv\Scripts\activate.bat

:: ── 3. Ensure dependencies are installed inside the venv ───────────────
.venv\Scripts\python.exe -c "import customtkinter, pynput" >nul 2>&1
if errorlevel 1 (
    echo Installing requirements...
    .venv\Scripts\pip.exe install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install requirements.
        pause
        exit /b 1
    )
)

:: ── 4. Launch without a console window ─────────────────────────────────
:: Use pythonw from the venv for a windowless launch; fall back to python.
if exist ".venv\Scripts\pythonw.exe" (
    start "" .venv\Scripts\pythonw.exe main.py
) else (
    start "" .venv\Scripts\python.exe main.py
)

endlocal
