@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=C:\Users\karee\AppData\Local\Programs\Python\Python312\python.exe"
set "GOOGLE_APPLICATION_CREDENTIALS="

for %%K in ("%USERPROFILE%\Downloads\ieee-attendance-*.json") do (
    if exist "%%~fK" set "GOOGLE_APPLICATION_CREDENTIALS=%%~fK"
)

if not defined GOOGLE_APPLICATION_CREDENTIALS (
    echo Firebase service-account JSON was not found in:
    echo %USERPROFILE%\Downloads
    echo Download it from Firebase Project settings ^> Service accounts.
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo Python 3.12 was not found at:
    echo %PYTHON%
    pause
    exit /b 1
)

echo Downloading attendance data from Firebase...
"%PYTHON%" export_attendance_firebase.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Attendance download completed.
    echo Output file: attendance_export.csv
) else (
    echo Attendance download failed with code %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%
