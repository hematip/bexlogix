# Purpose: Offline stack bootstrap script for local map and routing services.
# Workflow Role: Starts compose services and validates operational readiness.

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $repoRoot "infra\offline\docker-compose.offline.yml"
$osrmGraph = Join-Path $repoRoot "offline\osrm\data\tehran-latest.osrm"
$tilesPattern = Join-Path $repoRoot "offline\tiles\data\*.mbtiles"

if (-not (Test-Path $composeFile)) {
    Write-Error "Offline compose file was not found: $composeFile"
    exit 1
}
if (-not (Test-Path $osrmGraph)) {
    Write-Error "OSRM graph file was not found: $osrmGraph"
    Write-Host "Run: scripts\\offline_prepare_osrm_tehran.ps1"
    exit 1
}
$tileFiles = Get-ChildItem -Path $tilesPattern -ErrorAction SilentlyContinue | Sort-Object Name
if (($tileFiles | Measure-Object).Count -eq 0) {
    Write-Error "No MBTiles file found under: $(Split-Path $tilesPattern)"
    exit 1
}

$selectedTileFile = $tileFiles | Select-Object -First 1
$env:TILE_MB_FILE = $selectedTileFile.Name
Write-Host "Using MBTiles file: $($env:TILE_MB_FILE)"

docker compose -f $composeFile up -d
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed."
    exit 1
}

# FIX: [OFFLINE-OPS-01] Accept degraded startup if tiles are unavailable.
& (Join-Path $PSScriptRoot "offline_health.ps1") -WaitForReady -AllowTilesDown -MaxWaitSeconds 60
