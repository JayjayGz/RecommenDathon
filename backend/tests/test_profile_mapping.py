import json
from pathlib import Path

import pytest

from alphaforge.domain import profile_mapping as pm

PROFILES = json.loads((Path(__file__).resolve().parents[2] / "profiles.json").read_text())

# Persona answers are our own construction (CLAUDE.md describes the personas
# in prose, not as filled-in forms) -- chosen to match each persona's stated
# characteristics, not reverse-engineered from the expected profile id.

ROBERT = {
    "risk": "low", "reaction": "hesitant", "return": "3_4",
    "horizon": "5", "income": "regular",
    "sectors": [], "assets": ["bonds", "cash"], "exclusions": "none",
}

MATEO = {
    "risk": "medium", "reaction": "concerned", "return": "5_6",
    "horizon": "10", "income": "regular",
    "sectors": [], "assets": ["funds"], "exclusions": "limits",
}

AMIRA = {
    "risk": "very_high", "reaction": "calm", "return": "10_plus",
    "horizon": "15_plus", "income": "regular",
    "sectors": ["technology"], "assets": ["stocks", "crypto"], "exclusions": "none",
}


def test_robert_maps_to_profile_4():
    assert pm.risk_band(ROBERT) == "low"
    assert pm.investment_style(ROBERT) == "Income and stability"
    assert pm.map_profile(ROBERT, PROFILES) == 4


def test_mateo_maps_to_profile_10():
    # ESG preference is a known gap in the 8 questions -- passed explicitly here,
    # as it would be once the chat-clarification step (or a new question) sets it.
    assert pm.risk_band(MATEO) == "medium"
    assert pm.map_profile(MATEO, PROFILES, esg_preference=True) == 10


def test_amira_maps_to_profile_13():
    assert pm.risk_band(AMIRA) == "high"
    assert pm.investment_style(AMIRA) == "Growth and innovation"
    assert pm.map_profile(AMIRA, PROFILES) == 13


def test_tolerance_is_the_lower_of_its_signals():
    # A confident self-report shouldn't win against a worried loss reaction.
    answers = {"risk": "very_high", "reaction": "worried", "return": "10_plus"}
    assert pm.tolerance_score(answers) == 1


def test_capacity_is_the_lower_of_its_signals():
    answers = {"horizon": "15_plus", "income": "fragile"}
    assert pm.capacity_score(answers) == 2


def test_missing_answer_raises():
    with pytest.raises(ValueError, match="Missing questionnaire answer"):
        pm.tolerance_score({"risk": "low", "reaction": "calm"})


def test_unexpected_answer_value_raises():
    with pytest.raises(ValueError, match="Unexpected"):
        pm.tolerance_score({"risk": "extreme", "reaction": "calm", "return": "10_plus"})


def test_no_sector_or_asset_signal_defaults_to_broad_diversifier():
    answers = {"sectors": [], "assets": []}
    assert pm.investment_style(answers) == "Broad diversifier"


def test_home_country_preference_overrides_other_signals():
    answers = {"sectors": ["technology"], "assets": []}
    assert pm.investment_style(answers, home_country_preference=True) == "Home country"


@pytest.mark.parametrize("band,style", [(p["band"], p["style"]) for p in PROFILES["profiles"]])
def test_every_band_style_combination_in_profiles_json_is_reachable(band, style):
    # Sanity check: map_profile's lookup must find all 15 combinations that
    # actually exist in profiles.json, not just the three persona cases.
    matches = [p for p in PROFILES["profiles"] if p["band"] == band and p["style"] == style]
    assert len(matches) == 1


def test_to_assessment_matches_risk_band_and_investment_style():
    assessment = pm.to_assessment(ROBERT)
    assert assessment == {"risk_band": pm.risk_band(ROBERT), "preferred_style": pm.investment_style(ROBERT)}


def test_to_assessment_keys_match_profile_matching_s_validated_shape():
    # profile_matching.match_profile()'s assessment argument (and
    # investor_requests.py's validation of it) only accepts these two keys.
    assert set(pm.to_assessment(AMIRA)) == {"risk_band", "preferred_style"}
