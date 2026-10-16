# Typecheck, lint, and build the web app.
# Usage: powershell -File scripts/check-web.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
  npm run web:typecheck
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  npm run web:lint
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  npm run web:build
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
