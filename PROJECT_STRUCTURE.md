# Vue d'ensemble du workspace **POLYO**
Ce mémo est prévu pour ChatGPT : il décrit rapidement qui fait quoi dans chaque dossier afin d'éviter de chercher à l'aveugle. Chaque sous-projet est un dépôt cloné (présence de `.git` interne) que le dépôt racine POLYO agrège.

- `Calibrating-Rough-Volatility-Models-with-Deep-Learning/` — notebooks de cours sur l'implémentation et la calibration de modèles de volatilité rugueuse (rBergomi/Heston) ; `data/` contient les données CBOE nettoyées, `rbergomi/` et `utils.py` exposent les briques Python réutilisées par les notebooks.
- `hmmlearn/` — bibliothèque Python de modèles de Markov cachés ; le code vit dans `src/hmmlearn/`, `examples/` illustre l'API, `doc/` sert à la génération de la doc ReadTheDocs, `ext/` contient les extensions C.
- `jumpdiff/` — librairie Python pour estimer les paramètres de processus de diffusion avec sauts ; le package est dans `jumpdiff/`, les tests dans `test/`, la doc utilisateur dans `docs/`.
- `limit-order-book/` — moteur de carnet d'ordres haute performance en C++20 avec bindings Python ; `cpp/` porte le cœur du matching engine, `python/` les wrappers, `analytics/` et `scripts/` fournissent les analyses/benchmarks, `docs/` la documentation.
- `pykalman/` — implémentation Python (Kalman/UKF/EM) ; `pykalman/` contient le package, `examples/` des notebooks, `doc/` les sources Sphinx, `build_tools/` les scripts de packaging/CI.
- `RLTrader/` — proto TensorTrade pour agents RL de trading ; `lib/` porte le code de stratégie/environnements, `config/` les hyperparamètres, `data/` les sorties (tensorboard, agents, logs), `docker/` et `dev-with-docker` facilitent l'exécution containerisée.
- `rough_bergomi/` — démonstrateur Python du modèle de volatilité rugueuse rBergomi ; `rbergomi/` contient le moteur, `notebooks/` des exemples, `papers/` les ressources de référence.
- `TradeMaster/` — plateforme RL complète pour trading quantitatif ; `trademaster/` rassemble les modules RL, `configs/` et `pm/` gèrent la configuration/pipelines, `docs/` et `tutorial/` couvrent la doc, `tools/` les utilitaires d'entraînement/déploiement.
- `POLYO.code-workspace` — configuration VS Code pour ouvrir tous les sous-projets.

Notes pratiques :
- Les datasets lourds (ex. `limit-order-book/taq_quotes.parquet` ou `TradeMaster/data/`) sont déjà présents ici ; évite de les régénérer sans besoin.
- Comme chaque dossier a son propre `.git`, garde en tête que les historiques restent séparés ; le dépôt racine sert surtout de méta-repo/collection.
