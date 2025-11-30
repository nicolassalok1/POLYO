param(
    [string]$ApiKey = "",
    [string]$EnvName = "polyo-gpu"
)

$runner = Join-Path $PSScriptRoot "set_keys_and_run.ps1"
if (-not (Test-Path $runner)) {
    Write-Error "set_keys_and_run.ps1 introuvable dans $PSScriptRoot"
    exit 1
}

& $runner -ApiKey $ApiKey -EnvName $EnvName
