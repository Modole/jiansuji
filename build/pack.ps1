param(
  [string]$AppName = "HarmonicTester",
  [string]$IconPath = "assets\\app.ico"
)

Write-Host "==> Building $AppName with PyInstaller (onedir)" -ForegroundColor Cyan

# Ensure PyInstaller is available
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
  Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
  pip install pyinstaller | Write-Output
}

# Clean previous builds but keep pack.ps1
if (Test-Path "build") {
  Get-ChildItem -Path "build" -Recurse -Force | Where-Object { $_.Name -ne "pack.ps1" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
Remove-Item -Recurse -Force dist\\* -ErrorAction SilentlyContinue | Out-Null

# Build onedir exe (recommended for Flask static/templates)
$pyArgs = @(
  "--noconfirm",
  "--clean",
  "--onedir",
  "--name", $AppName,
  "--add-data", "app\\static;app\\static",
  "--add-data", "app\\static\\templates;app\\static\\templates",
  "--add-data", "data;data",
  "run.py"
)

if (Test-Path $IconPath) {
  $pyArgs += @("--icon", $IconPath)
} else {
  Write-Warning "Icon file not found: $IconPath. Building without custom icon."
}

Write-Host "pyinstaller $($pyArgs -join ' ')" -ForegroundColor Gray
pyinstaller @pyArgs

$exePath = Join-Path "dist" (Join-Path $AppName "$AppName.exe")
if (-not (Test-Path $exePath)) {
  Write-Error "Build failed: $exePath not found"; exit 1
}

Write-Host "==> Build succeeded: $exePath" -ForegroundColor Green

# Build installer with Inno Setup if available
$ISCC = "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
if (Test-Path $ISCC) {
  Write-Host "==> Compiling installer with Inno Setup" -ForegroundColor Cyan
  & $ISCC "installer\\HarmonicTester.iss"
  Write-Host "Installer output: installer\\output" -ForegroundColor Green
} else {
  Write-Warning "Inno Setup not found. Install from https://jrsoftware.org/isinfo.php and rerun to build installer."
}