# Purpose: Offline runtime health checker for local OSRM and tile services.
# Workflow Role: Provides operator-facing readiness verification before app execution.

param(
    [switch]$WaitForReady,
    [int]$MaxWaitSeconds = 30,
    [switch]$AllowTilesDown
)

$ErrorActionPreference = "Stop"

function Test-Url {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 2,
        [scriptblock]$Validator = $null
    )
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSeconds -UseBasicParsing
        if ($null -ne $Validator) {
            $isValid = & $Validator $response
            if (-not $isValid) {
                return @{ ok = $false; reason = "invalid_response" }
            }
        }
        return @{ ok = $true; reason = $null }
    } catch {
        return @{ ok = $false; reason = $_.Exception.Message }
    }
}

$osrmUrl = "http://127.0.0.1:5000/nearest/v1/driving/51.3890,35.6892?number=1"
$stylesUrl = "http://127.0.0.1:8080/styles.json"
$dataUrl = "http://127.0.0.1:8080/data.json"

$start = Get-Date
do {
    $osrm = Test-Url -Url $osrmUrl -Validator {
        param($r)
        $content = [string]$r.Content
        return $content.Contains('"code":"Ok"') -or $content.Contains('"code": "Ok"')
    }

    $stylesProbe = Test-Url -Url $stylesUrl -Validator {
        param($r)
        $ct = [string]$r.Headers["Content-Type"]
        return $ct.ToLower().Contains("json")
    }

    $tileProbe = @{ ok = $false; reason = "styles_unavailable" }
    if ($stylesProbe.ok) {
        try {
            $stylesPayload = Invoke-RestMethod -Uri $stylesUrl -TimeoutSec 2
            $styleId = $null
            if ($stylesPayload -is [System.Array] -and $stylesPayload.Count -gt 0) {
                $firstStyle = $stylesPayload[0]
                if ($firstStyle -is [string]) {
                    $styleId = $firstStyle
                } elseif ($null -ne $firstStyle.id) {
                    $styleId = [string]$firstStyle.id
                } elseif ($null -ne $firstStyle.name) {
                    $styleId = [string]$firstStyle.name
                }
            } elseif ($null -ne $stylesPayload.styles -and $stylesPayload.styles.Count -gt 0) {
                $firstStyle = $stylesPayload.styles[0]
                if ($firstStyle -is [string]) {
                    $styleId = $firstStyle
                } elseif ($null -ne $firstStyle.id) {
                    $styleId = [string]$firstStyle.id
                } elseif ($null -ne $firstStyle.name) {
                    $styleId = [string]$firstStyle.name
                }
            }

            if ([string]::IsNullOrWhiteSpace($styleId)) {
                $styleId = ""
            }
            if (-not [string]::IsNullOrWhiteSpace($styleId)) {
                $tileUrl = "http://127.0.0.1:8080/styles/$styleId/10/532/386.png"
                $tileProbe = Test-Url -Url $tileUrl -Validator {
                    param($r)
                    $ct = [string]$r.Headers["Content-Type"]
                    return $ct.ToLower().Contains("image/")
                }
            }
        } catch {
            $tileProbe = @{ ok = $false; reason = $_.Exception.Message }
        }
    }

    # FIX: [OFFLINE-OPS-02] Accept vector-only tilesets (raw mbtiles) as healthy tile service.
    if (-not $tileProbe.ok) {
        $dataProbe = Test-Url -Url $dataUrl -Validator {
            param($r)
            $ct = [string]$r.Headers["Content-Type"]
            return $ct.ToLower().Contains("json")
        }
        if ($dataProbe.ok) {
            $tileProbe = @{ ok = $true; reason = "vector_only" }
        }
    }

    $tiles = $tileProbe

    Write-Host ("OSRM:  " + ($(if ($osrm.ok) { "UP" } else { "DOWN" })) + ($(if (-not $osrm.ok) { " | " + $osrm.reason } else { "" })))
    Write-Host ("Tiles: " + ($(if ($tiles.ok) { "UP" } else { "DOWN" })) + ($(if (-not $tiles.ok) { " | " + $tiles.reason } else { "" })))

    # FIX: [OFFLINE-OPS-01] Allow degraded readiness when OSRM is up but tiles are unavailable.
    $isReady = if ($AllowTilesDown) { $osrm.ok } else { $osrm.ok -and $tiles.ok }
    if ($isReady) {
        exit 0
    }

    if (-not $WaitForReady) {
        exit 1
    }

    Start-Sleep -Seconds 2
} while (((Get-Date) - $start).TotalSeconds -lt $MaxWaitSeconds)

Write-Error "Offline services did not become healthy in time."
exit 1
