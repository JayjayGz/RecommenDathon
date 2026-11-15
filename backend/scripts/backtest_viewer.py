"""Run with: python -m streamlit run backend/scripts/backtest_viewer.py."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alphaforge.presentation.backtest_viewer import main
from alphaforge.infrastructure.local_data import LocalPortfolioRepository, DEFAULT_DATA_DIR

if __name__ == "__main__":
    main(LocalPortfolioRepository(), DEFAULT_DATA_DIR)
