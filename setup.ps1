Param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' not found. Please install it and re-run."
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

Require-Command conda

$envFile = Join-Path $scriptDir "environment.yml"
if (-not (Test-Path $envFile)) {
    throw "environment.yml not found at $envFile"
}

# Initialize conda for this session
$condaHook = (& conda "shell.powershell" "hook" 2>$null) -join [Environment]::NewLine
if (-not $condaHook) { throw "Could not initialize conda PowerShell hook." }
Invoke-Expression $condaHook

# Create or update environment
$envName = "polyo-gpu"
$existing = conda env list | Select-String "^\s*$envName\s"
if ($existing) {
    Write-Host "Environment '$envName' already exists. Updating with environment.yml..."
    conda env update -n $envName -f $envFile --prune
} else {
    Write-Host "Creating environment '$envName' from environment.yml..."
    conda env create -f $envFile
}

conda activate $envName

$extraPaths = @(
    (Join-Path $scriptDir "rough_bergomi"),
    (Join-Path $scriptDir "limit-order-book\python")
) -join ";"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$extraPaths;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $extraPaths
}

function Invoke-CmdChecked {
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [Parameter()][string[]]$Args = @()
    )
    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "'$Exe $($Args -join ' ')' failed with exit code $LASTEXITCODE"
    }
}

# GPU detection
$gpuAvailable = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    try {
        nvidia-smi > $null 2>&1
        if ($LASTEXITCODE -eq 0) { $gpuAvailable = $true }
    } catch { $gpuAvailable = $false }
}

function Get-PipVersion {
    param([string]$Name)
    $info = (& pip show $Name 2>$null)
    if (-not $info) { return $null }
    $line = $info | Select-String "^Version:"
    if (-not $line) { return $null }
    return ($line.ToString().Split(":")[1]).Trim()
}

function Ensure-Torch {
    param([bool]$UseGpu)
    $torchVer = Get-PipVersion "torch"
    $tvVer = Get-PipVersion "torchvision"
    $taVer = Get-PipVersion "torchaudio"
    $hasAll = $torchVer -and $tvVer -and $taVer
    $torchHasCuda = $torchVer -and ($torchVer -like "*+cu*")
    $targetIndex = $UseGpu ? "https://download.pytorch.org/whl/cu121" : "https://download.pytorch.org/whl/cpu"

    $needsInstall = $true
    if ($hasAll) {
        if ($UseGpu -and $torchHasCuda) { $needsInstall = $false }
        elseif (-not $UseGpu -and -not $torchHasCuda) { $needsInstall = $false }
    }

    if ($needsInstall) {
        Write-Host "Installing PyTorch stack from $targetIndex ..."
        Invoke-CmdChecked "pip" @("install","--upgrade","--index-url",$targetIndex,"torch","torchvision","torchaudio")
    } else {
        Write-Host "PyTorch/vision/audio already match target; skipping reinstall."
    }
}

Ensure-Torch -UseGpu:$gpuAvailable

# Install JAX
$isLinuxOrWSL = -not $IsWindows
if ($gpuAvailable -and $isLinuxOrWSL) {
    Write-Host "Installing JAX with CUDA 12 support..."
    Invoke-CmdChecked "pip" @("install","--upgrade","jax[cuda12]","-f","https://storage.googleapis.com/jax-releases/jax_cuda_releases.html")
} else {
    Write-Host "Installing JAX CPU build..."
    Invoke-CmdChecked "pip" @("install","--upgrade","jax[cpu]")
}

# Core Python libs (top-ups)
Invoke-CmdChecked "pip" @("install","--upgrade","gymnasium","tensorboard","pyro-ppl","stable-baselines3","ray[rllib]","requests","tqdm","plotly")

function Install-Editable {
    param([string]$Path)
    if (-not (Test-Path $Path)) { throw "Path not found: $Path" }
    $setup = Join-Path $Path "setup.py"
    $pyproject = Join-Path $Path "pyproject.toml"
    if (-not ((Test-Path $setup) -or (Test-Path $pyproject))) {
        Write-Warning "Skipping $Path (no setup.py or pyproject.toml found)."
        return
    }
    Write-Host "pip install -e $Path"
    Invoke-CmdChecked "pip" @("install","-e",$Path)
}

Install-Editable "./rough_bergomi"
Install-Editable "./jumpdiff"
Install-Editable "./hmmlearn"
Install-Editable "./pykalman"
Install-Editable "./RLTrader"
Install-Editable "./TradeMaster"
Install-Editable "./Calibrating-Rough-Volatility-Models-with-Deep-Learning"

# Build limit-order-book C++ engine and Python bindings
$hasMsvc = Get-Command cl -ErrorAction SilentlyContinue
$hasGcc  = Get-Command gcc -ErrorAction SilentlyContinue
$hasClang = Get-Command clang -ErrorAction SilentlyContinue
$compilerAvailable = $hasMsvc -or $hasGcc -or $hasClang
$lobBuilt = $false
if (-not $compilerAvailable) {
    Write-Warning "No C++ compiler (cl/gcc/clang) detected. Skipping limit-order-book build. Install Build Tools for Visual Studio or a suitable toolchain to enable it."
} else {
    Require-Command cmake
    Require-Command ninja
    Push-Location (Join-Path $scriptDir "limit-order-book/cpp")
    New-Item -ItemType Directory -Force -Path "build" | Out-Null
    Push-Location "build"
    Invoke-CmdChecked "cmake" @("-G","Ninja","-DCMAKE_BUILD_TYPE=Release","..")
    Invoke-CmdChecked "ninja"
    Pop-Location
    Pop-Location

    $lobPython = Join-Path $scriptDir "limit-order-book/python"
    $lobSetup = Join-Path $lobPython "setup.py"
    $lobPyproject = Join-Path $lobPython "pyproject.toml"
    if ((Test-Path $lobSetup) -or (Test-Path $lobPyproject)) {
        Push-Location $lobPython
        Invoke-CmdChecked "pip" @("install",".")
        Pop-Location
        $lobBuilt = $true
    } else {
        Write-Warning "limit-order-book/python has no setup.py/pyproject.toml; skipping pip install."
    }
}

# Sanity checks
Write-Host "Running sanity checks..."
$lobFlag = if ($lobBuilt) { "True" } else { "False" }
$sanity = @"
import sys, os, importlib

# Make sure local workspace paths (set in PYTHONPATH) are on sys.path
for p in os.environ.get("PYTHONPATH", "").split(os.pathsep):
    if p and p not in sys.path:
        sys.path.insert(0, p)

def try_import(name):
    try:
        importlib.import_module(name)
        print(f"[OK] import {name}")
        return True
    except Exception as exc:
        print(f"[FAIL] import {name}: {exc}")
        return False

import torch, jax
modules = [
    "hmmlearn",
    "jumpdiff",
    "pykalman",
    "gymnasium",
    "pandas",
    "numpy",
    "rbergomi",
    "trademaster",
]
results = [try_import(m) for m in modules]
lob_ready = $lobFlag
if lob_ready:
    results.append(try_import("limitorderbook"))
    results.append(try_import("olob"))
else:
    print("[SKIP] limit-order-book imports (build not attempted).")

print("torch.cuda.is_available():", torch.cuda.is_available())
print("torch version:", torch.__version__)
print("jax version:", jax.__version__)
print("python version:", sys.version)
print("All modules import status:", results)
"@
python -c $sanity

Write-Host "`nSetup complete."
