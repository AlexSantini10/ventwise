[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArgs
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repositoryRoot "docker-compose.ci.yml"

Push-Location $repositoryRoot
try {
    & docker compose -f $composeFile run --rm ci @PytestArgs
    $testExitCode = $LASTEXITCODE
}
finally {
    & docker compose -f $composeFile down --remove-orphans | Out-Null
    Pop-Location
}

exit $testExitCode
