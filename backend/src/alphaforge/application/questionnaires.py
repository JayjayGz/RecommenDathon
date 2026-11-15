"""Normalize the supplied fr-CA form by stable IDs, never client labels."""
import math

from .contracts import RequestError

FRENCH_CHOICES = {
    "situation_conjugale": 4, "personnes_a_charge": 4, "revenu_annuel": 5,
    "stabilite_revenus": 4, "dettes": 5, "objectif_investissement": 4,
    "horizon": 4, "besoin_imprevu": 4, "tolerance_risque": 5,
    "reaction_baisse": 4, "connaissances": 4, "secteurs": 9,
    "classes_actifs": 8, "exclusions": 3,
}
FRENCH_IDS = set(FRENCH_CHOICES) | {"fonds_urgence", "precisions_finales"}
TEXT_FIELDS = {"situation_conjugale_autre", "personnes_a_charge_autre", "revenu_annuel_autre",
               "dettes_autre", "objectif_details", "crypto_details", "exclusions_details"}
AMOUNT_FIELDS = {"dette_hypothecaire", "objectif_montant"}
EXTRA_FIELDS = TEXT_FIELDS | AMOUNT_FIELDS | {"partage_charges", "delai_retrait"}
EXTRA_PARENTS = {
    "situation_conjugale_autre": "situation_conjugale", "personnes_a_charge_autre": "personnes_a_charge",
    "partage_charges": "personnes_a_charge", "revenu_annuel_autre": "revenu_annuel",
    "dettes_autre": "dettes", "dette_hypothecaire": "dettes", "objectif_details": "objectif_investissement",
    "objectif_montant": "objectif_investissement", "delai_retrait": "horizon",
    "crypto_details": "classes_actifs", "exclusions_details": "exclusions",
}


def normalize_french(form):
    if (form.get("langue") != "fr-CA" or form.get("devise") != "CAD"
            or not isinstance(form.get("questions"), list) or len(form["questions"]) != len(FRENCH_IDS)):
        raise RequestError("Expected the supplied fr-CA CAD questionnaire")
    rows, missing = {}, []
    for q in form["questions"]:
        if not isinstance(q, dict) or not isinstance(q.get("id"), str) or q["id"] not in FRENCH_IDS or q["id"] in rows:
            raise RequestError("Unknown or duplicate question ID")
        rows[q["id"]] = q
    if set(rows) != FRENCH_IDS:
        raise RequestError("Missing questionnaire questions")
    values, extras = {}, {}
    for key, q in rows.items():
        answer = q.get("reponse")
        if key in FRENCH_CHOICES:
            allowed = {f"{key}_{n}" for n in range(1, FRENCH_CHOICES[key] + 1)}
            if answer is None or answer == []:
                missing.append(key)
            elif key in {"secteurs", "classes_actifs"}:
                if (not isinstance(answer, list) or len(answer) > len(allowed)
                        or any(not isinstance(v, str) or v not in allowed for v in answer)
                        or len(set(answer)) != len(answer)):
                    raise RequestError("Invalid multiple-choice answer")
            elif not isinstance(answer, str) or answer not in allowed:
                raise RequestError("Invalid single-choice answer")
        elif key == "fonds_urgence":
            if answer is None:
                missing.append(key)
            elif type(answer) not in (int, float) or not math.isfinite(answer) or answer < 0:
                raise RequestError("Invalid emergency fund amount")
        elif answer is not None and (not isinstance(answer, str) or len(answer) > 1000):
            raise RequestError("Invalid final notes")
        values[key] = answer
        additional = q.get("champs_complementaires", [])
        if not isinstance(additional, list) or len(additional) > 4:
            raise RequestError("Invalid supplementary fields")
        for item in additional:
            if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                    or item["id"] not in EXTRA_FIELDS or item["id"] in extras
                    or EXTRA_PARENTS.get(item["id"]) != key):
                raise RequestError("Unknown or duplicate supplementary field")
            name, response = item["id"], item.get("reponse")
            if response is not None:
                if name in TEXT_FIELDS and (not isinstance(response, str) or len(response) > 1000):
                    raise RequestError("Invalid supplementary text")
                if name in AMOUNT_FIELDS and (type(response) not in (int, float) or not math.isfinite(response) or response < 0):
                    raise RequestError("Invalid supplementary amount")
                if name == "partage_charges" and response not in ("principalement", "partagees"):
                    raise RequestError("Invalid expense sharing answer")
                if name == "delai_retrait" and response not in ("moins_1_an", "1_3_ans", "4_6_ans", "7_ans_plus"):
                    raise RequestError("Invalid withdrawal timing")
            extras[name] = response
    if extras.get("delai_retrait") is None:
        missing.append("delai_retrait")
    no_notes = rows["precisions_finales"].get("champ_rien_a_ajouter", {})
    if not isinstance(no_notes, dict) or type(no_notes.get("reponse")) not in (bool, type(None)):
        raise RequestError("Invalid final-notes checkbox")
    if no_notes.get("reponse") is True and values.get("precisions_finales"):
        raise RequestError("Conflicting final notes")

    def choice(key, codes):
        value = values[key]
        return codes[int(value.rsplit("_", 1)[1]) - 1] if value else None

    sector_codes = ["technology", "health", "finance", "energy", "real_estate", "industrials",
                    "consumer", "communications", "utilities"]
    asset_codes = ["stocks", "equity_funds", "bonds", "commodity_funds", "crypto", "commodity_futures", "fx"]
    selected_assets = values["classes_actifs"] or []
    assets = asset_codes if "classes_actifs_8" in selected_assets else [asset_codes[int(a.rsplit("_", 1)[1]) - 1] for a in selected_assets]
    answers = {
        "risk": choice("tolerance_risque", ["very_low", "low", "medium", "high", "very_high"]),
        "reaction": choice("reaction_baisse", ["worried", "hesitant", "concerned", "calm"]),
        "income": choice("stabilite_revenus", ["regular", "variable", "fragile", "unknown"]),
        "horizon": choice("horizon", ["1_2", "5", "10", "15_plus"]),
        "exclusions": choice("exclusions", ["none", "limits", "discussion"]),
        "sectors": [sector_codes[int(s.rsplit("_", 1)[1]) - 1] for s in (values["secteurs"] or [])],
        "assets": assets,
        "financial_context": {**values, **extras},
    }
    return answers, sorted(missing)
