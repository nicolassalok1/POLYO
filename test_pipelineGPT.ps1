# test_pipeline.ps1
# Orchestration script for the 10-step pipeline in tests/pipeline_demo/
# Usage example:
#   ./test_pipeline.ps1 -Channel "@gmgnsignals" -Limit 50 -PythonExe "python"

param(
    [string]$PythonExe = "python",
    [string]$Channel   = "https://t.me/gmgnsignals/3993253",
    [int]   $Limit     = 50
)

$ErrorActionPreference = "Stop"

# Resolve paths relative to repo root (location of this .ps1)
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PipelineDir = Join-Path $ScriptRoot "tests\pipeline_demo"
$LogsDir     = Join-Path $PipelineDir "pipeline_logs"

if (-not (Test-Path $PipelineDir)) {
    Write-Host "ERROR: Pipeline directory not found: $PipelineDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

function Run-Step {
    param(
        [string]$ScriptName,
        [string[]]$Args = @()
    )

    $scriptPath = Join-Path $PipelineDir $ScriptName

    if (-not (Test-Path $scriptPath)) {
        Write-Host "ERROR: Missing script $scriptPath" -ForegroundColor Red
        return
    }

    $argDisplay = if ($Args.Count -gt 0) { " " + ($Args -join " ") } else { "" }
    Write-Host "==> Running $scriptPath$argDisplay"

    & $PythonExe $scriptPath @Args
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        Write-Warning "Step $ScriptName exited with code $exitCode. Pipeline will continue; in-test fallbacks should handle this."
    }
}

# Step 1: fetch Telegram messages
Run-Step "step01_fetch_telegram.py" @("--channel", $Channel, "--limit", $Limit.ToString())

# Step 2: sentiment via OpenAI (or heuristic fallback)
Run-Step "step02_sentiment_openai.py"

# Step 3: fetch GMGN token data (or stub fallback)
Run-Step "step03_fetch_gmgn.py"

# Step 4: preprocess prices
Run-Step "step04_preprocess_prices.py"

# Step 5: Kalman analysis
Run-Step "step05_kalman_analysis.py"

# Step 6: JumpDiff analysis
Run-Step "step06_jumpdiff_analysis.py"

# Step 7: rBergomi-style analysis
Run-Step "step07_rbergomi_analysis.py"

# Step 8: combine features
Run-Step "step08_combine_features.py"

# Step 9: run RL and produce orders
Run-Step "step09_run_rl.py"

# Step 10: simulate GMGN order calls
Run-Step "step10_simulate_gmgn_order.py"

Write-Host "Pipeline execution finished." -ForegroundColor Green
