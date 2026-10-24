@echo off
rem Local model menu. Other command-line options are passed to setup.py unchanged.
setlocal EnableExtensions DisableDelayedExpansion
rem Python reads and writes text as UTF-8, including non-ASCII folder and user names (#3202).
set "PYTHONUTF8=1"
title Strata
cd /d "%~dp0"
if errorlevel 1 exit /b 1
set "MODE=run"
set "MODEL="
if "%~1"=="" goto menu
if /i "%~1"=="--local-setup" (
    set "MODE=setup"
    goto menu
)
if /i "%~1"=="--local-model" (
    set "MODEL=%~2"
    goto select
)
goto installer

:menu
echo.
echo  ========================================================
echo   Strata - local models [%MODE%]
echo    [1] IQ3_S       Qwen GSQ-RCO        - new
echo    [2] UD-IQ4_XS   Qwen Unsloth        - new
echo    [3] IQ2_XS      Qwen GSQ-RCO        - existing
echo    [4] IQ2_XXS     Orca uncensored     - existing
echo    [Q] Quit
echo  ========================================================
echo  IQ3_S / UD-IQ4_XS may use SSD paging on 48 GB RAM.
echo  Close the running model before starting another one.
echo.
choice /c 1234Q /n /m "Select (1/2/3/4/Q): "
if errorlevel 255 exit /b 1
if errorlevel 5 exit /b 0
if errorlevel 4 (
    set "MODEL=orca-iq2_xxs"
    goto select
)
if errorlevel 3 (
    set "MODEL=iq2_xs"
    goto select
)
if errorlevel 2 (
    set "MODEL=unsloth-ud-iq4_xs"
    goto select
)
if errorlevel 1 (
    set "MODEL=iq3_s"
    goto select
)
exit /b 1

:select
set "FAMILY=qwen"
set "GGUF_DIR=%~dp0..\Strata-data\models"
if /i "%MODEL%"=="iq3_s" goto iq3_s
if /i "%MODEL%"=="unsloth-ud-iq4_xs" goto iq4_xs
if /i "%MODEL%"=="iq2_xs" goto iq2_xs
if /i "%MODEL%"=="orca-iq2_xxs" goto orca
echo  Unknown local model. Use iq3_s, unsloth-ud-iq4_xs, iq2_xs or orca-iq2_xxs.
exit /b 2

:iq3_s
set "MODEL=iq3_s"
set "QUANT=IQ3_S"
set "STEM=Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S"
set "SHARDS=00002"
goto local

:iq4_xs
set "MODEL=unsloth-ud-iq4_xs"
set "FAMILY=unsloth"
set "QUANT=UD-IQ4_XS"
set "STEM=Qwen3.8-Flash-Next-UD-IQ4_XS"
set "SHARDS=00003"
goto local

:iq2_xs
set "MODEL=iq2_xs"
set "QUANT=IQ2_XS"
set "GGUF_DIR=%GGUF_DIR%\IQ2_XS"
set "STEM=Qwen3.8-Flash-Next-GSQ-RCO-IQ2_XS"
set "SHARDS=00002"

:local
for %%S in (00001 00002) do if not exist "%GGUF_DIR%\%STEM%-%%S-of-%SHARDS%.gguf" goto missing_shards
if "%SHARDS%"=="00003" if not exist "%GGUF_DIR%\%STEM%-00003-of-00003.gguf" goto missing_shards
if "%MODE%"=="setup" goto prepare
if not exist "strata-%MODEL%.json" goto prepare
if not exist "..\Strata-data\packs\%MODEL%\native_experts.txt" goto prepare
goto serve

:prepare
echo.
echo  Preparing %QUANT% from local GGUF files. Model shards will not be downloaded.
echo  This needs extra disk space; missing support files may be downloaded.
echo  Large models may run slower when experts must be read from SSD.
call :ensure_python
if errorlevel 1 goto failed
"%LOCAL_PYTHON%" setup.py --setup --yes --family "%FAMILY%" --model "%QUANT%" --gguf-dir "%GGUF_DIR%" --data-dir "%~dp0..\Strata-data" --cuda 12 --low-ram auto --context 131072 --vision no --port 8080 --no-start
if errorlevel 1 goto failed
if "%MODE%"=="setup" (
    echo  Setup finished. Use START-HERE.bat to start the model.
    pause
    exit /b 0
)
goto serve

:orca
set "MODEL=orca-iq2_xxs"
if not exist "strata-orca-iq2_xxs.json" goto missing_orca
if not exist "..\Strata-data\packs\orca-iq2_xxs\native_experts.txt" goto missing_orca
if "%MODE%"=="setup" (
    echo  Orca uses its existing custom config and BF16 embedding fix.
    echo  It is not supported by the standard setup menu. See docs\ORCA.md.
    pause
    goto menu
)

:serve
call :ensure_python
if errorlevel 1 goto failed
"%LOCAL_PYTHON%" -m serve.server --engine strata --config "strata-%MODEL%.json" --host 127.0.0.1 --port 8080 --open
if errorlevel 1 goto failed
exit /b 0

:installer
call :ensure_python
if errorlevel 1 goto failed
"%LOCAL_PYTHON%" setup.py %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%

:missing_shards
echo  Missing model shards: %GGUF_DIR%\%STEM%-*-of-%SHARDS%.gguf
echo  Put every shard in that folder, then try again.
goto failed

:missing_orca
echo  Orca config or pack is missing. Restore the old installation; see docs\ORCA.md.
goto failed

:failed
echo  Strata could not complete this action. See the error above.
pause
exit /b 1

:ensure_python
rem Prefer the bundled runtime when present, without downloading or creating a venv.
set "LOCAL_PYTHON=python\python.exe"
if exist "%LOCAL_PYTHON%" goto bundled
set "LOCAL_PYTHON=.venv\Scripts\python.exe"
if exist "%LOCAL_PYTHON%" exit /b 0
call :findpy
if defined PY goto venv
echo  Installing Python 3.12 for your user account ...
where winget >nul 2>nul
if errorlevel 1 goto pyorg
winget install -e --id Python.Python.3.12 --scope user --silent --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
call :findpy
if defined PY goto venv
:pyorg
echo  Downloading the Python installer from python.org ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe -OutFile \"$env:TEMP\strata-python-setup.exe\""
if errorlevel 1 exit /b 1
"%TEMP%\strata-python-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
call :findpy
if not defined PY (
    echo  Install 64-bit Python 3.12 from https://www.python.org/downloads/ then try again.
    exit /b 1
)
:venv
%PY% -m venv .venv
if exist ".venv\Scripts\python.exe" exit /b 0
echo  Could not create the Python environment in .venv
exit /b 1

:bundled
set "PYTHONNOUSERSITE=1"
set "PYTHONHOME="
set "PYTHONPATH="
exit /b 0

:findpy
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) and sys.maxsize > 2**32 else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3"
    exit /b 0
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) and sys.maxsize > 2**32 else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    exit /b 0
)
for %%V in (313 312 311 310) do if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
    set "PY="%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe""
    exit /b 0
)
exit /b 0
