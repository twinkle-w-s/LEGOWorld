param([string]$Python = "python", [switch]$Precision)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        & $Python -c "import sys; assert sys.version_info >= (3, 12), 'LEGOWorld v2 requires Python 3.12+. Pass -Python with a newer interpreter path.'"
        if ($LASTEXITCODE -ne 0) { throw 'A Python 3.12+ interpreter is required.' }
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create the virtual environment.' }
    }
    $installTarget = if ($Precision) { '.[dev,precision]' } else { '.[dev]' }
    & '.\.venv\Scripts\python.exe' -m pip install -e $installTarget
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & '.\.venv\Scripts\python.exe' -m legoworld doctor
    if ($LASTEXITCODE -ne 0) { throw 'Environment check failed.' }
} finally {
    Pop-Location
}
