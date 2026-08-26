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

function Get-CommandLineSummary {
    param([string]$CommandLine)

    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return "<empty command line>"
    }
    $singleLine = ($CommandLine -replace "\s+", " ").Trim()
    if ($singleLine.Length -le 180) {
        return $singleLine
    }
    return "$($singleLine.Substring(0, 177))..."
}

function Get-ListeningProcessInfo {
    param([int]$Port)

    $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    $listeners = @()
    foreach ($connection in $connections) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            $listeners += [pscustomobject]@{
                Port = $Port
                ProcessId = $connection.OwningProcess
                ProcessName = "<unknown>"
                CommandLine = ""
                CommandLineSummary = "<process disappeared before inspection>"
            }
            continue
        }
        $listeners += [pscustomobject]@{
            Port = $Port
            ProcessId = [int]$process.ProcessId
            ParentProcessId = [int]$process.ParentProcessId
            ProcessName = $process.Name
            CommandLine = [string]$process.CommandLine
            CommandLineSummary = Get-CommandLineSummary -CommandLine ([string]$process.CommandLine)
        }
    }
    return $listeners
}

function Test-IsExpectedApiProcess {
    param(
        [int]$Port,
        [string]$CommandLine
    )

    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return $false
    }
    return (
        $CommandLine -match "(^|\s)-m\s+uvicorn(\s|$)" -and
        $CommandLine -like "*services.api.app.main:app*" -and
        $CommandLine -match "(^|\s)--port\s+$Port(\s|$)"
    )
}

