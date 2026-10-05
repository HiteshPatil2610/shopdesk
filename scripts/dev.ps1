# Starts the API and web in hidden background processes; logs are in tmp/dev.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$flask = Join-Path $backend 'venv\Scripts\flask.exe'
if (-not (Test-Path -LiteralPath $flask)) { throw 'Create backend\venv and install requirements-dev.txt first.' }
if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules'))) { throw 'Run npm ci from frontend first.' }
foreach ($port in @(5001, 5173)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop the existing ShopDesk server first."
    }
}
$logDir = Join-Path $root 'tmp\dev'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$api = Start-Process -FilePath $flask -ArgumentList '--app', 'shopdesk', 'run', '-p', '5001', '--no-reload' -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'api.out.log') -RedirectStandardError (Join-Path $logDir 'api.err.log') -PassThru
$npm = (Get-Command npm.cmd).Source
# cmd only launches npm.cmd; no filesystem operations are delegated.
$web = Start-Process -FilePath $env:ComSpec -ArgumentList '/d', '/c', "`"$npm`" run dev -w web" -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'web.out.log') -RedirectStandardError (Join-Path $logDir 'web.err.log') -PassThru
Write-Host "API PID $($api.Id); web launcher PID $($web.Id). Logs: $logDir"
Write-Host 'ShopDesk: http://localhost:5173 (Admin: /admin; Billing: /pos)'
Write-Host 'Stop: Stop-Process -Id <API PID>; taskkill /PID <web launcher PID> /T /F'
