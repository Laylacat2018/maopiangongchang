$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$studioPidFile = Join-Path $studioRoot 'data\server-pid.json'
if (-not (Test-Path -LiteralPath $studioPidFile)) { Write-Output 'No managed server PID.'; exit 0 }
$studioServer = Get-Content -LiteralPath $studioPidFile -Raw | ConvertFrom-Json
$studioProcess = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + [int]$studioServer.pid)
if ($studioProcess -and $studioProcess.CommandLine -like '*uvicorn catstudio.main:app*' -and $studioProcess.ExecutablePath -eq $studioServer.python) {
    Stop-Process -Id $studioProcess.ProcessId
    Write-Output 'CatStudio stopped.'
} else { Write-Output 'The recorded process is absent or belongs to another application; nothing stopped.' }
