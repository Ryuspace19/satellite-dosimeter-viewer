$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Assert-LastExitCode {
    param([string]$Action)
    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed with exit code $LASTEXITCODE."
    }
}

function Find-Python {
    $commands = @("python", "py")
    foreach ($command in $commands) {
        $resolved = Get-Command $command -ErrorAction SilentlyContinue
        if ($resolved) {
            return $resolved.Source
        }
    }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "Python was not found. Install Python 3.11 or 3.12 and enable Add Python to PATH."
}

Write-Host ""
Write-Host "Satellite Dosimeter Viewer - Setup" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"

$Python = Find-Python
$VersionText = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Assert-LastExitCode "Python version check"
$VersionParts = $VersionText.Trim().Split(".")
$Major = [int]$VersionParts[0]
$Minor = [int]$VersionParts[1]
if ($Major -ne 3 -or $Minor -lt 11 -or $Minor -gt 12) {
    throw "Python 3.11 or 3.12 is required. Detected: $VersionText"
}
Write-Host "Python $VersionText found." -ForegroundColor Green

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating virtual environment..."
    & $Python -m venv ".venv"
    Assert-LastExitCode "Virtual environment creation"
}

Write-Host "Updating pip..."
& $VenvPython -m pip install --upgrade pip
Assert-LastExitCode "pip update"

Write-Host "Installing application dependencies..."
& $VenvPython -m pip install -r "requirements.txt"
Assert-LastExitCode "Dependency installation"

Write-Host "Checking imports..."
& $VenvPython -c "import pandas, numpy, streamlit, plotly, openpyxl, scipy, googleapiclient; print('Import check: OK')"
Assert-LastExitCode "Import check"

Write-Host ""
Write-Host "Setup completed." -ForegroundColor Green
Write-Host "Double-click run_app.bat to start the application."
