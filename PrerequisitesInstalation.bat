@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title OpenYTPlayer - Requirements installation

echo ============================================
echo  OpenYTPlayer - Requirements installation
echo ============================================
echo.
echo  This script gets a fresh Windows ready to
echo  double-click start.py / start.pyw.
echo.

REM ---------- [1/4] Locate Python ----------
set "PY="
set "PYW="
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py"
)
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    set "PY=python"
  )
)
if defined PY (
  echo [1/4] Python found: %PY%
  %PY% --version
) else (
  echo [1/4] Python not found. Trying to install Python 3.12 with winget...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo   ERROR: no winget available. Install Python 3.11 or newer manually:
    echo   https://www.python.org/downloads/
    echo   Check "Add python.exe to PATH" and "py launcher" in the installer,
    echo   then run this .bat again.
    pause
    exit /b 1
  )
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  if errorlevel 1 (
    echo   ERROR: winget installation failed. Install it manually:
    echo   https://www.python.org/downloads/
    pause
    exit /b 1
  )
  echo   Python installed. Looking for it again...
  set "PY="
  if exist "%LocalAppData%\Programs\Python\Launcher\py.exe" (
    set "PY=%LocalAppData%\Programs\Python\Launcher\py.exe"
  )
  if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 set "PY=py"
  )
  if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 set "PY=python"
  )
  if not defined PY (
    echo   Python was installed but is still not on the PATH.
    echo   Close this window, open a new one and run this .bat again.
    pause
    exit /b 1
  )
  echo   Python ready: %PY%
  %PY% --version
)
echo.

REM ---------- [2/4] Upgrade pip ----------
echo [2/4] Upgrading pip...
%PY% -m pip install --upgrade pip
if errorlevel 1 (
  echo   WARNING: pip could not be upgraded, continuing anyway.
)
echo.

REM ---------- [3/4] Install dependencies ----------
echo [3/4] Installing dependencies (requirements.txt)...
if not exist requirements.txt (
  echo   ERROR: requirements.txt was not found next to this .bat.
  pause
  exit /b 1
)
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo   ERROR: dependency installation failed.
  echo   Check your connection and run this .bat again.
  pause
  exit /b 1
)
echo   Dependencies installed.
echo.

REM ---------- [4/4] Verify ----------
echo [4/4] Verifying installation...
%PY% -c "import yt_dlp, ytmusicapi, PIL, pygame, requests, imageio, sounddevice, numpy, selenium; print('  All dependencies import OK')"
if errorlevel 1 (
  echo.
  echo   ERROR: some dependency does not import. Reinstall with:
  echo   %PY% -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo.
echo ============================================
echo  ALL DONE.
echo ============================================
echo.
echo  - Double-click start.pyw  = opens WITHOUT console (recommended).
echo  - Double-click start.py   = also opens without console
echo    (it relaunches itself with pythonw if the theme has ocultar_consola).
echo  - If you ever want to see the console:
echo    %PY% start.py --consola
echo.
pause
exit /b 0
