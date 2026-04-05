# Purpose: One-time OSRM preprocessing script for Tehran extract.
# Workflow Role: Builds local OSRM graph artifacts required by offline routing runtime.

param(
    [string]$PbfFile = "",
    [string]$OsrmImage = ""
)

$ErrorActionPreference = "Stop"
# FIX: [OPS-01] Do not treat native stderr as terminating for docker probes.
$previousNativeErrorPreference = $null
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $previousNativeErrorPreference = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
}
$resolvedOsrmImage = if ([string]::IsNullOrWhiteSpace($OsrmImage)) {
    if ([string]::IsNullOrWhiteSpace($env:OSRM_DOCKER_IMAGE)) { "osrm/osrm-backend:latest" } else { $env:OSRM_DOCKER_IMAGE }
} else {
    $OsrmImage
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$osrmDataDir = Join-Path $repoRoot "offline\osrm\data"
if (-not (Test-Path $osrmDataDir)) {
    New-Item -ItemType Directory -Path $osrmDataDir | Out-Null
}

$resolvedPbf = if ([string]::IsNullOrWhiteSpace($PbfFile)) {
    Join-Path $osrmDataDir "tehran-latest.osm.pbf"
} else {
    (Resolve-Path $PbfFile).Path
}

if (-not (Test-Path $resolvedPbf)) {
    Write-Error "OSRM PBF file was not found: $resolvedPbf"
    exit 1
}

if ((Split-Path -Leaf $resolvedPbf) -ne "tehran-latest.osm.pbf") {
    Copy-Item -Path $resolvedPbf -Destination (Join-Path $osrmDataDir "tehran-latest.osm.pbf") -Force
}

$mountArg = "${osrmDataDir}:/data"
Write-Host "Preparing OSRM graph from: $resolvedPbf"
Write-Host "Using OSRM image: $resolvedOsrmImage"

# Ensure image is available before running heavy steps.
$imageExists = $true
docker image inspect $resolvedOsrmImage 1> $null 2> $null
if ($LASTEXITCODE -ne 0) {
    $imageExists = $false
}
if (-not $imageExists) {
    Write-Host "OSRM image not found locally. Pulling: $resolvedOsrmImage"
    docker pull $resolvedOsrmImage
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to pull OSRM image '$resolvedOsrmImage'. If Docker Hub is blocked, import image tar with: docker load -i <osrm-image.tar>"
        if ($PSVersionTable.PSVersion.Major -ge 7) {
            $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
        }
        exit 1
    }
}

docker run --rm -t -v $mountArg $resolvedOsrmImage osrm-extract -p /opt/car.lua /data/tehran-latest.osm.pbf
if ($LASTEXITCODE -ne 0) {
    Write-Error "osrm-extract failed."
    exit 1
}

docker run --rm -t -v $mountArg $resolvedOsrmImage osrm-partition /data/tehran-latest.osrm
if ($LASTEXITCODE -ne 0) {
    Write-Error "osrm-partition failed."
    exit 1
}

docker run --rm -t -v $mountArg $resolvedOsrmImage osrm-customize /data/tehran-latest.osrm
if ($LASTEXITCODE -ne 0) {
    Write-Error "osrm-customize failed."
    exit 1
}

if (Test-Path (Join-Path $osrmDataDir "tehran-latest.osrm")) {
    Write-Host "OSRM graph is ready at: $osrmDataDir\tehran-latest.osrm"
} else {
    Write-Error "OSRM preprocessing finished without output graph file."
    if ($PSVersionTable.PSVersion.Major -ge 7) {
        $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
    }
    exit 1
}

if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
}
