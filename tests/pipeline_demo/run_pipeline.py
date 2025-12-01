from __future__ import annotations

import subprocess
import sys
from pathlib import Path


STEPS = [
    ("step01_fetch_telegram.py", ["--channel", "@gmgnsignals", "--limit", "50"]),
    ("step02_sentiment_openai.py", []),
    ("step03_fetch_gmgn.py", []),
    ("step04_preprocess_prices.py", []),
    ("step05_kalman_analysis.py", []),
    ("step06_jumpdiff_analysis.py", []),
    ("step07_rbergomi_analysis.py", []),
    ("step08_combine_features.py", []),
    ("step09_run_rl.py", []),
    ("step10_simulate_gmgn_order.py", []),
]


def run_step(script: str, args: list[str]) -> int:
    cmd = [sys.executable, str(Path(__file__).resolve().parent / script)] + args
    return subprocess.call(cmd)


def main() -> None:
    for script, args in STEPS:
        code = run_step(script, args)
        if code != 0:
            print(f"[runner] Step {script} exited with code {code}; aborting.")
            sys.exit(code)
    print("[runner] Pipeline completed (logs are under pipeline_demo/pipeline_logs).")


if __name__ == "__main__":
    main()
