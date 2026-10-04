# Starts ShopDesk for local development: both Flask APIs and both Vite apps,
# each in its own PowerShell window. Close a window (or Ctrl+C in it) to stop that piece.
#
#   .\scripts\dev.ps1
#
# Needs: backend\venv created and `npm install` done in frontend\ (SETUP_GUIDE §9).

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$flask = Join-Path $backend 'venv\Scripts\flask.exe'

if (-not (Test-Path $flask)) {
    Write-Error "backend\venv not found. Run: cd backend; py -3.12 -m venv venv; .\venv\Scripts\pip install -r requirements-dev.txt"
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Error "frontend\node_modules not found. Run: cd frontend; npm install"
}

$procs = @(
    @{ Title = 'ShopDesk admin_api :5001'; Dir = $backend;  Cmd = "& '$flask' --app admin_api run -p 5001 --debug" },
    @{ Title = 'ShopDesk pos_api :5002';   Dir = $backend;  Cmd = "& '$flask' --app pos_api run -p 5002 --debug" },
    @{ Title = 'ShopDesk admin-web :5173'; Dir = $frontend; Cmd = 'npm run dev -w admin-web' },
    @{ Title = 'ShopDesk pos-web :5174';   Dir = $frontend; Cmd = 'npm run dev -w pos-web' }
)

foreach ($p in $procs) {
    $command = "`$Host.UI.RawUI.WindowTitle = '$($p.Title)'; Set-Location '$($p.Dir)'; $($p.Cmd)"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $command | Out-Null
    Write-Host "Started $($p.Title)"
}

Write-Host ''
Write-Host 'Admin Console:   http://localhost:5173'
Write-Host 'Billing Counter: http://localhost:5174'
