You are Codex. Generate a Python script named `test_polyo_pipeline.py` that systematically tests all submodules of the POLYO project workspace.

REQUIREMENTS:

1. **Test Each Submodule**: For each POLYO subproject (rough_bergomi, jumpdiff, hmmlearn, pykalman, limit-order-book, RLTrader, TradeMaster, etc.), write a test function that:
   - Imports the module.
   - Executes a minimal representative function (e.g., simulate paths, run Kalman filter, train a small RL model).
   - Logs the inputs and outputs of that function (print to console or use Python logging).

2. **Test Inter-Module Communication**: Create a pipeline test that:
   - Runs a small end-to-end scenario using outputs from one module as inputs to the next.
   - For example, simulate rough volatility paths, pass them through a jump-diffusion model, apply a Kalman filter, and then feed the final state into an RL environment.
   - Verify that each step produces the expected output format.

3. **Logging**:
   - Each test function should print/log:
     - The function name being tested.
     - The sample inputs used.
     - The outputs obtained.

4. **Final Result Check**:
   - After running all individual tests, run a final “integration test” that chains multiple modules together to simulate a small end-to-end trading scenario on a mock shitcoin dataset.
   - Log whether the final combined pipeline runs without errors.

OUTPUT:
Generate the entire `test_polyo_pipeline.py` script in one go, including all necessary imports, test functions for each submodule, and a final integration test function.

---

Tu peux copier ce prompt dans Codex. Le script produit permettra de vérifier que chaque sous-module s’exécute correctement et que toute la chaîne fonctionne de bout en bout.
