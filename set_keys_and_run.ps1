# Renseigne tes clés ici (ce fichier est destiné à rester local, ne pas le pousser).
# Exemple d'usage :
#   pwsh -File .\set_keys_and_run.ps1

# =======================
#  CONFIGURE TES CLÉS
# =======================
$env:GMGN_API_KEY = "REMPLACE_PAR_TON_GMGN_API_KEY"

# Ajoute ici d'autres clés si besoin
# $env:OTHER_API_KEY = "..."

Write-Host "Clés chargées dans l'environnement (GMGN_API_KEY longueur: $($env:GMGN_API_KEY.Length))."
Write-Host "Lancement de Streamlit..."

streamlit run app_gmgn.py
