[CmdletBinding()]
param(
    [switch]$NoBuild,
    [switch]$NoBrowser,
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiUrl = "http://127.0.0.1:8000/health"
$webUrl = "http://127.0.0.1:5173/"

Set-Location $projectRoot

function Invoke-RequiredCommand {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit code $LASTEXITCODE): $Command $($Arguments -join ' ')"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install Docker Desktop first."
}

Write-Host "Checking Docker Desktop..." -ForegroundColor Cyan
& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon is unavailable. Start Docker Desktop and retry."
}

$composeArguments = @("compose", "up", "-d")
if (-not $NoBuild) {
    $composeArguments += "--build"
}

Write-Host "Starting Quality Case Agent..." -ForegroundColor Cyan
Invoke-RequiredCommand -Command "docker" -Arguments $composeArguments

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$apiReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri $apiUrl -TimeoutSec 3
        if ($health.status -eq "ok") {
            $apiReady = $true
            break
        }
    }
    catch {
        # The API may still be starting while the image and healthcheck settle.
    }
    Start-Sleep -Seconds 2
}

if (-not $apiReady) {
    Write-Host "API did not become ready within $TimeoutSeconds seconds. Container status:" -ForegroundColor Red
    & docker compose ps
    throw "Startup timed out. Run 'docker compose logs api' for details."
}

try {
    $webResponse = Invoke-WebRequest -Uri $webUrl -UseBasicParsing -TimeoutSec 5
    if ($webResponse.StatusCode -lt 200 -or $webResponse.StatusCode -ge 400) {
        throw "Web 返回 HTTP $($webResponse.StatusCode)"
    }
}
catch {
    throw "WebUI is not ready: $($_.Exception.Message)"
}

Write-Host "Startup complete." -ForegroundColor Green
Write-Host "  WebUI: $webUrl"
Write-Host "  API:   http://127.0.0.1:8000"

if (-not $NoBrowser) {
    Start-Process $webUrl
}
