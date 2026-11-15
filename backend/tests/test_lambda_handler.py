"""Transport/bootstrap checks. No credentials, network or model calls."""

import json

import pytest

from alphaforge.presentation.lambda_handler import handler


def test_health_distinguishes_liveness_from_pipeline_readiness(monkeypatch):
    monkeypatch.delenv("ALPHAFORGE_MODE", raising=False)
    result = handler({"action": "health"}, None)
    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {
        "ok": True, "service": "alphaforge-backend", "workflowConfigured": False,
    }


def test_unconfigured_workflow_never_returns_a_recommendation(monkeypatch):
    from alphaforge.presentation.lambda_handler import get_orchestrator
    get_orchestrator.cache_clear()
    monkeypatch.delenv("ALPHAFORGE_MODE", raising=False)
    result = handler({"action": "recommend", "request": {"profile_id": 4, "changes": []}}, None)
    assert result["statusCode"] == 503
    assert json.loads(result["body"])["error"]["code"] == "WORKFLOW_CONFIGURATION_UNAVAILABLE"
    assert "portfolio" not in json.loads(result["body"])


@pytest.mark.parametrize("event", [None, [], "health", 1])
def test_nonobject_events_are_rejected(event):
    assert handler(event, None)["statusCode"] == 400


@pytest.mark.parametrize("context", [None, [], "malformed", {"http": None}])
def test_malformed_http_context_does_not_crash(context):
    assert handler({"requestContext": context}, None)["statusCode"] == 400


@pytest.mark.parametrize("method,path,status", [
    ("GET", "/health", 200),
    ("POST", "/portfolio", 400),
    ("POST", "/chat", 400),
    ("GET", "/portfolio", 404),
    ("POST", "/health", 404),
    ("GET", "/unknown", 404),
])
def test_http_routes(method, path, status):
    event = {"requestContext": {"http": {"method": method}}, "rawPath": path}
    assert handler(event, None)["statusCode"] == status


def test_unknown_action_does_not_echo_untrusted_input():
    marker = "private-request-content"
    result = handler({"action": marker}, None)
    assert result["statusCode"] == 400
    assert marker not in result["body"]


@pytest.mark.parametrize("action", [[], {}, True])
def test_nonstring_actions_fail_without_a_transport_exception(action):
    assert handler({"action": action}, None)["statusCode"] == 400
