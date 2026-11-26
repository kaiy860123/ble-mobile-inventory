param([string]$PythonPath = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
function Invoke-Checked { param([string]$Command, [string[]]$Arguments) & $Command @Arguments; if ($LASTEXITCODE -ne 0) { throw "$Command failed with exit code $LASTEXITCODE" } }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { Invoke-Checked $PythonPath @('-m','venv','.venv') }
$projectPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
Invoke-Checked $projectPython @('-m','pip','install','-e','.[dev]')
Invoke-Checked 'npm.cmd' @('ci')
Invoke-Checked $projectPython @('scripts/generate-demo.py','--georeference-example')
Invoke-Checked 'npm.cmd' @('run','build')
Invoke-Checked $projectPython @('-m','pytest','-q')
Invoke-Checked 'npm.cmd' @('test')
Write-Host 'Setup passed. Run scripts/run-local.ps1 to open the synthetic demo.'
