# PlayPalace Client Build Script
# This script compiles the client using PyInstaller

$ErrorActionPreference = "Stop"

# Store the client directory
$clientDir = Get-Location
Write-Host "Building from: $clientDir"

# Verify we're in the right place
if (-not (Test-Path "client.py")) {
    Write-Host "ERROR: client.py not found in current directory"
    exit 1
}

Write-Host "Cleaning previous builds..."
Remove-Item dist, build -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Cleaned."

Write-Host "Starting compilation with PyInstaller..."
Write-Host "Command: python -m PyInstaller client.py --onefile --windowed --name PlayPalace11 --add-data 'sounds:sounds' --icon=icon.ico"

python -m PyInstaller client.py `
    --onefile `
    --windowed `
    --name PlayPalace11 `
    --add-data "sounds:sounds" `
    --icon=icon.ico

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Compilation failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Compilation complete!"

# Check if executable exists
if (Test-Path "dist\PlayPalace11.exe") {
    $size = (Get-Item "dist\PlayPalace11.exe").Length / 1MB
    Write-Host "SUCCESS: Compiled executable found"
    Write-Host "File size: $([math]::Round($size, 2)) MB"
    exit 0
} else {
    Write-Host "ERROR: Expected executable not found at dist\PlayPalace11.exe"
    exit 1
}
