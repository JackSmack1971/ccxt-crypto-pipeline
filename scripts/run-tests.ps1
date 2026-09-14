$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Project virtual environment not found. Provision it with: uv sync --locked"
}

& $venvPython -m pytest @args
exit $LASTEXITCODE
