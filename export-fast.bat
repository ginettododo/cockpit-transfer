@echo off
setlocal
set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"
pushd "%APP_DIR%"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m cockpit_transfer export-fast
) else (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 (
    python -m cockpit_transfer export-fast
  ) else (
    echo Python not found.
    echo Please install Python 3 and try again.
    echo.
    pause
    popd
    exit /b 1
  )
)
echo.
pause
popd
