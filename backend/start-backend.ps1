$ErrorActionPreference = "Stop"

Write-Host "Stopping old processes using port 8000..."
$connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
foreach ($connection in $connections) {
    if ($connection.OwningProcess -and $connection.OwningProcess -ne 0) {
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Set-Location $PSScriptRoot

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    . ".\venv\Scripts\Activate.ps1"
} elseif (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . ".\.venv\Scripts\Activate.ps1"
}

Write-Host "Starting Kondai from app.main:app..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
