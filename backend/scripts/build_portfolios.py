"""Regenerate profiles.json from the agreed dataset (overwrites output)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import argparse
from alphaforge.application.reference_portfolios import build_profiles
from alphaforge.infrastructure.local_data import LocalPortfolioRepository

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", nargs="?", default=None, help="Default: repository dataset/")
    parser.add_argument("out", nargs="?", default=None, help="Default: repository profiles.json")
    args = parser.parse_args()
    _, table = build_profiles(LocalPortfolioRepository(), args.data_dir, args.out)
    print(table.to_string(index=False))
