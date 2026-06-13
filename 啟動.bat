@echo off
title Business Card Scanner

echo ================================
echo   Starting Business Card Scanner
echo ================================
echo.

cd /d "%~dp0"

echo Installing packages...
py -m pip install -r requirements.txt -q

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4.*192"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%

echo.
echo ================================
echo  Open on phone: http://%IP%:5000
echo ================================
echo.

py app.py
pause