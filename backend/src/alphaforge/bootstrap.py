"""Composition root: connect application ports to local infrastructure."""
from .application.portfolio_engine import PortfolioEngine
from .infrastructure.local_data import LocalPortfolioRepository


def create_engine():
    return PortfolioEngine(LocalPortfolioRepository())
