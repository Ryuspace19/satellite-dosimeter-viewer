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

function Find-Git {
    $resolved = Get-Command git -ErrorAction SilentlyContinue
    if ($resolved) {
        return $resolved.Source
    }
    $defaultGit = "C:\Program Files\Git\cmd\git.exe"
    if (Test-Path -LiteralPath $defaultGit) {
        return $defaultGit
    }
    throw "Git was not found. Install Git for Windows."
}

Write-Host ""
Write-Host "Satellite Dosimeter Viewer - Update" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"

$Git = Find-Git
if (-not (Test-Path -LiteralPath ".git")) {
    throw "This folder is not a Git clone. Clone the GitHub repository first."
}

$Dirty = & $Git status --porcelain
if ($Dirty) {
    Write-Host "Update stopped because source files have local changes:" -ForegroundColor Yellow
    $Dirty | ForEach-Object { Write-Host $_ }
    throw "Commit or discard the source changes before updating. Data and credentials ignored by Git are unaffected."
}

Write-Host "Downloading the latest source code..."
& $Git fetch origin main
Assert-LastExitCode "git fetch"
& $Git pull --ff-only origin main
Assert-LastExitCode "git pull"

$SetupScript = Join-Path $PSScriptRoot "setup.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript
Assert-LastExitCode "Environment setup"

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Write-Host "Running tests..."
& $VenvPython -m pytest -q
Assert-LastExitCode "Application tests"

Write-Host ""
Write-Host "Update completed successfully." -ForegroundColor Green
Write-Host "credentials.json, tokens, manifests, and analysis outputs were not changed."
