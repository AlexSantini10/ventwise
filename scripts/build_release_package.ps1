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

$items = @(
  (Join-Path $root "custom_components\ventwise"),
  (Join-Path $root "README.md"),
  (Join-Path $root "LICENSE"),
  (Join-Path $root "NOTICE"),
  (Join-Path $root "hacs.json"),
  (Join-Path $root "brand")
) | Where-Object { Test-Path -LiteralPath $_ }

Compress-Archive -Path $items -DestinationPath $OutputPath -CompressionLevel Optimal
