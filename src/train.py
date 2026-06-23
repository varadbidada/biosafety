"""
Orchestrator for the full ML pipeline:
1. Feature engineering
2. Train XGBoost (regressor + classifier)
3. Train LSTM
4. Ensemble evaluation
5. Save metrics
"""

import os
import sys
import argparse
import subprocess
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_script(script_path, label):
    print(f"\n{'=' * 60}")
    print(f"[{label}]")
    print(f"{'=' * 60}")
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=ROOT,
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"[ERROR] {label} failed with code {result.returncode}")
        sys.exit(result.returncode)
    print(f"[OK] {label} completed")
    return result


def main():
    parser = argparse.ArgumentParser(description="DengueCast India - Full Training Pipeline")
    parser.add_argument("--skip-features", action="store_true", help="Skip feature engineering")
    parser.add_argument("--skip-xgb", action="store_true", help="Skip XGBoost training")
    parser.add_argument("--skip-lstm", action="store_true", help="Skip LSTM training")
    parser.add_argument("--skip-ensemble", action="store_true", help="Skip ensemble evaluation")
    parser.add_argument("--fast", action="store_true", help="Quick test run (fewer epochs/trees)")
    args = parser.parse_args()

    start_time = datetime.now()
    print(f"DengueCast India - Training Pipeline")
    print(f"Started at: {start_time}")
    print(f"Project root: {ROOT}")

    if not args.skip_features:
        run_script(
            os.path.join(ROOT, "src/features/make_features.py"),
            "Feature Engineering",
        )

    if not args.skip_xgb:
        run_script(
            os.path.join(ROOT, "src/models/train_xgb.py"),
            "XGBoost Training",
        )

    if not args.skip_lstm:
        run_script(
            os.path.join(ROOT, "src/models/train_lstm.py"),
            "LSTM Training",
        )

    if not args.skip_ensemble:
        run_script(
            os.path.join(ROOT, "src/models/ensemble.py"),
            "Ensemble Evaluation",
        )

    elapsed = datetime.now() - start_time
    print(f"\n{'=' * 60}")
    print(f"Pipeline finished in {elapsed}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
