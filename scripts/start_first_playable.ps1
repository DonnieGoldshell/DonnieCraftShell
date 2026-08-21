param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000,
    [switch]$NoBrowser,
    [switch]$SkipInstallCheck
)

$ErrorActionPreference = "Stop"

function Fail-FirstPlayable {
    param([string]$Message)
    Write-Host ""
    Write-Host "DonnieCraftShell First Playable could not start:" -ForegroundColor Red
    Write-Host "  $Message" -ForegroundColor Red
    Write-Host ""
    Write-Host "See FIRST_PLAYABLE.md for setup steps." -ForegroundColor Yellow
    exit 1
}

function Assert-Command {
    param(
        [string]$Name,
        [string]$InstallHint
    )
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail-FirstPlayable "$Name was not found. $InstallHint"
    }
}

function Assert-Path {
    param(
        [string]$Path,
        [string]$InstallHint
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        Fail-FirstPlayable "$Path was not found. $InstallHint"
    }
}

function Assert-PortAvailable {
    param(
        [int]$Port,
        [string]$Name
    )
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
    }
    catch {
        Fail-FirstPlayable "$Name port $Port is already in use. Stop the process using that port or pass a different port, for example -ApiPort 8010 -WebPort 3010."
    }
    finally {
        if ($null -ne $listener) {
            $listener.Stop()
        }
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$webRoot = Join-Path $repoRoot "apps\web"
$logsRoot = Join-Path $repoRoot ".dcs\logs"
$apiOutLog = Join-Path $logsRoot "first-playable-api.out.log"
$apiErrLog = Join-Path $logsRoot "first-playable-api.err.log"
$webOutLog = Join-Path $logsRoot "first-playable-web.out.log"
$webErrLog = Join-Path $logsRoot "first-playable-web.err.log"

Set-Location $repoRoot
New-Item -ItemType Directory -Force -Path $logsRoot | Out-Null

Assert-Command "python" "Install Python 3.11+ and ensure it is available on PATH."
Assert-Command "npm" "Install Node.js LTS, which includes npm."
$pythonCommand = (Get-Command "python").Source
$npmApplication = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if ($null -eq $npmApplication) {
    $npmApplication = Get-Command "npm"
}
$npmCommand = $npmApplication.Source

if (-not $SkipInstallCheck) {
    Assert-Path (Join-Path $webRoot "node_modules") "Run: cd apps\web; npm install"
    python -c "import fastapi, uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Fail-FirstPlayable "Backend dependencies are missing. Run: python -m pip install -r services/api/requirements.txt"
    }
}

$apiUrl = "http://localhost:$ApiPort"
$webUrl = "http://localhost:$WebPort"
Assert-PortAvailable -Port $ApiPort -Name "API"
Assert-PortAvailable -Port $WebPort -Name "Web"

Write-Host "Starting DonnieCraftShell First Playable..." -ForegroundColor Cyan
Write-Host "  API: $apiUrl"
Write-Host "  Web: $webUrl"
Write-Host "  Logs: $logsRoot"
Write-Host ""

$apiProcess = $null
$webProcess = $null

try {
    $env:DCS_CORS_ALLOWED_ORIGINS = "$webUrl,http://127.0.0.1:$WebPort"
    $env:NEXT_PUBLIC_API_BASE_URL = $apiUrl

    $apiStartInfo = @{
        FilePath = $pythonCommand
        ArgumentList = @("-m", "uvicorn", "services.api.app.main:app", "--host", "127.0.0.1", "--port", "$ApiPort")
        WorkingDirectory = $repoRoot
        RedirectStandardOutput = $apiOutLog
        RedirectStandardError = $apiErrLog
        PassThru = $true
        WindowStyle = "Hidden"
    }
    $apiProcess = Start-Process @apiStartInfo

    $webStartInfo = @{
        FilePath = $npmCommand
        ArgumentList = @("run", "dev", "--", "--hostname", "127.0.0.1", "--port", "$WebPort")
        WorkingDirectory = $webRoot
        RedirectStandardOutput = $webOutLog
        RedirectStandardError = $webErrLog
        PassThru = $true
        WindowStyle = "Hidden"
    }
    $webProcess = Start-Process @webStartInfo

    Write-Host "Waiting for services to respond..."
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "smoke_first_playable.ps1") `
        -ApiBaseUrl $apiUrl `
        -WebBaseUrl $webUrl `
        -TimeoutSeconds 90

    if (-not $NoBrowser) {
        Start-Process -FilePath $webUrl
    }

    Write-Host ""
    Write-Host "DonnieCraftShell is running." -ForegroundColor Green
    Write-Host "Open $webUrl and paste samples\first_playable_quiver_sample.txt."
    Write-Host "Press Ctrl+C in this terminal to stop API and web processes."

    while ($true) {
        if ($apiProcess.HasExited) {
            Fail-FirstPlayable "API process exited early. Check $apiOutLog and $apiErrLog"
        }
        if ($webProcess.HasExited) {
            Fail-FirstPlayable "Web process exited early. Check $webOutLog and $webErrLog"
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    foreach ($process in @($apiProcess, $webProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }
}
