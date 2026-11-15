"""Strict frontend questionnaire and follow-up contracts, without risk inference."""
from dataclasses import dataclass, field
from datetime import date
import math
import re

from .contracts import RecommendationRequest, RequestError
from .questionnaires import normalize_french
from .word_questionnaire import WORD_VERSION, normalize_word

QUESTIONNAIRE_VERSION = "rendements-seuls-v1"
OPTIONS = {
    "risk": {"very_low", "low", "medium", "high", "very_high"},
    "reaction": {"worried", "hesitant", "concerned", "calm"},
    "return": {"3_4", "5_6", "7_9", "10_plus"},
    "horizon": {"1_2", "5", "10", "15_plus"},
    "income": {"regular", "variable", "fragile", "unknown"},
    "sectors": {"technology", "health", "financial_services", "materials", "real_estate", "finance", "consumer", "other"},
    "assets": {"stocks", "bonds", "funds", "cash", "crypto"},
    "exclusions": {"none", "limits", "discussion"},
}
DETAILS = {"otherSector", "cryptoDetails", "exclusionDetails"}
TICKER = re.compile(r"[A-Z0-9.^=-]{1,24}")


def _tickers(values):
    if (not isinstance(values, list) or len(values) > 40
            or any(not isinstance(t, str) or not TICKER.fullmatch(t) for t in values)
            or len(set(values)) != len(values)):
        raise RequestError("Expected unique ticker identifiers")
    return list(values)


@dataclass(frozen=True)
class InvestorRequest:
    questionnaire: dict
    as_of: date
    assessment: dict = field(default_factory=dict)
    requirements: dict = field(default_factory=dict)
    message: str | None = None
    current_weights: dict | None = None
    changes: tuple = ()
    conversation: tuple = ()

    @classmethod
    def from_dict(cls, value):
        allowed = {"questionnaire", "as_of", "assessment", "requirements", "message", "portfolio", "changes", "conversation"}
        if not isinstance(value, dict) or set(value) - allowed:
            raise RequestError("Invalid investor request fields")
        questionnaire = value.get("questionnaire")
        if not isinstance(questionnaire, dict):
            raise RequestError("Expected a questionnaire object")
        french = "questions" in questionnaire
        word = questionnaire.get("version") == WORD_VERSION
        if french:
            normalize_french(questionnaire)
            answers = None
        elif word:
            normalize_word(questionnaire)
            answers = None
        elif set(questionnaire) != {"version", "answers"} or questionnaire["version"] != QUESTIONNAIRE_VERSION:
            raise RequestError("Unsupported questionnaire version")
        else:
            answers = questionnaire["answers"]
        if not (french or word) and (not isinstance(answers, dict) or set(OPTIONS) - set(answers) or set(answers) - (set(OPTIONS) | DETAILS)):
            raise RequestError("Expected all eight questionnaire answers")
        for key, options in ([] if french or word else OPTIONS.items()):
            answer = answers[key]
            if key in {"assets", "sectors"}:
                if (not isinstance(answer, list) or not answer or len(answer) > len(options)
                        or any(not isinstance(v, str) or v not in options for v in answer)
                        or len(set(answer)) != len(answer)):
                    raise RequestError("Invalid questionnaire selections")
            elif not isinstance(answer, str) or answer not in options:
                raise RequestError("Invalid questionnaire answer")
        if not (french or word) and any(not isinstance(answers[k], str) or len(answers[k]) > 1000 for k in DETAILS & set(answers)):
            raise RequestError("Invalid questionnaire details")
        assessment = value.get("assessment", {})
        if (not isinstance(assessment, dict) or set(assessment) - {"risk_band", "preferred_style"}
                or ("risk_band" in assessment and (not isinstance(assessment["risk_band"], str)
                                                  or assessment["risk_band"] not in {"low", "medium", "high"}))
                or ("preferred_style" in assessment and (not isinstance(assessment["preferred_style"], str)
                                                        or len(assessment["preferred_style"]) > 100))):
            raise RequestError("Invalid explicit profile assessment")
        requirements = value.get("requirements", {})
        if not isinstance(requirements, dict) or set(requirements) - {"excluded_tickers", "max_asset_weight_pct", "max_crypto_weight_pct"}:
            raise RequestError("Unsupported structured requirement")
        if "excluded_tickers" in requirements:
            _tickers(requirements["excluded_tickers"])
        for key in {"max_asset_weight_pct", "max_crypto_weight_pct"} & set(requirements):
            limit = requirements[key]
            if type(limit) not in (int, float) or not math.isfinite(limit) or not 0 <= limit <= 100:
                raise RequestError("Invalid weight limit")
        message = value.get("message")
        if message is not None and (not isinstance(message, str) or not message.strip() or len(message) > 5000):
            raise RequestError("Invalid personalization message")
        if message is not None and "changes" in value:
            raise RequestError("Use either a message or structured changes")
        existing = RecommendationRequest.from_dict({"profile_id": 1, "changes": value.get("changes", []),
            **({"as_of": value["as_of"]} if "as_of" in value else {})})
        weights = None
        if "portfolio" in value:
            portfolio = value["portfolio"]
            positions = portfolio.get("positions") if isinstance(portfolio, dict) else None
            if not isinstance(positions, list) or not 1 <= len(positions) <= 40 or portfolio.get("isDemo") is True:
                raise RequestError("A real current portfolio is required")
            weights = {}
            for position in positions:
                if not isinstance(position, dict):
                    raise RequestError("Invalid current holding")
                ticker, weight = position.get("symbol"), position.get("weight")
                if (not isinstance(ticker, str) or not TICKER.fullmatch(ticker) or ticker in weights
                        or type(weight) not in (int, float) or not math.isfinite(weight) or not 0 < weight <= 100):
                    raise RequestError("Invalid current holding")
                weights[ticker] = weight / 100
            if abs(sum(weights.values()) - 1) > 1e-6:
                raise RequestError("Current portfolio weights must total 100 percent")
        conversation = value.get("conversation", [])
        if (not isinstance(conversation, list) or len(conversation) > 100
                or any(not isinstance(m, dict) or set(m) != {"role", "content"}
                       or not isinstance(m["role"], str) or m["role"] not in {"user", "assistant"} or not isinstance(m["content"], str)
                       or len(m["content"]) > 10000 for m in conversation)):
            raise RequestError("Invalid conversation")
        return cls(questionnaire, existing.as_of, assessment, requirements, message, weights,
                   existing.changes, tuple(conversation))

    def to_dict(self):
        # Conversation is interpretation context, not an authority for profile policy.
        return {"questionnaire": self.questionnaire, "assessment": self.assessment,
                "requirements": self.requirements, "as_of": self.as_of.isoformat(),
                "message": self.message, "current_weights": self.current_weights,
                "changes": [c.to_dict() for c in self.changes], "conversation": list(self.conversation)}

    def normalized_answers(self):
        if self.questionnaire.get("version") == WORD_VERSION:
            return normalize_word(self.questionnaire)
        if "questions" in self.questionnaire:
            return normalize_french(self.questionnaire)
        return self.questionnaire["answers"], []
