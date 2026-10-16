# PHANTOM web dev runner.
# Usage: powershell -File scripts/run-web.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath (Join-Path $root "node_modules"))) {
  Write-Host "Installing npm dependencies..."
  Push-Location $root
  try { npm install } finally { Pop-Location }
}

Write-Host "Starting Vite dev server"
Push-Location $root
try {
  npm run web:dev
} finally {
  Pop-Location
}
