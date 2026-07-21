param(
  [Parameter(Mandatory = $true)]
  [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$outputDir = Split-Path -Parent $OutputPath

if (-not (Test-Path -LiteralPath $outputDir)) {
  New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if (Test-Path -LiteralPath $OutputPath) {
  Remove-Item -LiteralPath $OutputPath -Force
}

$integrationDir = Join-Path $root "custom_components\ventwise"
$items = @(
  Get-ChildItem -LiteralPath $integrationDir -Force |
    Where-Object {
      $_.Name -ne ".gitkeep" -and
      $_.Name -ne "__pycache__" -and
      $_.Extension -ne ".pyc"
    } |
    ForEach-Object { $_.FullName }
)
$items += @(
  (Join-Path $root "README.md"),
  (Join-Path $root "LICENSE"),
  (Join-Path $root "NOTICE"),
  (Join-Path $root "hacs.json")
)

Compress-Archive -Path $items -DestinationPath $OutputPath -CompressionLevel Optimal
