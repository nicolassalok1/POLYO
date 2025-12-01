# test_pipeline.ps1
# Orchestration du pipeline tests/pipeline_demo sans arrêt après la première erreur.

param(
    [string]$Channel   = "https://t.me/gmgnsignals/3993253",
    [int]   $Limit     = 1,
    [string]$PythonExe = "python"
)

# On ne stoppe pas le script sur erreur PowerShell
$ErrorActionPreference = "Continue"

# Resolve repo root from this script's location
$ScriptPath = $MyInvocation.MyCommand.Path
$RepoRoot   = Split-Path -Parent $ScriptPath
$PipelineDir = Join-Path $RepoRoot "tests\pipeline_demo"

Write-Host "Repository root: $RepoRoot" -ForegroundColor DarkGray
Write-Host "Pipeline dir   : $PipelineDir" -ForegroundColor DarkGray
Write-Host ""

# Ordered list of pipeline steps
$steps = @(
    @{ Name = "step01_fetch_telegram.py";       Args = @("--channel", $Channel, "--limit", $Limit) }
    @{ Name = "step02_sentiment_openai.py";     Args = @() }
    @{ Name = "step03_fetch_gmgn.py";           Args = @() }
    @{ Name = "step04_preprocess_prices.py";    Args = @() }
    @{ Name = "step05_kalman_analysis.py";      Args = @() }
    @{ Name = "step06_jumpdiff_analysis.py";    Args = @() }
    @{ Name = "step07_rbergomi_analysis.py";    Args = @() }
    @{ Name = "step08_combine_features.py";     Args = @() }
    @{ Name = "step09_run_rl.py";               Args = @() }
    @{ Name = "step10_simulate_gmgn_order.py";  Args = @() }
)

foreach ($step in $steps) {
    $name       = $step.Name
    $args       = $step.Args
    $scriptPath = Join-Path $PipelineDir $name

    if (-not (Test-Path $scriptPath)) {
        Write-Host "SKIP: $scriptPath not found." -ForegroundColor Yellow
        # On continue quand même, le fallback côté Python doit gérer.
        continue
    }

    $argString = if ($args.Count -gt 0) { $args -join ' ' } else { "" }
    Write-Host "==> Running $scriptPath $argString" -ForegroundColor Cyan

    $exitCode = 0
    try {
        & $PythonExe $scriptPath @args
        $exitCode = $LASTEXITCODE
    }
    catch {
        Write-Host "EXCEPTION while running $name : $_" -ForegroundColor Red
        $exitCode = 1
    }

    if ($exitCode -ne 0) {
        Write-Host "ERROR: $name exited with code $exitCode (pipeline continues, fallback/empty .log should handle it)." -ForegroundColor Red
    } else {
        Write-Host "OK: $name completed successfully." -ForegroundColor Green
    }

    Write-Host ""
}

Write-Host "Pipeline execution finished (with possible errors, see logs)." -ForegroundColor Green
