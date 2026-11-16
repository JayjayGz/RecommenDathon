"""Traceable questionnaire understanding. Pure rules; no model, I/O or risk invention."""
from copy import deepcopy
import hashlib
import json
import re

from .profile_matching import CLASS_PREFERENCES, SECTOR_PREFERENCES
from .request_language import asset_mentions, asset_aliases, fold

METHOD = "questionnaire_understanding_v1"
SECTOR_WORDS = {
    "technology": ("technologie", "technologies", "technologique", "technology"),
    "health": ("santé", "santé publique", "health", "healthcare"),
    "finance": ("finance", "financier", "financiers", "banques", "financials"),
    "energy": ("énergie", "energy"), "real_estate": ("immobilier", "real estate"),
    "industrials": ("industrie", "industriel", "industrials"),
    "consumer": ("consommation", "consumer"),
    "communications": ("communications", "télécommunications"),
    "utilities": ("services aux collectivités", "services publics", "utilities"),
}
ASSET_WORDS = {
    "stocks": ("actions individuelles", "actions directes", "actions", "stocks"),
    "equity_funds": ("fonds d'actions", "fnb d'actions", "equity funds"),
    "bonds": ("obligations", "obligataire", "obligataires", "bonds"),
    "commodity_funds": ("matières premières", "fonds de matières premières", "commodity funds"),
    "crypto": ("cryptomonnaies", "cryptomonnaie", "crypto", "cryptocurrencies"),
    "commodity_futures": ("contrats à terme", "futures"),
    "fx": ("devises", "forex", "currency trading"),
}
STYLE_WORDS = {
    "Home country": ("canada", "canadien", "canadiennes", "canadiens"),
    "Income and stability": ("complément de revenu", "revenu régulier", "revenus réguliers", "dividendes"),
    "Growth and innovation": ("croissance", "innovation", "growth"),
    "Broad diversifier": ("diversifié", "diversification", "diversifier"),
    "Responsible (ESG)": ("esg", "responsable", "responsables", "durable"),
}
RISK_FIELDS = {"risk", "reaction", "knowledge", "horizon", "income"}
TEXT_FIELDS = {"situation_conjugale_autre", "personnes_a_charge_autre", "revenu_annuel_autre",
               "dettes_autre", "objectif_details", "crypto_details", "exclusions_details",
               "precisions_finales", "otherSector", "cryptoDetails", "exclusionDetails"}
LABELS = {
    "personnes_a_charge": "personnes à charge", "revenu_annuel": "revenu annuel",
    "dettes": "dettes", "fonds_urgence": "fonds d'urgence", "objectif_investissement": "objectif",
    "besoin_imprevu": "besoin de liquidités", "situation_conjugale": "situation familiale",
}


