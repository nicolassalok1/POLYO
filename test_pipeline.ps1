Param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Script,
        [string[]]$StepArgs = @(),
        [string]$LogName
    )
    Write-Host "==> Running $Script $($StepArgs -join ' ')" -ForegroundColor Cyan
    & $PythonExe $Script @StepArgs
    $logPath = Join-Path $logDir $LogName
    $hasContent = (Test-Path $logPath) -and ((Get-Item $logPath).Length -gt 0)
    if ($LASTEXITCODE -eq 0 -and $hasContent) {
        Write-Host "STATUS [$LogName]: SUCCESS" -ForegroundColor Green
    } elseif ($LASTEXITCODE -ne 0 -and $hasContent) {
        Write-Warning "STATUS [$LogName]: WARNING (step failed but log has content; downstream may use fallback)."
    } else {
        Write-Error "STATUS [$LogName]: ERROR (log empty or step failed); downstream will use fallback."
    }
}

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Definition)
$pipelineDir = Join-Path (Get-Location) "tests/pipeline_demo"
$logDir = Join-Path $pipelineDir "pipeline_logs"

# Clear logs at start; emptiness signals fallback usage if a step fails.
Get-ChildItem -Path $logDir -Filter "*.log" -ErrorAction SilentlyContinue | ForEach-Object {
    $_.FullName | Out-Null
    Set-Content -Path $_.FullName -Value ""
}

Invoke-Step -Script (Join-Path $pipelineDir "step01_fetch_telegram.py") -StepArgs @("--channel","https://t.me/gmgnsignals/3993253","--limit","1") -LogName "step01_telegram_messages.log"
Invoke-Step -Script (Join-Path $pipelineDir "step02_sentiment_openai.py") -LogName "step02_sentiment.log"
Invoke-Step -Script (Join-Path $pipelineDir "step03_fetch_gmgn.py") -LogName "step03_gmgn_data.log"
Invoke-Step -Script (Join-Path $pipelineDir "step04_preprocess_prices.py") -LogName "step04_preprocessed.log"
Invoke-Step -Script (Join-Path $pipelineDir "step05_kalman_analysis.py") -LogName "step05_kalman.log"
Invoke-Step -Script (Join-Path $pipelineDir "step06_jumpdiff_analysis.py") -LogName "step06_jumpdiff.log"
Invoke-Step -Script (Join-Path $pipelineDir "step07_rbergomi_analysis.py") -LogName "step07_rbergomi.log"
Invoke-Step -Script (Join-Path $pipelineDir "step08_combine_features.py") -LogName "step08_combined_features.log"
Invoke-Step -Script (Join-Path $pipelineDir "step09_run_rl.py") -LogName "step09_orders.log"
Invoke-Step -Script (Join-Path $pipelineDir "step10_simulate_gmgn_order.py") -LogName "step10_simulated_calls.log"

Write-Host "`nPipeline completed. Logs are in tests/pipeline_demo/pipeline_logs" -ForegroundColor Green
