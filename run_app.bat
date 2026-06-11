@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo The application is not set up yet.
  echo Starting setup...
  call "%~dp0setup.bat"
  if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app\main.py
