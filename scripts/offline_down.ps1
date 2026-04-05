# Purpose: Offline stack shutdown script for local map and routing services.
# Workflow Role: Stops compose services used by BexLogix offline runtime.

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $repoRoot "infra\offline\docker-compose.offline.yml"

if (-not (Test-Path $composeFile)) {
    Write-Error "Offline compose file was not found: $composeFile"
    exit 1
}

docker compose -f $composeFile down
exit $LASTEXITCODE
