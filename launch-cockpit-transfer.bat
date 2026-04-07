@echo off
setlocal
set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"
where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
  start "" /D "%TEMP%" pythonw "%APP_DIR%\main.pyw"
) else (
  where pyw >nul 2>nul
  if %ERRORLEVEL%==0 (
    start "" /D "%TEMP%" pyw "%APP_DIR%\main.pyw"
  ) else (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
      start "" /D "%TEMP%" py -3 "%APP_DIR%\main.pyw"
    ) else (
      where python >nul 2>nul
      if %ERRORLEVEL%==0 (
        start "" /D "%TEMP%" python "%APP_DIR%\main.pyw"
      ) else (
        echo Python not found.
        echo Please install Python 3 and then reopen this folder.
        pause
      )
    )
  )
)
