"""Questionnaire answers -> one of the 15 base profiles. Plain function, not an agent.

Scoring follows CLAUDE.md: capacity (ability to take risk) and tolerance
(willingness to take risk) are each scored 1-6, and the risk level is the
lower of the two -- so one optimistic answer can never outweigh a cautious
one. Band = low (1-2) / medium (3-4) / high (5-6).

Answers use the real questionnaire's field names and values
(frontend/src/data.js): risk, reaction, return, horizon, income, sectors,
assets, exclusions.

Known gap: the questionnaire has no question about home-country preference
or ESG/responsible investing, so "Home country" and "Responsible (ESG)"
cannot be derived from the 8 answers alone. esg_preference and
home_country_preference are explicit overrides for when that signal comes
from elsewhere (e.g. the "I'm not sure" chat clarification agent reading the
exclusions free text) -- not inferred here.
"""

# Tolerance signals (willingness), each scored 1-6.
RISK_SCORE = {"very_low": 1, "low": 2, "medium": 4, "high": 5, "very_high": 6}
REACTION_SCORE = {"worried": 1, "hesitant": 2, "concerned": 4, "calm": 6}
RETURN_SCORE = {"3_4": 1, "5_6": 3, "7_9": 5, "10_plus": 6}

# Capacity signals (ability), each scored 1-6.
HORIZON_SCORE = {"1_2": 1, "5": 3, "10": 5, "15_plus": 6}
INCOME_SCORE = {"unknown": 2, "fragile": 2, "variable": 4, "regular": 6}

STYLES = ("Broad diversifier", "Home country", "Growth and innovation",
          "Income and stability", "Responsible (ESG)")


def _lookup(table, answers, key):
    if key not in answers:
        raise ValueError(f"Missing questionnaire answer: {key!r}")
    value = answers[key]
    if value not in table:
        raise ValueError(f"Unexpected {key!r} answer: {value!r}")
    return table[value]


def tolerance_score(answers):
    """1-6: willingness to take risk, the lower of self-report, loss reaction and desired return."""
    return min(_lookup(RISK_SCORE, answers, "risk"),
               _lookup(REACTION_SCORE, answers, "reaction"),
               _lookup(RETURN_SCORE, answers, "return"))


def capacity_score(answers):
    """1-6: ability to take risk regardless of feelings, the lower of horizon and income stability."""
    return min(_lookup(HORIZON_SCORE, answers, "horizon"),
               _lookup(INCOME_SCORE, answers, "income"))


def risk_level(answers):
    """1-6 overall risk level: the lower of capacity and tolerance."""
    return min(capacity_score(answers), tolerance_score(answers))


def risk_band(answers):
    """low (1-2) / medium (3-4) / high (5-6)."""
    level = risk_level(answers)
    if level <= 2:
        return "low"
    if level <= 4:
        return "medium"
    return "high"


def investment_style(answers, esg_preference=False, home_country_preference=False):
    """One of the 5 styles. See module docstring for the ESG/home-country gap."""
    if esg_preference:
        return "Responsible (ESG)"
    if home_country_preference:
        return "Home country"
    sectors = set(answers.get("sectors", []))
    assets = set(answers.get("assets", []))
    if "technology" in sectors:
        return "Growth and innovation"
    if assets & {"bonds", "cash"} and not assets & {"stocks", "crypto"}:
        return "Income and stability"
    return "Broad diversifier"


def map_profile(answers, profiles_config, esg_preference=False, home_country_preference=False):
    """Returns the matching profile_id (1-15) from profiles_config['profiles']."""
    band = risk_band(answers)
    style = investment_style(answers, esg_preference, home_country_preference)
    for profile in profiles_config["profiles"]:
        if profile["band"] == band and profile["style"] == style:
            return profile["id"]
    raise ValueError(f"No profile for band={band!r} style={style!r}")


def to_assessment(answers, esg_preference=False, home_country_preference=False):
    """{"risk_band", "preferred_style"} -- the shape profile_matching.match_profile()'s
    `assessment` argument accepts (see investor_requests.py's validation of the same
    two keys). Passing this in place of an empty assessment makes match_profile() use
    this module's capacity/tolerance band and explicit style, instead of its own
    single-signal risk_map and automatic asset/sector-overlap scoring.
    """
    return {"risk_band": risk_band(answers),
            "preferred_style": investment_style(answers, esg_preference, home_country_preference)}
