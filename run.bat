@echo off
setlocal

REM Run from the folder this .bat file is in (project root)
cd /d "%~dp0"

REM Ensure logs folder exists
if not exist "data\run_logs" mkdir "data\run_logs"

REM Run and log output
"C:\Users\jake4\AppData\Local\Microsoft\WindowsApps\python3.12.exe" "%~dp0main.py" >> "%~dp0data\run_logs\run.log" 2>&1
