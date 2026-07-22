$ErrorActionPreference = "Stop"

$port = 4173
if ($env:PORT) {
  $port = [int]$env:PORT
}

$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if (-not $listeners) {
  Write-Host "No KVNP app server is listening on port $port."
  exit 0
}

foreach ($listener in $listeners) {
  $owner = [int]$listener.OwningProcess
  if ($owner -gt 0 -and $owner -ne $PID) {
    Write-Host "Stopping app server on port $port (PID $owner)..."
    Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
  }
}
