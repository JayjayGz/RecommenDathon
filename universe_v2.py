# AlphaForge team universe (v2). Paste this list over UNIVERSE in build_dataset.py.
# ticker, name, asset_class, market, currency (listing currency), sector
#
# Selection rules (team assumptions, document in the technical documentation):
#  - Canadian investor: prefer CAD-listed funds; U.S. assets where no CAD-listed equivalent fits the style.
#  - Diversified ETFs form the core; single stocks only where a style needs them.
#  - Single stocks: among the largest companies in their sector in Nov 2021 (start of the window),
#    or long-standing dividend payers, to limit survivorship bias.
#  - Full price history from 2021-11-12 (the build script warns if a history starts later).

UNIVERSE = [
    # Bonds and cash (5)
    ("ZAG.TO",  "BMO Aggregate Bond Index ETF",                      "etf_bond",   "TSX",       "CAD", "Bonds (Canada aggregate)"),
    ("XSB.TO",  "iShares Core Canadian Short Term Bond Index ETF",   "etf_bond",   "TSX",       "CAD", "Bonds (Canada short-term)"),
    ("ZST.TO",  "BMO Ultra Short-Term Bond ETF",                     "etf_bond",   "TSX",       "CAD", "Bonds (Canada ultra short-term)"),
    ("XRB.TO",  "iShares Canadian Real Return Bond Index ETF",       "etf_bond",   "TSX",       "CAD", "Bonds (Canada inflation-linked)"),
    ("BND",     "Vanguard Total Bond Market ETF",                    "etf_bond",   "NASDAQ",    "USD", "Bonds (U.S. aggregate)"),
    # Broad equity core (4)
    ("XIC.TO",  "iShares Core S&P/TSX Capped Composite Index ETF",   "etf_equity", "TSX",       "CAD", "Broad market (Canada)"),
    ("VFV.TO",  "Vanguard S&P 500 Index ETF",                        "etf_equity", "TSX",       "CAD", "Broad market (U.S.)"),
    ("XEF.TO",  "iShares Core MSCI EAFE IMI Index ETF",              "etf_equity", "TSX",       "CAD", "Broad market (international developed)"),
    ("XEC.TO",  "iShares Core MSCI Emerging Markets IMI Index ETF",  "etf_equity", "TSX",       "CAD", "Broad market (emerging markets)"),
    # Style and theme funds (6)
    ("QQQ",     "Invesco QQQ Trust (Nasdaq-100)",                    "etf_equity", "NASDAQ",    "USD", "Growth (U.S. tech-heavy)"),
    ("XIT.TO",  "iShares S&P/TSX Capped Information Technology Index ETF", "etf_equity", "TSX", "CAD", "Growth (Canada tech)"),
    ("VDY.TO",  "Vanguard FTSE Canadian High Dividend Yield Index ETF", "etf_equity", "TSX",    "CAD", "Income (Canada dividend)"),
    ("SCHD",    "Schwab U.S. Dividend Equity ETF",                   "etf_equity", "NYSE Arca", "USD", "Income (U.S. dividend)"),
    ("XESG.TO", "iShares ESG Aware MSCI Canada Index ETF",           "etf_equity", "TSX",       "CAD", "ESG (Canada)"),
    ("ESGV",    "Vanguard ESG U.S. Stock ETF",                       "etf_equity", "Cboe BZX",  "USD", "ESG (U.S.)"),
    # Alternatives (3)
    ("GLD",     "SPDR Gold Shares",                                  "etf_commodity", "NYSE Arca", "USD", "Gold"),
    ("BTC-USD", "Bitcoin",                                           "crypto",     "Crypto (24/7)", "USD", "Crypto asset"),
    ("ETH-USD", "Ether",                                             "crypto",     "Crypto (24/7)", "USD", "Crypto asset"),
    # Canadian stocks (8)
    ("RY.TO",   "Royal Bank of Canada",                              "equity",     "TSX",       "CAD", "Financials"),
    ("TD.TO",   "Toronto-Dominion Bank",                             "equity",     "TSX",       "CAD", "Financials"),
    ("FTS.TO",  "Fortis",                                            "equity",     "TSX",       "CAD", "Utilities"),
    ("ENB.TO",  "Enbridge",                                          "equity",     "TSX",       "CAD", "Energy"),
    ("CNR.TO",  "Canadian National Railway",                         "equity",     "TSX",       "CAD", "Industrials"),
    ("ATD.TO",  "Alimentation Couche-Tard",                          "equity",     "TSX",       "CAD", "Consumer Staples"),
    ("SHOP.TO", "Shopify",                                           "equity",     "TSX",       "CAD", "Information Technology"),
    ("CSU.TO",  "Constellation Software",                            "equity",     "TSX",       "CAD", "Information Technology"),
    # U.S. stocks (5)
    ("MSFT",    "Microsoft",                                         "equity",     "NASDAQ",    "USD", "Information Technology"),
    ("NVDA",    "NVIDIA",                                            "equity",     "NASDAQ",    "USD", "Information Technology"),
    ("JNJ",     "Johnson & Johnson",                                 "equity",     "NYSE",      "USD", "Health Care"),
    ("PG",      "Procter & Gamble",                                  "equity",     "NYSE",      "USD", "Consumer Staples"),
    ("TSLA",    "Tesla",                                             "equity",     "NASDAQ",    "USD", "Consumer Discretionary"),
    # Benchmarks for validation, not held in profiles (3)
    ("VCNS.TO", "Vanguard Conservative ETF Portfolio",               "etf_balanced", "TSX",     "CAD", "Benchmark (conservative, about 40% stocks)"),
    ("VBAL.TO", "Vanguard Balanced ETF Portfolio",                   "etf_balanced", "TSX",     "CAD", "Benchmark (balanced, about 60% stocks)"),
    ("VGRO.TO", "Vanguard Growth ETF Portfolio",                     "etf_balanced", "TSX",     "CAD", "Benchmark (growth, about 80% stocks)"),
]
