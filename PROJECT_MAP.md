# POLYO Workspace Map
This root repo is a wrapper that tracks several finance/ML subprojects as git submodules. Use this map to orient ChatGPT or tooling.

## Root contents
- `.gitmodules` — records all submodules and their upstream URLs (github.com/nicolassalok1/...).
- `PROJECT_STRUCTURE.md` — high-level overview of each subproject (already present).
- `environment.yml` — conda spec for env `polyo-gpu` (Python 3.10, core scientific stack, cmake/ninja/make).
- `setup.ps1` — PowerShell setup script: creates env from `environment.yml`, installs PyTorch/JAX, installs local packages editable, optionally builds limit-order-book if a C++ toolchain is present, and runs sanity checks.
- `test_polyo_pipeline.py` — smoke tests/imports across subprojects and a small mock pipeline.
- `POLYO.code-workspace` — VS Code multi-root workspace.

## Submodules (each is its own git repo)
- `Calibrating-Rough-Volatility-Models-with-Deep-Learning/` — notebooks and utils for calibrating rough volatility (Heston/rBergomi). Mostly notebooks; no Python package installable.
- `hmmlearn/` — HMM library (src/hmmlearn). Standard Python package.
- `jumpdiff/` — jump-diffusion parameter estimation (package: jumpdiff).
- `limit-order-book/` — C++20 matching engine with Python bindings under `python/` (olob/). Requires C++ toolchain + cmake/ninja to build.
- `pykalman/` — Kalman filtering package (pykalman/).
- `RLTrader/` — RL trading prototype (not packaged; mainly scripts/configs).
- `rough_bergomi/` — rough volatility demo (rbergomi module in `rbergomi/`).
- `TradeMaster/` — RL trading platform (trademaster package).

## Notes
- Submodules keep their own history; commits here only track their pointers.
- Some folders contain large datasets (e.g., limit-order-book data). Avoid regenerating unless needed.
- To update submodules, use `git submodule update --init --recursive` (already tracked in `.gitmodules`).
