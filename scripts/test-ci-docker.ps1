[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArgs
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repositoryRoot
try {
    Write-Warning "test-ci-docker.ps1 is deprecated; use python scripts/run_tests.py."
    & python scripts/run_tests.py -- @PytestArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
