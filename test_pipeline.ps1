Param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Script,
        [string[]]$Args = @()
    )
    Write-Host "==> Running $Script $($Args -join ' ')" -ForegroundColor Cyan
    & $PythonExe $Script @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Step $Script failed with exit code $LASTEXITCODE"
    }
}

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Definition)
$pipelineDir = Join-Path (Get-Location) "tests/pipeline_demo"

Invoke-Step (Join-Path $pipelineDir "step01_fetch_telegram.py") @("--channel","@gmgnsignals","--limit","50")
Invoke-Step (Join-Path $pipelineDir "step02_sentiment_openai.py")
Invoke-Step (Join-Path $pipelineDir "step03_fetch_gmgn.py")
Invoke-Step (Join-Path $pipelineDir "step04_preprocess_prices.py")
Invoke-Step (Join-Path $pipelineDir "step05_kalman_analysis.py")
Invoke-Step (Join-Path $pipelineDir "step06_jumpdiff_analysis.py")
Invoke-Step (Join-Path $pipelineDir "step07_rbergomi_analysis.py")
Invoke-Step (Join-Path $pipelineDir "step08_combine_features.py")
Invoke-Step (Join-Path $pipelineDir "step09_run_rl.py")
Invoke-Step (Join-Path $pipelineDir "step10_simulate_gmgn_order.py")

Write-Host "`nPipeline completed. Logs are in tests/pipeline_demo/pipeline_logs" -ForegroundColor Green
