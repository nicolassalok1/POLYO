param(
    [string]$ApiKey = "",
    [string]$EnvName = "polyo-gpu"
)

# Prépare le PATH pour la toolchain MinGW64 (MSYS2) si présente
$mingw = "C:\msys64\mingw64\bin"
if (Test-Path $mingw) {
    if (-not ($env:PATH -split ";" | Where-Object { $_ -ieq $mingw })) {
        $env:PATH = "$mingw;$env:PATH"
    }
}

# Relayer vers le script principal
$runner = Join-Path $PSScriptRoot "set_keys_and_run.ps1"
if (-not (Test-Path $runner)) {
    Write-Error "set_keys_and_run.ps1 introuvable dans $PSScriptRoot"
    exit 1
}

& $runner -ApiKey $ApiKey -EnvName $EnvName
