"""Regressions for defects reproduced through the connected HTTP pipeline."""
from copy import deepcopy
import json
import subprocess

import pytest

from alphaforge.application.contracts import RequestError
from alphaforge.application.evidence import canonical, release_errors
from alphaforge.application.investor_requests import InvestorRequest
from alphaforge.domain.profile_matching import InvestorInputError, resolve_message
from alphaforge.domain.proposals import ProposalError, apply_proposal
from test_investor_workflow import investor_source, source, investor_request, run, ROOT


@pytest.fixture(scope="module")
def browser_contracts():
    # Generate contracts with the actual frontend, including every source option.
    script = """import {QUESTIONS,fieldVisible,validateAnswers,makeQuestionnairePayload} from './plateforme/src/data.js';
function base(){const a={};for(const q of QUESTIONS){if(q.optional)continue;a[q.id]=q.type==='number'?0:q.type==='multi'?[q.options[0][0]]:q.options[0][0];for(const d of q.details){if(d.required&&fieldVisible(d,a))a[d.key]=d.options[0][0];}}return a;}
const cases=[];for(const q of QUESTIONS){for(const [v] of q.options){const a=base();a[q.id]=q.type==='multi'?[v]:v;cases.push({id:q.id,value:v,valid:validateAnswers(a),payload:makeQuestionnairePayload(a)});}}
console.log(JSON.stringify({base:makeQuestionnairePayload(base()),cases}));"""
    return json.loads(subprocess.check_output(["node", "--input-type=module", "-e", script], cwd=ROOT, text=True))


def test_every_browser_choice_is_accepted_without_missing_answers(browser_contracts):
    for case in browser_contracts["cases"]:
        assert case["valid"], case
        request = InvestorRequest.from_dict({"questionnaire": case["payload"], "as_of": "2025-03-01"})
        _, missing = request.normalized_answers()
        assert not missing, (case["id"], case["value"], missing)


def test_word_crosswalk_preserves_details_and_normalizes_interests(browser_contracts):
    form = deepcopy(browser_contracts["base"])
    # Le montant visé appartient au contrat historique, et non au formulaire v4.
    form["version"] = "questionnaire-word-16-v2"
    form["answers"].update(marital="other", maritalOther="Fictional context", dependents="other",
        dependentsOther="Fictional dependant", supportMode="shared", annualIncome="other", incomeOther="Fictional income",
        debt="other", debtOther="Fictional debt", mortgageAmount=0, goal="project", goalDetails="Fictional goal",
        targetAmount=10000, withdrawalTiming="7_plus", sectors=["industry"], assets=["all"],
        cryptoDetails="Fictional crypto context", exclusions="limits", exclusionDetails="SPY", notes="Fictional notes")
    answers, missing = InvestorRequest.from_dict({"questionnaire": form}).normalized_answers()
    assert not missing
    assert answers["sectors"] == ["industrials"]
    assert {"commodity_funds", "commodity_futures", "crypto", "bonds"} <= set(answers["assets"])
    context = answers["financial_context"]
    assert context["partage_charges"] == "partagees"
    assert context["delai_retrait"] == "7_ans_plus"
    assert context["dette_hypothecaire"] == 0
    assert context["objectif_montant"] == 10000
    assert context["precisions_finales"] == "Fictional notes"


@pytest.mark.parametrize("update", [
    {"unknown": "value"}, {"emergencyFund": True}, {"emergencyFund": -1}, {"emergencyFund": float("nan")},
    {"assets": ["all", "bonds"]}, {"sectors": ["technology", "technology"]},
    {"maritalOther": "Hidden while single"}, {"cryptoDetails": "Hidden while stocks"},
    {"mortgageAmount": -1}, {"withdrawalTiming": "invalid"}, {"notes": "text", "noNotes": True},
    {"noNotes": "true"}, {"notes": " "}, {"risk": "invented"},
])
def test_native_backend_rejects_invalid_hidden_or_conflicting_fields(browser_contracts, update):
    form = deepcopy(browser_contracts["base"])
    form["answers"].update(update)
    with pytest.raises(RequestError):
        InvestorRequest.from_dict({"questionnaire": form})


