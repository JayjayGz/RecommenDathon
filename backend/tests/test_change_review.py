"""Vérifier l’avis avant ajout et la séparation entre simulation et confirmation."""
from copy import deepcopy

import pytest

from alphaforge.application.change_review import build_change_review
from alphaforge.application.evidence import release_errors
from test_investor_workflow import investor_source, investor_request, questionnaire, run
from test_orchestrator import source


def test_compatible_addition_is_only_an_unapplied_review(investor_source):
    initial, _ = run(investor_source)
    current = initial.payload["recommendation"]["portfolio"]
    original = deepcopy(current)
    outcome, audit = run(investor_source, investor_request(message="Ajouter NVIDIA 5%", portfolio=current))
    review = outcome.payload["change_review"]
    assert outcome.status == "PASS" and review["verdict"] == "compatible"
    assert review["applied"] is False and review["confirmation_required"] is True
    assert current == original
    assert review == outcome.payload["recommendation"]["changeReview"]
    assert "correspond à vos intérêts" in " ".join(review["strengths"])
    assert "Aucun ajout n’est appliqué automatiquement" in outcome.payload["message"]
    assert "change_review" in {entry["field"] for entry in audit["evidence"]["entries"]}


@pytest.mark.parametrize("key,value,expected", [
    ("assets", ["bonds", "funds"], "catégorie absente"),
    ("sectors", ["health"], "secteurs choisis"),
    ("horizon", "1_2", "retrait prévu est proche"),
])
def test_preferences_and_horizon_change_the_advice_without_new_caps(investor_source, key, value, expected):
    form = questionnaire()
    form["answers"][key] = value
    outcome, _ = run(investor_source, investor_request(questionnaire=form, message="Ajouter NVDA 5%"))
    assert outcome.status == "PASS"
    review = outcome.payload["change_review"]
    assert review["verdict"] == "clarification_required"
    assert expected in " ".join(review["cautions"])
    assert all(c["passes"] for c in outcome.payload["portfolio"]["validation"]["checks"].values())


def test_rejected_request_never_receives_an_approval(investor_source):
    outcome, _ = run(investor_source, investor_request(message="Ajouter NVDA 5%", requirements={"excluded_tickers": ["NVDA"]}))
    assert outcome.status == "CONFLICT"
    assert outcome.payload["change_review"]["verdict"] == "not_retained"
    assert "recommendation" not in outcome.payload


def test_adjusted_request_and_worsening_risk_require_clarification(investor_source):
    outcome, _ = run(investor_source, investor_request(message="Ajouter NVDA 20%"))
    assert outcome.payload["change_review"]["verdict"] == "clarification_required"
    assert "alternative simulée" in " ".join(outcome.payload["change_review"]["cautions"])
    _, audit = run(investor_source, investor_request(message="Ajouter NVDA 5%"))
    evaluation = deepcopy(audit["decisions"])
    evaluation["as_requested"]["validation"].update(volatility_pct=1, max_drawdown_pct=-1)
    review = build_change_review(evaluation, "as_requested")
    assert review["verdict"] == "clarification_required"
    assert "fluctuations historiques augmentent" in " ".join(review["cautions"])
    assert "baisse historique devient plus profonde" in " ".join(review["cautions"])


def test_unweighted_interest_receives_qualitative_advice_and_no_invented_weight(investor_source):
    outcome, audit = run(investor_source, investor_request(message="Je souhaite investir dans NVIDIA aussi."))
    assert outcome.status == "MISSING_INFO"
    assert outcome.payload["error"]["code"] == "ALLOCATION_AMOUNT_REQUIRED"
    text = outcome.payload["message"]
    assert "Analyse préalable de NVIDIA" in text
    assert "correspond à vos intérêts" in text and "Sans montant" in text
    assert "automatiquement" in text and "5%" not in text
    assert "recommendation" not in outcome.payload and audit["llm_calls"] == []
    assert "EVALUATE_PORTFOLIO" not in audit["result"]["states"]


def test_forged_advice_fails_the_release_gate(investor_source):
    _, audit = run(investor_source, investor_request(message="Ajouter NVDA 5%"))
    evaluation = deepcopy(audit["decisions"])
    evaluation["change_review"]["applied"] = True
    assert "INVALID_CHANGE_REVIEW" in release_errors(audit["evidence"], audit["data_manifest"], evaluation, "as_requested")


def test_unweighted_interest_retains_explicit_exclusion(investor_source):
    outcome, _ = run(investor_source, investor_request(message="Ajouter NVDA", requirements={"excluded_tickers": ["NVDA"]}))
    assert outcome.status == "MISSING_INFO" and "recommendation" not in outcome.payload
    assert "explicitement exclu NVDA" in outcome.payload["message"]


def test_a_numerically_passing_addition_can_still_increase_concentration(investor_source):
    outcome, _ = run(investor_source, investor_request(message="Ajouter XBB.TO 1%"))
    assert outcome.status == "PASS"
    review = outcome.payload["change_review"]
    assert review["verdict"] == "clarification_required"
    assert "concentration entre les positions augmente" in " ".join(review["cautions"])


def test_initial_questionnaire_does_not_require_change_confirmation(investor_source):
    outcome, _ = run(investor_source)
    assert outcome.status == "PASS"
    assert "change_review" not in outcome.payload and "changeReview" not in outcome.payload["recommendation"]
