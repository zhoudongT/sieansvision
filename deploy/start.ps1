param([Parameter(Mandatory=$true)][string]$DataDir)
$ErrorActionPreference = 'Stop'
& node (Join-Path $PSScriptRoot '../scripts/platform.cjs') start --data-dir $DataDir
exit $LASTEXITCODE
