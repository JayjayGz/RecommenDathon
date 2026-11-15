"""Investor-facing language and questionnaire tensions, independent of model order."""
from copy import deepcopy

import pytest

from alphaforge.application.investor_summary import questionnaire_observations, change_analysis
from test_investor_workflow import investor_source, investor_request, french_form, run
from test_orchestrator import source


@pytest.mark.parametrize("answers,expected", [
    ({"risk": "high", "reaction": "worried"}, "contraste"),
    ({"risk": "high", "horizon": "1_2"}, "retrait proche"),
    ({"risk": "low", "assets": ["crypto"]}, "cryptomonnaies"),
    ({"income": "fragile", "financial_context": {"fonds_urgence": 0}}, "réserve"),
    ({"horizon": "10", "financial_context": {"delai_retrait": "moins_1_an"}}, "horizon long"),
])
def test_neutral_tensions_are_grounded_in_answer_combinations(answers, expected):
    original = deepcopy(answers)
    assert expected in " ".join(questionnaire_observations(answers))
    assert answers == original


def test_consistent_and_unknown_answers_do_not_invent_contradictions():
    assert questionnaire_observations({"risk": "high", "reaction": "calm", "horizon": "15_plus"}) == []
    assert questionnaire_observations({}) == []
    assert questionnaire_observations({"income": "fragile"}) == []  # missing reserve is not zero


def test_french_summary_flags_tensions_and_uses_the_new_questionnaire_mapping(investor_source):
    form = french_form()
    questions = {q["id"]: q for q in form["questions"]}
    questions["tolerance_risque"]["reponse"] = "tolerance_risque_5"
    outcome, records = run(investor_source, investor_request(questionnaire=form))
    text = outcome.payload["explanation"]
    assert outcome.status == "PASS"
    assert outcome.payload["profile_match"]["risk_band"] == "low"
    assert outcome.payload["profile_match"]["risk_mapping_source"] == "capacity_tolerance_style_v1"
    assert outcome.payload["profile_match"]["questionnaire_mapping"]["tolerance_score"] == 1
    assert "contraste" in text and "retrait proche" in text
    assert "Simulation éducative" in text
    assert len(text.split()) < 350
    assert outcome.payload["message"] == outcome.payload["recommendation"]["explanation"] == text
    assert not any(term in text for term in ["[", "E1", "PASS", "HHI", "profiles.json", "snapshot", "funding"])
    assert "annualisée" in text and "plus forte baisse" in text
    assert records["evidence"]["entries"]  # traceability is retained privately
    assert len(outcome.payload["limitations"]) == 4
    assert all("pipeline" not in limit and "CSV" not in limit for limit in outcome.payload["limitations"])


def test_followup_explains_actual_changes_and_retains_baseline_evidence(investor_source):
    initial, _ = run(investor_source)
    outcome, records = run(investor_source, investor_request(message="Ajouter NVIDIA 5%"))
    text = outcome.payload["explanation"]
    assert outcome.status == "PASS"
    assert text != initial.payload["explanation"]
    assert "augmenter NVDA de 5 points" in text
    assert "NVDA passe de 0 % à 5 %" in text
    assert "en contrepartie" in text
    assert "fluctuations annualisées" in text
    assert "risque historique restent inchangés" in text  # prix fictifs constants
    assert "base.volatility_pct" in {e["field"] for e in records["evidence"]["entries"]}
    assert text == outcome.payload["recommendation"]["explanation"]


def exemple_comparaison():
    mesures = {"status": "PASS", "period": {"first_date": "2024-01-01", "last_date": "2025-01-01", "observations": 52},
               "currency": "CAD", "method": "mensuel", "rebalance": "monthly",
               "annual_growth_pct": 5, "volatility_pct": 10, "max_drawdown_pct": -8}
    return {"requested_changes": [{"exclude": "AAA"}],
            "base": {"weights": {"AAA": .2, "BBB": .8}, "validation": mesures},
            "adjusted": {"weights": {"BBB": 1}, "validation": {**mesures, "volatility_pct": 12, "max_drawdown_pct": -6}}}


def test_alternative_explains_removed_position_and_mixed_risk():
    evaluation = exemple_comparaison()
    original = deepcopy(evaluation)
    text = " ".join(change_analysis(evaluation, "adjusted"))
    assert "exclure AAA" in text and "alternative simulée" in text
    assert "AAA passe de 20 % à 0 %" in text
    assert "BBB passe de 80 % à 100 %" in text
    assert "fluctuations historiques augmentent" in text and "baisse est moins profonde" in text
    assert evaluation == original


def test_different_windows_do_not_claim_effect_of_change():
    evaluation = exemple_comparaison()
    evaluation["adjusted"]["validation"]["period"] = {"first_date": "2024-06-01"}
    text = " ".join(change_analysis(evaluation, "adjusted"))
    assert "périodes ou les méthodes" in text
    assert "fluctuations annualisées" not in text


def test_unchanged_and_rejected_proposals_are_explicit():
    evaluation = exemple_comparaison()
    evaluation["adjusted"] = deepcopy(evaluation["base"])
    assert "aucun changement effectif" in " ".join(change_analysis(evaluation, "adjusted"))
    assert "Aucun changement n’est appliqué" in " ".join(change_analysis(evaluation, None))
    assert change_analysis({"requested_changes": []}, None) == []
