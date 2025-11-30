Param(
    [string]$EnvName = "polyo-gpu"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

$tests = @(
    "tests\test_polyo_pipeline.py",
    "tests\use_case_simple.py",
    "tests\use_case_stress_tests.py",
    "tests\test_input_stress.py",
    "tests\test_telegram_signal_pipeline_unit.py"
)

$conda = Get-Command conda -ErrorAction SilentlyContinue

function Ensure-Pytest {
    $checkPytest = @'
import importlib, sys
sys.exit(0 if importlib.util.find_spec("pytest") else 1)
'@
    if ($conda) {
        $checkPytest | conda run -n $EnvName python -
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Installing pytest in '$EnvName'..."
            conda run -n $EnvName python -m pip install pytest -q
        }
    } else {
        python - <<'PY'
import importlib, sys
sys.exit(0 if importlib.util.find_spec("pytest") else 1)
PY
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Installing pytest in current environment..."
            python -m pip install pytest -q
        }
    }
}

function Run-Test {
    param([string]$Path)
    $full = Join-Path $scriptDir $Path
    if (-not (Test-Path $full)) {
        Write-Warning "Test not found: $full"
        return
    }
    Write-Host "Running $Path ..."
    $usePytest = $Path -like "*test_telegram_signal_pipeline_unit.py"
    if ($usePytest) {
        Ensure-Pytest
        if ($conda) {
            conda run -n $EnvName python -m pytest $full
        } else {
            Write-Warning "conda not found, using current python."
            python -m pytest $full
        }
    } else {
        if ($conda) {
            & conda run -n $EnvName python $full
        } else {
            Write-Warning "conda not found, using current python."
            & python $full
        }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "$Path exited with code $LASTEXITCODE"
    } else {
        Write-Host "$Path OK"
    }
}

foreach ($t in $tests) {
    Run-Test -Path $t
}
