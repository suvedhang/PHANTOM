# Clear generated artifacts under output/ (databases, reports, exports).
# Keeps the directory structure so the app can recreate files.
# Usage: powershell -File scripts/reset-output.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$output = Join-Path $root "output"

if (-not (Test-Path -LiteralPath $output)) {
  New-Item -ItemType Directory -Path $output | Out-Null
}

Get-ChildItem -LiteralPath $output -Recurse -File -Include *.db, *.db-wal, *.db-shm, *.log, *.csv, *.json |
  Where-Object { $_.Name -ne ".gitkeep" } |
  ForEach-Object {
    Write-Host "Removing $($_.FullName)"
    Remove-Item -LiteralPath $_.FullName -Force
  }

foreach ($sub in @("reports", "evidence", "exports")) {
  $path = Join-Path $output $sub
  if (-not (Test-Path -LiteralPath $path)) {
    New-Item -ItemType Directory -Path $path | Out-Null
  }
}

Write-Host "output/ reset."
