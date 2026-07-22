$ErrorActionPreference = "Stop"

$port = 4173
if ($env:PORT) {
  $port = [int]$env:PORT
}

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
foreach ($listener in $listeners) {
  $owner = [int]$listener.OwningProcess
  if ($owner -gt 0 -and $owner -ne $PID) {
    Write-Host "Stopping existing app server on port $port (PID $owner)..."
    Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
  }
}

Start-Sleep -Milliseconds 500
$env:PORT = "$port"
Write-Host "Starting KVNP Passport Photo Studio on http://127.0.0.1:$port"
python server.py
