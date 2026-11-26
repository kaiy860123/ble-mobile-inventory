param([ValidateSet('demo','ble','external')][string]$Mode = 'demo', [int]$Port = 8080, [string]$Config = 'config/site.example.json')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.venv/Scripts/python.exe' -m ble_inventory.cli serve --mode $Mode --host 127.0.0.1 --port $Port --config $Config
exit $LASTEXITCODE
