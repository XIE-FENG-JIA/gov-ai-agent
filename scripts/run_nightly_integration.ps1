$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$pythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$null = Get-Command $pythonBin -ErrorAction Stop

& $pythonBin "scripts/run_nightly_integration.py" --python $pythonBin @args
exit $LASTEXITCODE
