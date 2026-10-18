@echo off
rem Double-click to configure a local model; explicit options go to setup.py.
if "%~1"=="" (
    call "%~dp0START-HERE.bat" --local-setup
) else (
    call "%~dp0START-HERE.bat" --setup %*
)
exit /b %ERRORLEVEL%
