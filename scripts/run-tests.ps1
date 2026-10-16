# Run the backend test suite with the project venv.
# Usage: powershell -File scripts/run-tests.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root "apps\api"
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
  Write-Error "Python venv not found at $python."
}

Push-Location $api
try {
  & $python -m pytest -q @args
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
