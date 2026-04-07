@echo off
setlocal
set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"
pushd "%APP_DIR%"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m transferimento_cockpits import-fast
) else (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 (
    python -m transferimento_cockpits import-fast
  ) else (
    echo Python non trovato.
    echo Installa Python 3 e riprova.
    echo.
    pause
    popd
    exit /b 1
  )
)
echo.
pause
popd
