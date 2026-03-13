@echo off
REM GEM Portal Automation - Disable Auto-Start on Windows
REM This removes the shortcut from the Startup folder

echo Disabling auto-start for GEM Portal Automation...
echo.

set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

if exist "%STARTUP_FOLDER%\GEM Portal Automation.lnk" (
    del "%STARTUP_FOLDER%\GEM Portal Automation.lnk"
    echo ✅ Auto-start disabled!
    echo.
    echo The application will no longer start automatically.
) else (
    echo Auto-start was not enabled.
)

echo.
pause
