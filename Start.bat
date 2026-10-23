@echo off
setlocal
cd /d "%~dp0"
title Tilbud

rem 1) Anaconda / Miniconda: find it and activate it, because double-clicking does not do that by itself
set "ACT="
for %%D in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "%LOCALAPPDATA%\anaconda3" "%LOCALAPPDATA%\miniconda3" "%ProgramData%\anaconda3" "%ProgramData%\miniconda3" "C:\anaconda3" "C:\miniconda3") do (
  if not defined ACT if exist "%%~D\Scripts\activate.bat" set "ACT=%%~D"
)
if defined ACT (
  echo Using conda in %ACT%
  call "%ACT%\Scripts\activate.bat" "%ACT%"
  python app.py
  goto :done
)

rem 2) a normal Python install
where python >nul 2>nul
if not errorlevel 1 (
  python app.py
  goto :done
)
where py >nul 2>nul
if not errorlevel 1 (
  py app.py
  goto :done
)

echo Could not find Python or Anaconda.
echo Open "Anaconda Prompt" and run:  where python
echo and send the answer to Claude.
pause
exit /b 1

:done
if errorlevel 1 (
  echo.
  echo The window did not start. The message above says why - send it to Claude.
  pause
)
