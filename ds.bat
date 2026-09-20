@echo off
rem =============================================================================
rem ds.bat — devsweep launcher shortcut for Windows Command Prompt
rem =============================================================================
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0"
set "VENV_PYTHON=%ROOT_DIR%.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo.
    echo   [devsweep] First-time setup: Initialising virtual environment...
    echo.
    where python >nul 2>&1
    if errorlevel 1 (
        where py >nul 2>&1
        if errorlevel 1 (
            echo   [ERROR] Python is required but was not found in PATH.
            echo   Please install Python from https://python.org/downloads
            exit /b 1
        ) else (
            set "PY_CMD=py -3"
        )
    ) else (
        set "PY_CMD=python"
    )

    %PY_CMD% -m venv "%ROOT_DIR%.venv"
    if errorlevel 1 (
        echo   [ERROR] Failed to create virtual environment.
        exit /b 1
    )

    echo   [devsweep] Installing dependencies...
    if exist "%ROOT_DIR%requirements.txt" (
        "%ROOT_DIR%.venv\Scripts\pip.exe" install -r "%ROOT_DIR%requirements.txt" --quiet
    ) else (
        "%ROOT_DIR%.venv\Scripts\pip.exe" install "rich>=13.0.0" --quiet
    )
    echo   [devsweep] Setup complete!
    echo.
)

rem Map command shortcuts
if "%~1"=="help" (
    "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --help
) else if "%~1"=="scan" (
    "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --skip-projects
) else if "%~1"=="full" (
    if "%~2"=="" (
        "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py"
    ) else (
        "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --scan-projects "%~2"
    )
) else if "%~1"=="report" (
    if "%~2"=="" (
        "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --markdown audit-report.md --redact
    ) else (
        "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --markdown "%~2" --redact
    )
) else if "%~1"=="json" (
    if "%~2"=="" (
        "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --json audit-report.json --redact
    ) else (
        "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --json "%~2" --redact
    )
) else if "%~1"=="script" (
    if "%~2"=="" (
        "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --generate-script cleanup.ps1
    ) else (
        "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --generate-script "%~2"
    )
) else if "%~1"=="clean" (
    "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" --generate-script cleanup.ps1
    if exist "%ROOT_DIR%cleanup.ps1" (
        powershell -ExecutionPolicy Bypass -File "%ROOT_DIR%cleanup.ps1"
    )
) else (
    "%VENV_PYTHON%" "%ROOT_DIR%devsweep.py" %*
)
