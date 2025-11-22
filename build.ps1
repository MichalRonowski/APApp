# Build desktop executable with PyInstaller and (optionally) Inno Setup installer
# Run in Windows PowerShell

param(
    [switch]$Installer
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host 'Setting up environment...'
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Clean previous build
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue | Out-Null

Write-Host 'Building executable (PyInstaller)...'
# Try to stop running instance that may lock dist files
Get-Process -Name 'APApp' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$addData = @(
    'templates;templates',
    'static;static',
    'ex_input.csv;.',
    'config.json;.',
    'logo.png;.',
    'output\\NazwyKlienci.csv;.'
)
$addData += 'output/Jednostki.csv;output'

$addDataArgs = foreach ($d in $addData) { '--add-data', $d }

# Optional icon (provide static\app.ico if available)
$iconArg = @()
if (Test-Path 'static\app.ico') { $iconArg = @('--icon', 'static\app.ico') }

pyinstaller --noconfirm @iconArg --noconsole --name 'APApp' @addDataArgs 'desktop_app.py'

if (-not $Installer) { exit 0 }

# Build installer with Inno Setup (if installed)
$ISCC = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
if (-not (Test-Path $ISCC)) {
    Write-Warning 'Inno Setup not found. Install Inno Setup 6 or run build.ps1 without -Installer.'
    exit 0
}

Write-Host 'Building installer (Inno Setup)...'
& $ISCC 'installer.iss'
