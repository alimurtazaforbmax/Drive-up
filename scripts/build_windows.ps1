<#
.SYNOPSIS
  Build DriveUp for Windows with PyInstaller (optional Inno Setup installer).

.EXAMPLE
  .\scripts\build_windows.ps1
  .\scripts\build_windows.ps1 -MakeInstaller
#>
param(
    [switch]$MakeInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Write-Host "==> Installing build dependencies"
& $Python -m pip install -r requirements.txt -r requirements-build.txt

Write-Host "==> Cleaning previous build"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist\DriveUp, build\DriveUp

Write-Host "==> Running PyInstaller"
& $Python -m PyInstaller --noconfirm --clean driveup.spec

$DistApp = Join-Path $Root "dist\DriveUp"
if (-not (Test-Path (Join-Path $DistApp "DriveUp.exe"))) {
    throw "Build failed: DriveUp.exe not found in dist\DriveUp"
}

Write-Host "==> Portable build ready: $DistApp"
Write-Host "    Run DriveUp.exe from that folder."

if ($MakeInstaller) {
    $Iscc = @(
        "${env:LocalAppData}\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $Iscc) {
        Write-Warning "Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php"
        Write-Warning "Portable folder is still available at dist\DriveUp"
        exit 0
    }

    New-Item -ItemType Directory -Force -Path (Join-Path $Root "dist\installers") | Out-Null
    Write-Host "==> Compiling Windows installer with Inno Setup"
    & $Iscc (Join-Path $Root "installer\windows\driveup.iss")
    Write-Host "==> Installer written to dist\installers\"
}