function Test-IsExpectedWebProcess {
    param(
        [int]$ProcessId,
        [int]$Port,
        [string]$CommandLine,
        [string]$RepoRoot
    )

    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return $false
    }

    $normalizedCommandLine = $CommandLine.ToLowerInvariant().Replace("/", "\")
    $normalizedRepoRoot = ([string]$RepoRoot).ToLowerInvariant().Replace("/", "\")
    $hasRepoEvidence = $normalizedCommandLine.Contains($normalizedRepoRoot) -or $normalizedCommandLine.Contains("donniecraftshell")
    $hasNextEvidence = (
        $normalizedCommandLine.Contains("npm") -or
        $normalizedCommandLine.Contains("next") -or
        $normalizedCommandLine.Contains("node_modules\next")
    )
    $hasDirectPortEvidence = (
        $CommandLine -match "(^|\s)--port\s+$Port(\s|$)" -or
        $CommandLine -match "(^|\s)-p\s+$Port(\s|$)" -or
        $CommandLine -match "(^|\s)$Port(\s|$)"
    )
    $hasAncestorPortEvidence = Test-ExpectedWebAncestor -ProcessId $ProcessId -Port $Port -RepoRoot $RepoRoot

    return ($hasRepoEvidence -and $hasNextEvidence -and ($hasDirectPortEvidence -or $hasAncestorPortEvidence))
}

function Test-ExpectedWebAncestor {
    param(
        [int]$ProcessId,
        [int]$Port,
        [string]$RepoRoot
    )

    $normalizedRepoRoot = ([string]$RepoRoot).ToLowerInvariant().Replace("/", "\")
    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 8 -and $null -ne $current -and $current.ParentProcessId -ne 0; $i++) {
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($current.ParentProcessId)" -ErrorAction SilentlyContinue
        if ($null -eq $parent) {
            return $false
        }

        $parentCommandLine = [string]$parent.CommandLine
        $normalizedParentCommandLine = $parentCommandLine.ToLowerInvariant().Replace("/", "\")
        $hasRepoEvidence = $normalizedParentCommandLine.Contains($normalizedRepoRoot) -or $normalizedParentCommandLine.Contains("donniecraftshell")
        $hasNextEvidence = (
            $normalizedParentCommandLine.Contains("npm") -or
            $normalizedParentCommandLine.Contains("next") -or
            $normalizedParentCommandLine.Contains("node_modules\next")
        )
        $hasPortEvidence = (
            $parentCommandLine -match "(^|\s)--port\s+$Port(\s|$)" -or
            $parentCommandLine -match "(^|\s)-p\s+$Port(\s|$)" -or
            $parentCommandLine -match "(^|\s)$Port(\s|$)"
        )
        if ($hasRepoEvidence -and $hasNextEvidence -and $hasPortEvidence) {
            return $true
        }
        $current = $parent
    }

    return $false
}

function Get-ChildProcessIds {
    param([int]$ParentProcessId)

    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentProcessId" -ErrorAction SilentlyContinue)
    $ids = @()
    foreach ($child in $children) {
        $ids += Get-ChildProcessIds -ParentProcessId ([int]$child.ProcessId)
        $ids += [int]$child.ProcessId
    }
    return $ids
}

function Stop-ProcessTreeSafely {
    param(
        [int]$ProcessId,
        [string]$Reason
    )

    $processIds = @()
    $processIds += Get-ChildProcessIds -ParentProcessId $ProcessId
    $processIds += $ProcessId
    $processIds = @($processIds | Select-Object -Unique)

    foreach ($id in $processIds) {
        $process = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($null -ne $process -and -not $process.HasExited) {
            Write-Host "Stopping DonnieCraftShell process $id ($($process.ProcessName)): $Reason" -ForegroundColor Yellow
            Stop-Process -Id $id -ErrorAction SilentlyContinue
        }
    }

    foreach ($id in $processIds) {
        try {
            Wait-Process -Id $id -Timeout 5 -ErrorAction SilentlyContinue
        }
        catch {
            # A terminating wait error is handled the same way as a timeout: verify below.
        }
        $process = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Wait-PortReleased {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $listeners = @(Get-ListeningProcessInfo -Port $Port)
        if ($listeners.Count -eq 0) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Assert-PortAvailableOrCleanStale {
    param(
        [int]$Port,
        [string]$Name,
        [string]$Kind,
        [string]$RepoRoot
    )

    $listeners = @(Get-ListeningProcessInfo -Port $Port)
    if ($listeners.Count -eq 0) {
        return
    }

    foreach ($listener in $listeners) {
        $isExpected = $false
        if ($Kind -eq "api") {
            $isExpected = Test-IsExpectedApiProcess -Port $Port -CommandLine $listener.CommandLine
        }
        elseif ($Kind -eq "web") {
            $isExpected = Test-IsExpectedWebProcess -ProcessId $listener.ProcessId -Port $Port -CommandLine $listener.CommandLine -RepoRoot $RepoRoot
        }

        if (-not $isExpected) {
            Fail-FirstPlayable "$Name port $Port is already in use by PID $($listener.ProcessId) ($($listener.ProcessName)): $($listener.CommandLineSummary). This process is not confidently identified as a stale DonnieCraftShell $Kind child, so it will not be terminated automatically. Stop it manually or pass alternate ports, for example -ApiPort 8010 -WebPort 3010."
        }
    }

    foreach ($listener in $listeners) {
        Stop-ProcessTreeSafely -ProcessId $listener.ProcessId -Reason "stale DonnieCraftShell $Name listener on port $Port"
    }

    if (-not (Wait-PortReleased -Port $Port -TimeoutSeconds 15)) {
        Fail-FirstPlayable "$Name port $Port is still in use after stopping stale DonnieCraftShell processes. Stop the remaining process manually or pass alternate ports, for example -ApiPort 8010 -WebPort 3010."
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
Assert-PortAvailableOrCleanStale -Port $ApiPort -Name "API" -Kind "api" -RepoRoot $repoRoot
Assert-PortAvailableOrCleanStale -Port $WebPort -Name "Web" -Kind "web" -RepoRoot $repoRoot

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
            Stop-ProcessTreeSafely -ProcessId $process.Id -Reason "First Playable launcher shutdown"
        }
    }
}