def signature(answers):
    return hashlib.sha256(json.dumps(answers, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def leaves(value, path=""):
    if isinstance(value, dict):
        for key in sorted(value):
            yield from leaves(value[key], f"{path}.{key}" if path else key)
    else:
        yield path, value


def text_inputs(answers):
    for path, value in leaves(answers):
        if isinstance(value, str) and (".question_context." in path or path.rsplit(".", 1)[-1] in TEXT_FIELDS):
            if value.strip():
                yield {"field": path, "text": value}


def mentions(text, aliases):
    found = set()
    for code, values in aliases.items():
        if any(re.search(r"(?<!\w)" + re.escape(fold(value)) + r"(?!\w)", fold(text)) for value in values):
            found.add(code)
    return found


def text_intent(text, field):
    value = fold(text)
    if re.search(r"\b(ignore|contourne|systeme|instructions?|garantis|guarantee)\b", value):
        return "untrusted_instruction"
    if re.search(r"\b(si|peut-etre|hypothetique|eventuellement)\b", value):
        return "ambiguous"
    if re.search(r"\bpas\s+seulement\b", value):
        return "context"
    if re.search(r"(?:ne\s+pas\s+exclure|n[' ]exclu\w*\s+pas|ne\b.{0,40}\bpas\s+exclure|sans\s+exclure)", value):
        return "ambiguous"
    if re.search(r"\b(exclure|exclus|excluez|eviter|sans|aucun|aucune|ni|sauf|no|without|except|exclude|avoid)\b|\bpas\s+", value):
        return "exclude"
    if re.search(r"\bnot\b", value):
        return "ambiguous"
    if re.search(r"\bne\b.{0,60}\bpas\b|\bn[' ]\w+.{0,40}\bpas\b", value):
        return "ambiguous"
    if field.endswith("exclusions_details") or field == "exclusionDetails":
        return "exclude"
    if re.search(r"\b(prefer\w*|privilegi\w*|souhait\w*|veux|voudrais|aimerais|interess\w*|favoris\w*|penche|attir\w*|investir|cherche|uniquement|seulement|exclusivement)\b", value):
        return "prefer"
    if field.endswith(("crypto_details", ".sectors", ".assets")) and (
            mentions(text, SECTOR_WORDS) or mentions(text, ASSET_WORDS)):
        return "prefer"
    if field.endswith("objectif_details") and mentions(text, STYLE_WORDS):
        return "prefer"
    return "context"


def questionnaire_mentions(text, assets):
    found = asset_mentions(text, assets)
    ambiguous_words = {"A", "ON", "IT", "ALL", "OR", "ARE", "TO", "DE", "ET", "SI", "UN", "EN", "NO"}
    return {ticker for ticker in found if ticker not in ambiguous_words
            or re.search(r"(?<![\w.^=-])" + re.escape(ticker) + r"(?![\w.^=-])", text)
            or (fold(assets[ticker]["name"]) != fold(ticker) and fold(assets[ticker]["name"]) in fold(text))}


def understand_questionnaire(answers, assets):
    """Each received field has an explicit use; unresolvable instructions stay visible."""
    original = deepcopy(answers)
    effective = deepcopy(answers)
    preferences = {"sectors": set(), "assets": set(), "tickers": set(), "styles": set()}
    excluded_tickers, excluded_classes, only_classes = set(), set(), set()
    findings, signals, fields = [], [], []
    texts = list(text_inputs(answers))
    text_paths = {row["field"] for row in texts}
    for path, value in leaves(original):
        root = path.split(".")[0]
        usage = ("risk_mapping" if root in RISK_FIELDS else "preference_matching"
                 if root in {"assets", "sectors"} else "constraint_resolution"
                 if root == "exclusions" or path.endswith("exclusions_details") else
                 "language_interpretation" if path in text_paths else "context_review")
        fields.append({"field": path, "value": deepcopy(value), "usage": usage,
                       "status": "examined", "source": "questionnaire"})

    def finding(code, field, message, blocking=False):
        item = {"code": code, "field": field, "message": message, "blocking": blocking}
        if item not in findings:
            findings.append(item)

    for row in texts:
        folded = fold(row["text"])
        # Clear conflicts are questions to resolve, never replacement scores.
        if (answers.get("knowledge") not in {None, "beginner"}
                and re.search(r"\bje (?:suis (?:debutant|novice)|debute)\b", folded)):
            finding("CONTRADICTORY_KNOWLEDGE", row["field"], "Vos connaissances cochées et votre précision de débutant diffèrent. Confirmez votre expérience.", True)
        if (answers.get("income") == "regular"
                and re.search(r"\bmes revenus sont (?:fragiles|incertains|instables)\b", folded)):
            finding("CONTRADICTORY_INCOME_STABILITY", row["field"], "Des revenus réguliers sont cochés, mais la précision les décrit comme incertains. Confirmez leur stabilité.", True)
        if answers.get("risk") in {"high", "very_high"} and re.search(
                r"(?:je ne (?:peux|veux) (?:supporter|accepter) aucune perte|je veux (?:un capital|mon capital) garanti)", folded):
            finding("CONTRADICTORY_LOSS_TOLERANCE", row["field"], "La tolérance élevée cochée contredit une demande de capital garanti ou de perte nulle. Aucun portefeuille risqué ne peut garantir le capital.", True)
        timing = re.search(r"(?:ma retraite|j[' ](?:ai|aurai) besoin|je (?:compte|prevois|dois) (?:retirer|utiliser)).{0,50}\bdans\s+(\d{1,2})\s+(ans?|mois)\b", folded)
        if timing:
            lower = {"1_2": 1, "5": 5, "10": 10, "15_plus": 15}.get(answers.get("horizon"))
            months = int(timing[1]) if timing[2] == "mois" else int(timing[1]) * 12
            if lower is not None and months < lower * 12:
                finding("CONTRADICTORY_HORIZON", row["field"], "Le texte prévoit d'utiliser l'épargne avant l'horizon coché. Confirmez l'horizon et la part qui doit rester disponible.", True)
        # Split sentences and adversative clauses without splitting ticker suffixes.
        clauses = re.split(r"[;\n]|[.!?](?:\s+|$)|\bmais\b|\bet\s+(?=(?:pas|sans|je)\b)", row["text"], flags=re.I)
        for clause in filter(str.strip, clauses):
            intent = text_intent(clause, row["field"])
            sectors = mentions(clause, SECTOR_WORDS)
            classes = mentions(clause, ASSET_WORDS)
            if not classes and mentions(clause, {"funds": ("ETF", "FNB")}):
                classes.add("funds")
            tickers = questionnaire_mentions(clause, assets)
            styles = mentions(clause, STYLE_WORDS)
            if intent == "context" and row["field"].endswith("crypto_details") and tickers:
                intent = "prefer"
            if intent == "untrusted_instruction":
                relevant_exclusion = bool((sectors or classes or tickers) and re.search(
                    r"\b(sans|exclure|eviter|pas|aucun|aucune|no|without|except)\b", fold(clause)))
                finding("INSTRUCTION_NOT_APPLIED", row["field"],
                        "Une instruction adressée au système ne modifie pas les règles de sélection. Confirmez séparément toute exclusion formulée dans cette phrase.", relevant_exclusion)
                continue
            if intent == "ambiguous":
                if sectors or classes or tickers or styles:
                    finding("AMBIGUOUS_NOTE", row["field"], "Précisez si cette préférence est ferme, sans condition ni double négation.", True)
                continue
            if intent == "context":
                if (sectors or classes or tickers) and re.search(r"\d\s*%|\b(maximum|plafond)\b", fold(clause)):
                    finding("EXPLICIT_ALLOCATION_NEEDS_CONFIRMATION", row["field"], "La précision contient une limite ou un poids de placement. Confirmez sa portée avant de choisir un modèle ; aucun poids n'est supposé.", True)
                continue
            if intent == "exclude":
                if sectors or "Responsible (ESG)" in styles:
                    finding("UNVERIFIABLE_EXCLUSION", row["field"], "Une exclusion sectorielle, d'activité ou ESG exige une vérification des sous-jacents que le catalogue ne fournit pas.", True)
                    continue
                if not tickers and not classes:
                    finding("UNRESOLVED_EXCLUSION", row["field"], "Indiquez les symboles ou noms complets du catalogue et précisez ce que vous souhaitez exclure.", True)
                    continue
                # Validate the whole exclusion clause, including unknown tails,
                # even when it appeared in final notes or a general precision.
                residual = fold(clause)
                for ticker in sorted(tickers, key=len, reverse=True):
                    for alias in sorted(asset_aliases(ticker, assets[ticker]), key=len, reverse=True):
                        residual = re.sub(r"(?<!\w)" + re.escape(fold(alias)) + r"(?!\w)", " ", residual)
                for code in classes:
                    for alias in sorted(ASSET_WORDS.get(code, ("ETF", "FNB")), key=len, reverse=True):
                        residual = re.sub(r"(?<!\w)" + re.escape(fold(alias)) + r"(?!\w)", " ", residual)
                residual = re.sub(r"\b(?:je|ne|n|veux|souhaite|voudrais|exclure|exclus|excluez|eviter|sans|pas|de|d|des|les|le|la|l|et|ou|aucun|aucune|ni|tout|sauf|no|without|except|exclude|avoid)\b", " ", residual)
                if re.sub(r"[\s,:'’.-]+", "", residual):
                    finding("UNRESOLVED_EXCLUSION", row["field"], "Une partie de l'exclusion n'est pas reconnue. Précisez la liste complète ; aucune partie n'est ignorée.", True)
                    continue
                excluded_tickers.update(tickers)
                excluded_classes.update(classes)
            else:
                if (sectors or classes or tickers) and re.search(r"\d\s*%|\b(maximum|plafond|imperativement|obligatoirement|absolument)\b", fold(clause)):
                    finding("EXPLICIT_ALLOCATION_NEEDS_CONFIRMATION", row["field"], "La précision impose une présence, une limite ou un poids. Confirmez cette contrainte avant de choisir un modèle ; aucun poids n'est supposé.", True)
                    continue
                preferences["sectors"].update(sectors)
                preferences["assets"].update(classes)
                preferences["tickers"].update(tickers)
                preferences["styles"].update(styles)
                if classes and re.search(r"\b(uniquement|seulement|exclusivement)\b", fold(clause)):
                    only_classes.update(classes)
                if "Responsible (ESG)" in styles:
                    finding("ESG_STYLE_NOT_CERTIFIED", row["field"], "Le style responsable est une préférence de modèle ; le catalogue ne certifie pas les critères ESG des placements.")
                if not (sectors or classes or tickers or styles):
                    finding("CONTEXT_WITHOUT_SELECTION_RULE", row["field"], "Cette précision est conservée comme contexte ; elle ne définit pas une préférence de placement vérifiable.")
            for kind, values in (("sectors", sectors), ("assets", classes), ("tickers", tickers), ("styles", styles)):
                for value in sorted(values):
                    signals.append({"kind": kind, "value": value, "intent": intent,
                                    "field": row["field"], "quote": clause.strip(), "source": "deterministic"})

    requested = set(answers.get("assets", []))
    if only_classes:
        allowed = set().union(*(CLASS_PREFERENCES[code] for code in only_classes))
        chosen = set().union(*(CLASS_PREFERENCES[code] for code in requested))
        if chosen - allowed:
            finding("CONTRADICTORY_EXCLUSIVE_PREFERENCE", "assets", "La précision demande une seule catégorie alors que d'autres catégories sont cochées. Confirmez les catégories autorisées.", True)
        excluded_tickers.update(t for t, metadata in assets.items() if metadata["asset_class"] not in allowed)
    if excluded_classes & (requested | preferences["assets"]):
        finding("CONTRADICTORY_ASSET_PREFERENCES", "assets", "Une classe d'actifs est à la fois demandée et exclue. Confirmez votre préférence.", True)
    if excluded_tickers & preferences["tickers"]:
        finding("CONTRADICTORY_TICKER_PREFERENCES", "notes", "Un actif est à la fois préféré et exclu. Confirmez votre choix.", True)
    for ticker, metadata in assets.items():
        if any(metadata["asset_class"] in CLASS_PREFERENCES[code] for code in excluded_classes):
            excluded_tickers.add(ticker)
    effective["assets"] = sorted(requested | preferences["assets"])
    effective["sectors"] = sorted(set(answers.get("sectors", [])) | preferences["sectors"])
    effective["_preferences"] = {key: sorted(value) for key, value in preferences.items()}
    effective["_preferences"]["excluded_classes"] = sorted(excluded_classes)
    context = answers.get("financial_context", {})
    if context.get("fonds_urgence") == 0:
        finding("NO_EMERGENCY_RESERVE", "financial_context.fonds_urgence", "Aucun fonds d'urgence déclaré : précisez comment financer un imprévu sans vendre les placements.")
    if context.get("besoin_imprevu") in {"besoin_imprevu_3", "besoin_imprevu_4"}:
        finding("LIQUIDITY_REVIEW", "financial_context.besoin_imprevu", "Le besoin de retrait anticipé doit être examiné ; aucun montant à investir n'est déduit du questionnaire.")
    if context.get("dettes") == "dettes_1" and (context.get("dette_hypothecaire") or 0) > 0:
        finding("CONTRADICTORY_DEBT", "financial_context.dette_hypothecaire", "Vous indiquez aucune dette mais un prêt hypothécaire positif. Corrigez ces réponses.", True)
    ceiling = {"dettes_2": 25000, "dettes_3": 100000}.get(context.get("dettes"))
    if ceiling and (context.get("dette_hypothecaire") or 0) >= ceiling:
        finding("CONTRADICTORY_DEBT", "financial_context.dette_hypothecaire", "La part hypothécaire dépasse le total des dettes indiqué. Confirmez la tranche ou le montant.", True)
    if context.get("dettes") not in {None, "dettes_1"}:
        finding("DEBT_CONTEXT", "financial_context.dettes", "Les dettes déclarées sont examinées comme contexte ; leurs taux et mensualités manquent pour calculer une capacité d'investissement.")
    if context.get("objectif_investissement") == "objectif_investissement_2":
        finding("PROJECT_CONTEXT", "financial_context.objectif_investissement", "L'objectif de projet est rapproché de l'horizon déclaré ; aucun montant cible ni rendement nécessaire n'est supposé.")
    if context.get("personnes_a_charge") not in {None, "personnes_a_charge_1"}:
        finding("DEPENDENTS_CONTEXT", "financial_context.personnes_a_charge", "Les personnes à charge et le partage des dépenses sont conservés pour examiner les besoins de réserve ; ils ne constituent pas un score de risque.")
    for code in requested | preferences["assets"]:
        if code in {"cash", "commodity_futures", "fx"}:
            finding("UNSUPPORTED_ASSET_PREFERENCE", "assets", f"La préférence {code} est comprise, mais aucun placement correspondant ne peut être proposé dans le moteur actuel.")
    return {"method": METHOD, "input_hash": signature(original), "original_answers": original,
            "answers": effective, "fields": fields, "signals": signals, "findings": findings,
            "preferences": {key: sorted(value) for key, value in preferences.items()},
            "requirements": {"excluded_tickers": sorted(excluded_tickers)},
            "coverage": {"received_fields": len(fields), "examined_fields": len(fields),
                         "text_fields": len(texts)},
            "limitations": ["Les informations financières sans règle approuvée sont examinées comme contexte, sans score de capacité inventé.",
                            "La correspondance compare les profils de référence disponibles ; elle ne garantit pas un portefeuille optimal ni une adéquation financière complète."]}
