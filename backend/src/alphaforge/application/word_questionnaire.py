"""Adapt the browser's Word questionnaire to the supplied French form by stable IDs."""
import math

from .contracts import RequestError
from .questionnaires import normalize_french

WORD_VERSION = "questionnaire-word-16-v4"
WORD_VERSIONS = (WORD_VERSION, "questionnaire-word-16-v2")
# Option order is the same as the supplied French questionnaire, not a risk score.
CHOICES = {
    "marital": ("situation_conjugale", ("single", "partnered", "separated", "other")),
    "dependents": ("personnes_a_charge", ("none", "one", "many", "other")),
    "annualIncome": ("revenu_annuel", ("under_50k", "50_100k", "100_150k", "150k_plus", "other")),
    "income": ("stabilite_revenus", ("regular", "variable", "fragile", "unknown")),
    "debt": ("dettes", ("none", "under_25k", "25_100k", "100k_plus", "other")),
    "goal": ("objectif_investissement", ("retirement", "project", "wealth", "other")),
    "horizon": ("horizon", ("1_2", "5", "10", "15_plus")),
    "liquidity": ("besoin_imprevu", ("no", "partly", "yes", "unknown")),
    "risk": ("tolerance_risque", ("very_low", "low", "medium", "high", "very_high")),
    "reaction": ("reaction_baisse", ("worried", "hesitant", "concerned", "calm")),
    "knowledge": ("connaissances", ("beginner", "basic", "good", "advanced")),
    "sectors": ("secteurs", ("technology", "health", "finance", "energy", "real_estate", "industry", "consumer", "communications", "utilities")),
    "assets": ("classes_actifs", ("stocks", "equity_funds", "bonds", "alternatives", "crypto", "futures", "fx", "all")),
    "exclusions": ("exclusions", ("none", "limits", "discussion")),
}
# key -> French supplementary ID, parent, visible choices (None means always visible).
DETAILS = {
    "maritalOther": ("situation_conjugale_autre", "marital", ("other",)),
    "dependentsOther": ("personnes_a_charge_autre", "dependents", ("other",)),
    "supportMode": ("partage_charges", "dependents", ("one", "many", "other")),
    "incomeOther": ("revenu_annuel_autre", "annualIncome", ("other",)),
    "debtOther": ("dettes_autre", "debt", ("other",)),
    "mortgageAmount": ("dette_hypothecaire", "debt", None),
    "goalDetails": ("objectif_details", "goal", ("project", "other")),
    "targetAmount": ("objectif_montant", "goal", None),
    "withdrawalTiming": ("delai_retrait", "horizon", None),
    "cryptoDetails": ("crypto_details", "assets", ("crypto", "all")),
    "exclusionDetails": ("exclusions_details", "exclusions", ("limits", "discussion")),
}
DETAIL_CHOICES = {
    "supportMode": {"main": "principalement", "shared": "partagees"},
    "withdrawalTiming": {"under_1": "moins_1_an", "1_3": "1_3_ans", "4_6": "4_6_ans", "7_plus": "7_ans_plus"},
}


def _amount(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 1000


def normalize_word(questionnaire):
    if (set(questionnaire) != {"version", "answers"} or questionnaire["version"] not in WORD_VERSIONS
            or not isinstance(questionnaire["answers"], dict)):
        raise RequestError("Invalid Word questionnaire contract")
    answers = questionnaire["answers"]
    if questionnaire["version"] == WORD_VERSION and (
            answers.get("marital") == "separated" or answers.get("exclusions") == "discussion"
            or "targetAmount" in answers):
        raise RequestError("Cette réponse a été retirée du questionnaire actuel")
    if set(answers) - (set(CHOICES) | set(DETAILS) | {"emergencyFund", "notes", "noNotes"}):
        raise RequestError("Unknown Word questionnaire fields")
    rows = {}
    for key, (french, options) in CHOICES.items():
        value = answers.get(key)
        response = None
        if key in answers:
            if key in {"sectors", "assets"}:
                if (not isinstance(value, list) or not value
                        or any(not isinstance(v, str) or v not in options for v in value)
                        or len(set(value)) != len(value) or ("all" in value and len(value) != 1)):
                    raise RequestError("Invalid Word questionnaire selections")
                response = [f"{french}_{options.index(v) + 1}" for v in value]
            else:
                if not isinstance(value, str) or value not in options:
                    raise RequestError("Invalid Word questionnaire choice")
                response = f"{french}_{options.index(value) + 1}"
        rows[key] = {"id": french, "reponse": response}
    for key, (french, parent, visible) in DETAILS.items():
        if key not in answers:
            continue
        value, selected = answers[key], answers.get(parent)
        if visible and not any(v in selected if isinstance(selected, list) else v == selected for v in visible):
            raise RequestError("Hidden Word questionnaire field")
        if key in DETAIL_CHOICES:
            if not isinstance(value, str) or value not in DETAIL_CHOICES[key]:
                raise RequestError("Invalid Word supplementary choice")
            value = DETAIL_CHOICES[key][value]
        elif key in {"mortgageAmount", "targetAmount"}:
            if not _amount(value):
                raise RequestError("Invalid Word supplementary amount")
        elif not _text(value):
            raise RequestError("Invalid Word supplementary text")
        rows[parent].setdefault("champs_complementaires", []).append({"id": french, "reponse": value})
    if "emergencyFund" in answers and not _amount(answers["emergencyFund"]):
        raise RequestError("Invalid emergency fund amount")
    if "notes" in answers and not _text(answers["notes"]):
        raise RequestError("Invalid final notes")
    if "noNotes" in answers and type(answers["noNotes"]) is not bool:
        raise RequestError("Invalid final-notes checkbox")
    if answers.get("noNotes") is True and "notes" in answers:
        raise RequestError("Conflicting final notes")
    questions = list(rows.values()) + [
        {"id": "fonds_urgence", "reponse": answers.get("emergencyFund")},
        {"id": "precisions_finales", "reponse": answers.get("notes"),
         "champ_rien_a_ajouter": {"reponse": answers.get("noNotes")}},
    ]
    return normalize_french({"langue": "fr-CA", "devise": "CAD", "questions": questions})
