Param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

# GPU detection
$gpuAvailable = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    try {
        nvidia-smi > $null 2>&1
        if ($LASTEXITCODE -eq 0) { $gpuAvailable = $true }
    } catch { $gpuAvailable = $false }
}

# Install PyTorch
if ($gpuAvailable) {
    Write-Host "GPU detected via nvidia-smi. Installing PyTorch with CUDA..."
    pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
} else {
    Write-Host "No GPU detected. Installing CPU PyTorch..."
    pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
}

# Install JAX
$isLinuxOrWSL = -not $IsWindows
if ($gpuAvailable -and $isLinuxOrWSL) {
    Write-Host "Installing JAX with CUDA 12 support..."
    pip install --upgrade "jax[cuda12]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
} else {
    Write-Host "Installing JAX CPU build..."
    pip install --upgrade "jax[cpu]"
}

# Core Python libs (top-ups)
pip install --upgrade gymnasium tensorboard pyro-ppl stable-baselines3 "ray[rllib]" requests tqdm plotly

function Install-Editable {
    param([string]$Path)
    if (-not (Test-Path $Path)) { throw "Path not found: $Path" }
    Write-Host "pip install -e $Path"
    pip install -e $Path
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
if (-not ($hasMsvc -or $hasGcc -or $hasClang)) {
    Write-Warning "No C++ compiler (cl/gcc/clang) detected. Install Build Tools for Visual Studio or a suitable toolchain."
}

Require-Command cmake
Require-Command ninja

Push-Location (Join-Path $scriptDir "limit-order-book/cpp")
New-Item -ItemType Directory -Force -Path "build" | Out-Null
Push-Location "build"
cmake -G "Ninja" -DCMAKE_BUILD_TYPE=Release ..
ninja
Pop-Location
Pop-Location

Push-Location (Join-Path $scriptDir "limit-order-book/python")
pip install .
Pop-Location

# Sanity checks
Write-Host "Running sanity checks..."
$sanity = @'
import sys, torch, jax, importlib
modules = ["hmmlearn", "jumpdiff", "pykalman", "gymnasium", "pandas", "numpy"]
for m in modules:
    importlib.import_module(m)
print("torch.cuda.is_available():", torch.cuda.is_available())
print("torch version:", torch.__version__)
print("jax version:", jax.__version__)
print("python version:", sys.version)
print("All modules imported successfully.")
'@
python -c $sanity

Write-Host "`nSetup complete."
