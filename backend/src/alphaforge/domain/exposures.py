"""Expositions pondérées issues du catalogue fourni, sans données inventées."""
from collections import defaultdict
import re

METHOD = "weighted_catalog_exposures_v1"
SECTORS = {
    "technology": {"Technologie de l'information"}, "health": {"Santé"},
    "finance": {"Finance"}, "financial_services": {"Finance"}, "energy": {"Énergie"},
    "real_estate": {"Immobilier"}, "industrials": {"Industrie"},
    "consumer": {"Biens de consommation de base", "Consommation discrétionnaire"},
    "communications": {"Services de communication"}, "utilities": {"Services aux collectivités"},
    "materials": {"Matériaux"}, "other": set(),
}


def parse_allocation(value):
    """Les répartitions absentes ne sont jamais interprétées comme zéro."""
    if value.startswith(("Données non disponibles", "Sans objet")):
        return None
    parts = value.split(";")
    values = {}
    for part in parts:
        match = re.fullmatch(r"\s*(.+?)\s*:\s*(\d+(?:[.,]\d+)?)\s*%\s*", part)
        if not match:
            raise ValueError("Répartition mal formée")
        label, amount = match.groups()
        if label in values:
            raise ValueError("Libellé de répartition répété")
        values[label] = float(amount.replace(",", "."))
    total = sum(values.values())
    if not values or any(v > 100 for v in values.values()) or not 0 < total <= 100.1:
        raise ValueError("Total de répartition invalide")
    # Un léger dépassement dû aux arrondis est conservé dans les valeurs sources.
    divisor = total if total > 100 else 100
    return {"source_pct": values, "fractions": {k: v / divisor for k, v in values.items()},
            "source_total_pct": round(total, 8), "rounding_rescaled": total > 100}


def exposure_review(weights, catalog, answers, allowed_tickers, asset_metadata, constraints):
    """Séparer les référentiels sectoriels et les bases géographiques."""
    dimensions = {}
    for dimension in ("sectors", "geography", "asset_classes"):
        groups = defaultdict(lambda: defaultdict(float))
        contributors = defaultdict(list)
        covered, missing = 0.0, []
        for ticker, weight in sorted(weights.items()):
            if weight <= 0:
                continue
            row = catalog.get(ticker, {})
            allocation = row.get(dimension)
            if allocation is None:
                missing.append(ticker)
                continue
            basis = row[dimension + "_basis"]
            known = sum(allocation["fractions"].values())
            covered += weight * known * 100
            contributors[basis].append(ticker)
            for label, fraction in allocation["fractions"].items():
                groups[basis][label] += weight * fraction * 100
        dimensions[dimension] = {
            "groups": [{"basis": basis, "weights_pct": {k: round(v, 6) for k, v in sorted(values.items()) if v > 0},
                        "tickers": contributors[basis]} for basis, values in sorted(groups.items())],
            "covered_pct": round(covered, 6), "unclassified_pct": round(max(0, 100 - covered), 6),
            "missing_tickers": missing,
        }
    preferred = set().union(*(SECTORS[s] for s in answers.get("sectors", [])))
    gics = next((g["weights_pct"] for g in dimensions["sectors"]["groups"] if g["basis"] == "GICS"), {})
    preference_pct = round(sum(v for label, v in gics.items() if label in preferred), 6)
    insights = []
    if gics:
        largest = sorted(gics, key=lambda label: (-gics[label], label))[0]
        insights.append({"kind": "largest_measured_sector", "sector": largest, "weight_pct": gics[largest],
                         "preferred": largest in preferred})
    if dimensions["sectors"]["missing_tickers"]:
        insights.append({"kind": "incomplete_sector_coverage", "tickers": dimensions["sectors"]["missing_tickers"]})
    # Pistes qualitatives uniquement : aucun poids, aucune simulation ou performance présumée.
    candidates = []
    for ticker in sorted(set(allowed_tickers) - set(weights) - set(constraints.get("excluded_tickers", []))):
        row = catalog.get(ticker, {})
        if row.get("sectors_basis") != "GICS" or not row.get("sectors") or not row.get("description_fr"):
            continue
        sectors = row["sectors"]["fractions"]
        matches = preferred & set(sectors)
        if not matches or asset_metadata[ticker]["asset_class"] != "equity" or "stocks" not in answers.get("assets", []):
            continue
        sector = sorted(matches, key=lambda label: (gics.get(label, 0), label))[0]
        candidates.append({"ticker": ticker, "sector": sector, "current_measured_sector_pct": gics.get(sector, 0),
                           "description_fr": row["description_fr"], "status": "to_study", "applied": False})
    candidates.sort(key=lambda c: (c["current_measured_sector_pct"], c["ticker"]))
    return {"method": METHOD, "dimensions": dimensions, "preferred_sector_weight_pct": preference_pct,
            "preferred_sectors": sorted(preferred), "insights": insights,
            "potential_assets": candidates[:3],
            "limitations": [
                "Les répartitions proviennent des dates et méthodes du catalogue ; elles ne décrivent pas nécessairement les expositions actuelles.",
                "Les bases géographiques restent séparées : siège social, domicile des sociétés d’un indice et objectif d’un fonds ne mesurent pas les revenus par pays.",
                "Les données inconnues ne valent pas zéro. Les titres sous-jacents détaillés et leurs chevauchements ne sont pas établis.",
                "Les pistes d’actifs ne sont ni pondérées ni simulées ; les préférences ne prouvent pas une adéquation financière."
            ]}
