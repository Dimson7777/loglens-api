$ErrorActionPreference = "Stop"

Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$pythonCandidates = @(
    (Join-Path $repoRoot ".venv/Scripts/python.exe"),
    (Join-Path (Split-Path -Parent $repoRoot) ".venv/Scripts/python.exe")
)

$python = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $python = $pythonCmd.Source
    }
}

if (-not $python) {
    throw "Python interpreter not found. Create a virtual environment and install dependencies first."
}

$env:ALEMBIC_DATABASE_URL = "postgresql+psycopg://loglens:loglens@localhost:5432/loglens"

Write-Host "==> Running Alembic migrations"
& $python -m alembic upgrade head

Write-Host "==> Running Ruff check"
& $python -m ruff check .

Write-Host "==> Running Ruff format check"
& $python -m ruff format --check .

Write-Host "==> Running mypy"
& $python -m mypy .

Write-Host "==> Running pytest"
& $python -m pytest -v

Write-Host "==> Building and starting Docker Compose stack"
docker compose up -d --build --wait

Write-Host "==> Verifying service health"
$composeJson = docker compose ps --format json | ConvertFrom-Json
$requiredServices = @("api", "db", "redis", "celery-worker", "celery-beat")

foreach ($service in $requiredServices) {
    $match = $composeJson | Where-Object { $_.Service -eq $service }
    if (-not $match) {
        throw "Service '$service' is missing from docker compose ps output."
    }

    if ($service -in @("api", "db", "redis", "celery-worker")) {
        if ($match.Health -ne "healthy") {
            throw "Service '$service' is not healthy. Current health: '$($match.Health)'"
        }
    }

    if ($match.State -ne "running") {
        throw "Service '$service' is not running. Current state: '$($match.State)'"
    }
}

Write-Host "==> Docker Compose services verified"
docker compose ps
