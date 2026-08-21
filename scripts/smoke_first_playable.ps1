param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$WebBaseUrl = "http://localhost:3000",
    [string]$SamplePath = "",
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

$arguments = @(
    (Join-Path $PSScriptRoot "smoke_first_playable.py"),
    "--api-base-url", $ApiBaseUrl,
    "--web-base-url", $WebBaseUrl,
    "--timeout-seconds", "$TimeoutSeconds"
)
if ($SamplePath) {
    $arguments += @("--sample-path", $SamplePath)
}

python $arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
