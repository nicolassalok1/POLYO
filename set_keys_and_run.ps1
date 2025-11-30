param(
    [string]$ApiKey = "",
    [string]$EnvName = "polyo-gpu"
)

# Renseigne ton API key ici ou passe-le en argument -ApiKey.
# Si aucune cle n'est fournie, l'app utilisera automatiquement les donnees dummy_gmgn (mode test).

if ($ApiKey -ne "") {
    $env:GMGN_API_KEY = $ApiKey
}

$keyLen = 0
if ($env:GMGN_API_KEY) {
    $keyLen = $env:GMGN_API_KEY.Length
}

Write-Host "GMGN_API_KEY longueur: $keyLen"
if ($keyLen -eq 0) {
    Write-Warning "Aucune cle trouvee, l'app demarrera en mode TEST (dummy data)."
} else {
    Write-Host "Cle detectee, l'app tentera le mode LIVE (GMGN API)."
}

$condaCmd = Get-Command conda -ErrorAction SilentlyContinue
if ($condaCmd) {
    Write-Host "Execution via conda run dans l'env '$EnvName' avec python -m streamlit..."
    conda run -n $EnvName python -m streamlit run app_gmgn_polyo.py
} else {
    Write-Warning "conda introuvable dans cette session; essaie d'activer l'env '$EnvName' manuellement puis relance."
    Write-Host "Tentative d'executer streamlit directement..."
    streamlit run app_gmgn_polyo.py
}