def test_native_questionnaire_releases_and_incomplete_form_stops_before_loading(investor_source, browser_contracts, monkeypatch):
    form = browser_contracts["base"]
    outcome, _ = run(investor_source, investor_request(questionnaire=form))
    assert outcome.status == "PASS" and outcome.payload["recommendation"]["compliance"]["passed"]
    incomplete = deepcopy(form)
    del incomplete["answers"]["withdrawalTiming"]
    def unexpected(*args, **kwargs):
        pytest.fail("Incomplete form reached snapshot loading")
    monkeypatch.setattr(investor_source, "load", unexpected)
    outcome, _ = run(investor_source, investor_request(questionnaire=incomplete))
    assert outcome.payload["error"]["code"] == "QUESTIONNAIRE_INCOMPLETE"
    assert outcome.payload["error"]["missing_answers"] == ["delai_retrait"]


@pytest.mark.parametrize("ticker", ["XEF.TO", "XBB.TO", "XIU.TO"])
def test_canadian_tickers_are_not_confused_with_target_weight_instructions(investor_source, ticker):
    snapshot = investor_source.load(investor_request().as_of, include_universe=True)
    assert resolve_message(f"Add {ticker} 1%", snapshot.assets) == {"ticker": ticker, "add_pct": 1}
    assert resolve_message(f"Add {ticker.lower()} 1%.", snapshot.assets) == {"ticker": ticker, "add_pct": 1}
    with pytest.raises(InvestorInputError, match="Précisez une seule modification"):
        resolve_message(f"Set {ticker} to 10%", snapshot.assets)


def test_unknown_dotted_symbol_is_not_resolved_to_known_asset(investor_source):
    snapshot = investor_source.load(investor_request().as_of, include_universe=True)
    with pytest.raises(InvestorInputError) as error:
        resolve_message("Add XIU.TO.OTHER 1%", snapshot.assets)
    assert error.value.code == "ASSET_NOT_IN_UNIVERSE"


def test_conflict_evidence_survives_canonical_disk_round_trip(investor_source, tmp_path):
    outcome, records = run(investor_source, investor_request(message="Add BTC-USD 1%"))
    assert outcome.status == "CONFLICT" and outcome.payload["compliance"]["passed"]
    path = tmp_path / "audit.json"
    path.write_text(canonical(records))
    loaded = json.loads(path.read_text())
    selected = loaded["result"]["assessment"]["selected_branch"]
    assert not release_errors(loaded["evidence"], loaded["data_manifest"], loaded["decisions"], selected)


@pytest.mark.parametrize("ticker", ["XBB.TO", "BND", "AGG", "ZST.TO"])
def test_bond_addition_and_reduction_use_metadata_and_preserve_other_bonds(ticker):
    config = json.loads((ROOT / "profiles.json").read_text())
    bonds = {"XBB.TO", "BND", "AGG", "ZST.TO"}
    other = "BND" if ticker != "BND" else "XBB.TO"
    profile = {"band": "low", "crypto_allowed": False, "weights": {ticker: .1, other: .6, "SPY": .3}}
    constraints = {"bond_tickers": sorted(bonds), "etf_tickers": sorted(bonds | {"SPY"})}
    for change, expected in [(5, .15), (-5, .05)]:
        weights, _ = apply_proposal(profile, [{"ticker": ticker, "add_pct": change}], True,
                                   config, bonds | {"SPY"}, constraints)
        assert weights[ticker] == expected
        assert weights[other] == .6
        assert sum(weights.values()) == pytest.approx(1.)
    with pytest.raises(ProposalError, match="Cannot fund"):
        apply_proposal(profile, [{"ticker": ticker, "add_pct": 31}], True, config, bonds | {"SPY"}, constraints)


def test_rounding_reserve_can_be_any_dataset_bond_and_is_order_independent():
    config = json.loads((ROOT / "profiles.json").read_text())
    constraints = {"bond_tickers": ["BND", "XBB.TO"], "etf_tickers": ["BND", "XBB.TO", "SPY"]}
    weights = {"BND": .304, "XBB.TO": .304, "SPY": .392}
    results = []
    for ordered in (weights, dict(reversed(list(weights.items())))):
        profile = {"band": "low", "crypto_allowed": False, "weights": ordered}
        results.append(apply_proposal(profile, [], True, config, set(weights), constraints)[0])
    assert results[0] == results[1]
    profile = {"band": "low", "crypto_allowed": False, "weights": {"BND": .7, "SPY": .3}}
    result, _ = apply_proposal(profile, [{"ticker": "BND", "add_pct": 1}], True, config, {"BND", "SPY"}, constraints)
    assert sum(result.values()) == pytest.approx(1.) and result["BND"] > 0
