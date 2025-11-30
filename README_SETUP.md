# POLYO Setup Guide (Windows)

Ce document résume l’installation complète pour un clone frais du repo, y compris CUDA, Build Tools, conda, et la résolution des pièges habituels. Objectif : pouvoir lancer `setup.ps1` puis `set_keys_and_run.ps1` sans surprises.

## Prérequis système
- Windows 10/11 64‑bit.
- Droits d’installation (admin recommandé).
- Espace disque suffisant (~15‑20 Go).

## Étape 1 — GPU / CUDA (optionnel mais recommandé)
1. Installe les pilotes NVIDIA récents (GeForce/Quadro selon ton GPU).
2. Installe le **CUDA Toolkit** (version compatible avec cu121 pour torch 2.5.1+cu121).
3. Vérifie avec `nvidia-smi` dans un terminal : si la commande répond, le GPU est visible. Sinon, réinstalle les drivers/CUDA.

> Sans GPU, tout fonctionne en CPU, mais plus lent. Le script avertit si `nvidia-smi` est absent.

## Étape 2 — Build Tools (compilateur C++)
Certaines dépendances (limit-order-book) nécessitent un compilateur C++.
1. Installe **Visual Studio Build Tools** ou **Visual Studio Community**.
2. Sélectionne le workload **“Desktop development with C++”** (inclut MSVC, CMake, Ninja).
3. Redémarre PowerShell après installation pour que `cl.exe` soit dans le PATH (ou ouvre un “Developer PowerShell”).
4. Vérifie avec `cl` dans le terminal ; si non trouvé, relance la session ou exécute `VsDevCmd.bat` de VS.

> Si tu n’as pas besoin de `limit-order-book`, tu peux ignorer l’absence de compilateur (warning seulement).

### Alternative : toolchain MSYS2/MinGW (Windows)
Si tu préfères éviter Visual Studio :
1. Installe **MSYS2** (chemin par défaut `C:\msys64`).
2. Ouvre la console **MSYS2 MINGW64** (icône bleue “M”, pas l’icône violette “MSYS”).
3. Mets à jour MSYS2 :
   ```bash
   pacman -Syu
   # si demandé, relance la console, puis :
   pacman -Syu
   ```
4. Installe la toolchain et les outils :
   ```bash
   pacman -S --needed base-devel mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja
   ```
5. (Optionnel) Ajoute au PATH Windows : `C:\msys64\mingw64\bin` pour utiliser gcc/ninja depuis PowerShell.
6. Redémarre PowerShell et relance `pwsh -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1` : le script détectera `gcc/clang` et tentera de builder `limit-order-book`.

> Rappels : utiliser **MINGW64**, pas MSYS ni CLANG par défaut ; vérifier avec `gcc --version` ou `ninja --version` dans PowerShell après ajout au PATH.

#### Ajouter MINGW64 au PATH depuis PowerShell
- Session courante :
  ```pwsh
  $mingw = "C:\msys64\mingw64\bin"
  if (-not ($env:PATH -split ";" | Where-Object { $_ -ieq $mingw })) {
      $env:PATH = "$mingw;$env:PATH"
  }
  gcc --version
  ninja --version
  cmake --version
  ```
- Persistant (admin) :
  ```pwsh
  $mingw = "C:\msys64\mingw64\bin"
  $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
  if (-not ($machinePath -split ";" | Where-Object { $_ -ieq $mingw })) {
      [Environment]::SetEnvironmentVariable("Path", "$mingw;$machinePath", "Machine")
  }
  ```
  Puis rouvre PowerShell et vérifie `gcc --version`.

## Étape 3 — Miniconda/Conda
1. Installe **Miniconda** ou **Anaconda** (choisir “Add conda to PATH” ou initialise le shell via `conda init powershell`).
2. Ouvre un PowerShell sans profil, teste `conda --version`.

## Étape 4 — Cloner le repo
```pwsh
git clone <repo> POLYO
cd POLYO
```

## Étape 5 — Provisioning automatique
Lancer le setup complet (installe env `polyo-gpu`, PyTorch CUDA, JAX, streamlit, dépendances locales, etc.) :
```pwsh
pwsh -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```
Ce que fait `setup.ps1` :
- Crée/actualise l’env conda `polyo-gpu` avec les packages de base + pybind11.
- Installe streamlit via conda-forge.
- Répare certifi si cassé.
- Réinstalle/upgrade les paquets pip clés (gymnasium, tensorboard, pyro-ppl, stable-baselines3, ray[rllib], requests, tqdm, plotly).
- Installe en editable : jumpdiff, hmmlearn, pykalman, TradeMaster (et saute ceux sans setup).
- Tente de builder limit-order-book (si compilateur dispo). Si aucun `cl/gcc/clang`, warning seulement.
- Fait des sanity checks d’import (hmmlearn, jumpdiff, pykalman, gymnasium, pandas, numpy, rbergomi, trademaster) et affiche torch/jax versions + torch.cuda.is_available().

## Étape 6 — Lancer l’application Streamlit
```pwsh
pwsh -ExecutionPolicy Bypass -File .\set_keys_and_run.ps1
```
Options :
- `-ApiKey "<GMGN_API_KEY>"` (facultatif). Sans clef → mode TEST (dummy data).
- `-EnvName "polyo-gpu"` (par défaut). Le script crée l’env via `setup.ps1` si absent, vérifie streamlit, puis lance `python -m streamlit run app_gmgn_polyo.py` via conda run.

## Pièges fréquents & solutions
- **`conda` introuvable** : réouvre un terminal après `conda init powershell`, ou lance depuis “Anaconda Prompt (PowerShell)”. Assure-toi que Miniconda est sur le PATH.
- **`streamlit` introuvable** : `set_keys_and_run.ps1` l’installera si besoin. Sinon : `conda install -n polyo-gpu -c conda-forge streamlit`.
- **Certifi METADATA manquante** (erreur pip) : `python -m pip install --force-reinstall certifi` (déjà fait dans `setup.ps1`).
- **Compilateur C++ manquant** : installe Build Tools + workload C++; ou ignore si tu n’as pas besoin de limit-order-book.
- **CUDA non détectée** : vérifier `nvidia-smi`, drivers, version CUDA. Sinon, l’app tourne en CPU.
- **Ray/gym versions** : le setup réinstalle les versions compatibles ; en cas de conflit, nettoyer l’env (`conda env remove -n polyo-gpu`) puis relancer `setup.ps1`.

## Commandes utiles
- Supprimer l’env et repartir propre :
  ```pwsh
  conda env remove -n polyo-gpu
  pwsh -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
  ```
- Vérifier GPU : `nvidia-smi`
- Lancer l’app directement si l’env est actif : `python -m streamlit run app_gmgn_polyo.py`
