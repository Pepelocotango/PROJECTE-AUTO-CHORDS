@echo off
rem Llançador d'AUTO CHORDS per a Windows (equivalent a AUTO_CHORDS.sh).
rem Les DLL natives (Vamp + libsndfile + codecs) no són al costat de
rem vamp_host_local.exe, a portable\win-dlls: cal posar-les al PATH o
rem l'anàlisi (F5/F7) falla amb STATUS_DLL_NOT_FOUND (0xC0000135).

setlocal
cd /d "%~dp0"

set "PATH=%CD%\portable\win-dlls;%PATH%"
set "PYTHONUTF8=1"

if exist "%CD%\.venv\Scripts\python.exe" (
    set "PY=%CD%\.venv\Scripts\python.exe"
) else (
    set "PY=py"
)

"%PY%" -m app.main %*
set "RC=%ERRORLEVEL%"

endlocal
exit /b %RC%
