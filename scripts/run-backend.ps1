# PHANTOM backend dev runner.
# Usage: powershell -File scripts/run-backend.ps1 [-AutostartMock]
param(
  [switch]$AutostartMock
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root "apps\api"
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
  Write-Error "Python venv not found at $python. Create it first (see docs/IMPLEMENTATION_PLAN.md)."
}

if (-not $AutostartMock) {
  $env:PHANTOM_AUTOSTART_MOCK = "false"
}

Write-Host "Starting PHANTOM API from $api"
Push-Location $api
try {
  & $python -m phantom_api.main
} finally {
  Pop-Location
}
