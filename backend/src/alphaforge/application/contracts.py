"""Validated request and transport-independent workflow outcome."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
import re


class RequestError(ValueError):
    pass


@dataclass(frozen=True)
class Change:
    ticker: str
    add_pct: int | None = None

    def to_dict(self):
        return ({"exclude": self.ticker} if self.add_pct is None else
                {"ticker": self.ticker, "add_pct": self.add_pct})


@dataclass(frozen=True)
class RecommendationRequest:
    profile_id: int
    changes: tuple[Change, ...]
    as_of: date

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) - {"profile_id", "changes", "as_of"}:
            raise RequestError("Expected profile_id, changes and optional as_of")
        if type(value.get("profile_id")) is not int or value["profile_id"] <= 0:
            raise RequestError("profile_id must be a positive integer")
        changes = value.get("changes")
        if not isinstance(changes, list) or len(changes) > 40:
            raise RequestError("changes must be a list of at most 40 edits")
        parsed = []
        for change in changes:
            if not isinstance(change, dict):
                raise RequestError("Each change must be an object")
            keys = set(change)
            if keys == {"exclude"}:
                ticker, points = change["exclude"], None
            elif keys == {"ticker", "add_pct"}:
                ticker, points = change["ticker"], change["add_pct"]
                if type(points) is not int or not -100 <= points <= 100:
                    raise RequestError("add_pct must be whole percentage points between -100 and 100")
            else:
                raise RequestError("Use exclude, or ticker and add_pct")
            if not isinstance(ticker, str) or not re.fullmatch(r"[A-Z0-9.^=-]{1,24}", ticker):
                raise RequestError("Invalid ticker")
            parsed.append(Change(ticker, points))
        today = datetime.now(timezone.utc).date()
        try:
            raw_date = value.get("as_of", today.isoformat())
            if not isinstance(raw_date, str):
                raise ValueError()
            as_of = date.fromisoformat(raw_date)
            if raw_date != as_of.isoformat() or as_of > today:
                raise ValueError()
        except ValueError as error:
            raise RequestError("as_of must be YYYY-MM-DD and cannot be in the future (UTC)") from error
        return cls(value["profile_id"], tuple(parsed), as_of)

    def to_dict(self):
        return {"profile_id": self.profile_id, "changes": [c.to_dict() for c in self.changes],
                "as_of": self.as_of.isoformat()}


@dataclass(frozen=True)
class WorkflowOutcome:
    status: str
    payload: dict
