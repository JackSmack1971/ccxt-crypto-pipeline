$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$venvRoot = if ($env:CCXT_PROJECT_VENV) { $env:CCXT_PROJECT_VENV } else { Join-Path $repoRoot '.venv' }
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Project virtual environment not found. Provision it with: uv sync --locked --extra test, or set CCXT_PROJECT_VENV to a provisioned environment."
}

& $venvPython -m pytest @args
exit $LASTEXITCODE
