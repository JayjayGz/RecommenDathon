"""Summarize supplied macro data without inferring publication timing or trades."""
import pandas as pd


def macro_context(frame, as_of, bond_tickers=()):
    observations = []
    future_releases = 0
    for series_id, rows in frame.groupby("series_id", sort=True):
        rows = rows[rows.date <= pd.Timestamp(as_of)].sort_values("date")
        if "release_date" in rows:
            future = rows.release_date.notna() & (rows.release_date > pd.Timestamp(as_of))
            future_releases += int(future.sum())
            rows = rows[~future]
        if rows.empty:
            continue
        row = rows.iloc[-1]
        release = row.get("release_date", pd.NaT)
        observations.append({"series_id": str(series_id), "label": row["label"],
            "value": float(row["value"]), "unit": row["unit"], "frequency": row["frequency"],
            "source": row["source"], "reference_date": row.date.date().isoformat(),
            "release_date": release.date().isoformat() if pd.notna(release) else None,
            "publication_timing": "release_date_supplied" if pd.notna(release) else "unverified",
            "allocation_effect": "none"})
    return {"as_of": as_of.isoformat(), "method": "bond_macro_reference_context_v1", "series": observations,
            "asset_class_scope": "etf_bond", "applies_to_tickers": sorted(bond_tickers),
            "excluded_future_releases": future_releases,
            "limitations": [
                "Macro figures provide context only for the evaluated bond assets, not equity or other asset-class forecasts. No macro-to-weight rule is configured.",
                "Reference dates do not establish publication dates. Missing release dates and revised data prevent certification that a macro value was available historically.",
                "Each macro series may end before the requested as-of date; the reported reference date exposes that coverage. No missing macro observations are filled.",
            ]}
