# Fetches ffmpeg.exe/ffprobe.exe (static Windows build) into resources/ffmpeg/
# so the packaged app never needs the customer to install ffmpeg themselves.
# Run once before building (build_installer.ps1 calls this automatically);
# safe to re-run, it always re-fetches the latest release.
#
# Deliberately the GPL build, not LGPL: Video Composer's ffmpeg invocation
# requires "-c:v libx264" (backend/app/modules/video_composer/service.py),
# and libx264/libx265 are GPL-only codecs excluded from BtbN's LGPL builds --
# the LGPL build cannot run this app's own Video Composer feature. Bundling
# a GPL binary alongside a closed-source app via subprocess (not static
# linking) is common commercial practice, but is a real legal question the
# app's owner should confirm for their own distribution before shipping --
# not something to treat as settled by this script. The bundled LICENSE.txt
# must ship alongside the binaries either way.

$ErrorActionPreference = "Stop"

$ResourcesDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FfmpegDir = Join-Path $ResourcesDir "ffmpeg"
$ZipPath = Join-Path $env:TEMP "ffmpeg-gpl-build.zip"

New-Item -ItemType Directory -Force -Path $FfmpegDir | Out-Null

Write-Host "Looking up latest BtbN FFmpeg GPL Windows build..."
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
$asset = $release.assets | Where-Object { $_.name -like "ffmpeg-n*-latest-win64-gpl-*.zip" -and $_.name -notlike "*shared*" } | Select-Object -First 1
if (-not $asset) {
    throw "Could not find a win64 GPL static ffmpeg build in the latest BtbN release."
}

Write-Host "Downloading $($asset.name) ($([math]::Round($asset.size / 1MB, 1)) MB)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $ZipPath

Write-Host "Extracting ffmpeg.exe / ffprobe.exe / LICENSE.txt..."
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName -match "bin/ffmpeg\.exe$" -or $entry.FullName -match "bin/ffprobe\.exe$" -or $entry.FullName -match "LICENSE\.txt$") {
            $destPath = Join-Path $FfmpegDir (Split-Path -Leaf $entry.FullName)
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destPath, $true)
            Write-Host "  -> $destPath"
        }
    }
} finally {
    $zip.Dispose()
}

Remove-Item $ZipPath -Force
Write-Host "Done. Bundled ffmpeg in $FfmpegDir"
