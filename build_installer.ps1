# One-command repeatable build for the AI Content Library desktop installer.
# See docs/features/14-desktop-packaging.md for the full design.
#
# Prerequisites (one-time, per build machine):
#   - Python venv at backend\.venv with `pip install -r backend\requirements-build.txt`
#   - Node.js + `npm install` already run in frontend\
#   - Inno Setup 6 installed (winget install JRSoftware.InnoSetup)
#
# This needs to be re-run periodically even with no app changes, since
# yt-dlp's extraction logic goes stale as platforms change -- ship a fresh
# build whenever requirements.txt bumps yt-dlp.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "== 1/4: Fetching bundled ffmpeg =="
& powershell -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "resources\download_ffmpeg.ps1")

Write-Host "== 2/4: Building frontend =="
Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
} finally {
    Pop-Location
}

Write-Host "== 3/4: Building backend with PyInstaller =="
Push-Location (Join-Path $RepoRoot "backend")
try {
    & ".\.venv\Scripts\python.exe" -m PyInstaller AIContentLibrary.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
} finally {
    Pop-Location
}

Write-Host "== 4/4: Compiling installer with Inno Setup =="
$ISCC = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $ISCC)) {
    $ISCC = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $ISCC)) {
    throw "Inno Setup's ISCC.exe not found -- install it first (winget install JRSoftware.InnoSetup)."
}
Push-Location (Join-Path $RepoRoot "installer")
try {
    & $ISCC installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Done: installer\Output\AIContentLibrarySetup.exe"
