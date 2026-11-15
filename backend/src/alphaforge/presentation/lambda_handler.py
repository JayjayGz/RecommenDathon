"""Transport validation and workflow dispatch. No AWS calls on import."""
import base64
import binascii
from functools import lru_cache
import json
import os

from alphaforge.application.contracts import RecommendationRequest, RequestError
from alphaforge.application.investor_requests import InvestorRequest

HTTP_STATUS = {"PASS": 200, "CONFLICT": 200, "INVALID_REQUEST": 400, "MISSING_INFO": 422,
               "FAILED": 500, "AUDIT_FAILED": 503, "TIMEOUT": 504}


@lru_cache(maxsize=1)
def get_orchestrator():
    from alphaforge.bootstrap import create_orchestrator
    return create_orchestrator()


def _configured():
    mode = os.environ.get("ALPHAFORGE_MODE")
    return mode == "local" or (mode == "s3" and bool(os.environ.get("DATA_BUCKET"))
                               and bool(os.environ.get("AUDIT_BUCKET")))


def _decode_request(event, is_http):
    if not is_http:
        payload = event.get("request")
    else:
        headers = event.get("headers") or {}
        if not isinstance(headers, dict):
            raise RequestError("Invalid headers")
        content_type = next((v for k, v in headers.items() if k.lower() == "content-type"), "application/json")
        if not isinstance(content_type, str) or content_type.split(";")[0].strip() != "application/json":
            raise RequestError("Expected application/json")
        body = event.get("body")
        if not isinstance(body, str) or len(body.encode()) > 90 * 1024:
            raise RequestError("Invalid request body")
        try:
            raw = base64.b64decode(body, validate=True) if event.get("isBase64Encoded") is True else body.encode()
            if len(raw) > 64 * 1024:
                raise RequestError("Request too large")
            payload = json.loads(raw)
        except (ValueError, UnicodeError, binascii.Error) as error:
            raise RequestError("Invalid JSON body") from error
    try:
        if len(json.dumps(payload, allow_nan=False).encode()) > 64 * 1024:
            raise RequestError("Request too large")
    except (ValueError, TypeError) as error:
        raise RequestError("Invalid request JSON") from error
    if isinstance(payload, dict) and "questions" in payload and "langue" in payload:
        payload = {"questionnaire": payload}
    if isinstance(payload, dict) and "questionnaire" in payload:
        return InvestorRequest.from_dict(payload)
    return RecommendationRequest.from_dict(payload)


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(payload, allow_nan=False),
        "isBase64Encoded": False,
    }


def handler(event, context):
    """Health is liveness/configuration only, never a data/model access probe."""
    if not isinstance(event, dict):
        return _response(400, {"error": {"code": "INVALID_EVENT"}})

    request_context = event.get("requestContext")
    http = request_context.get("http") if isinstance(request_context, dict) else None
    if isinstance(http, dict):
        method, path = http.get("method"), event.get("rawPath")
        if method == "GET" and path == "/health":
            action = "health"
        elif method == "POST" and path == "/portfolio":
            action = "recommend"
        elif method == "POST" and path == "/chat":
            action = "personalize"
        else:
            return _response(404, {"error": {"code": "ROUTE_NOT_FOUND"}})
    else:
        action = event.get("action")

    if action == "health":
        return _response(200, {
            "ok": True,
            "service": "alphaforge-backend",
            "workflowConfigured": bool(_configured()),
        })
    if isinstance(action, str) and action in {"recommend", "personalize"}:
        try:
            request = _decode_request(event, isinstance(http, dict))
            if action == "personalize" and not isinstance(request, InvestorRequest):
                raise RequestError("Personalization requires questionnaire context")
            if action == "personalize" and request.message is None and not request.changes:
                raise RequestError("A personalization instruction is required")
        except RequestError:
            return _response(400, {"error": {"code": "INVALID_REQUEST"}})
        try:
            workflow = get_orchestrator()
        except Exception:
            return _response(503, {"error": {"code": "WORKFLOW_CONFIGURATION_UNAVAILABLE"}})
        remaining = getattr(context, "get_remaining_time_in_millis", None)
        outcome = workflow.run(request, remaining_ms=remaining)
        if isinstance(http, dict) and isinstance(request, InvestorRequest):
            payload = outcome.payload
            if action == "personalize" and outcome.status in {"PASS", "CONFLICT", "MISSING_INFO", "INVALID_REQUEST"}:
                code = payload.get("error", {}).get("code", outcome.status)
                response = {"message": payload.get("message", f"Aucun portefeuille validé n’a été proposé. État de l’analyse : {code}."),
                            "runId": payload.get("run_id"), "status": outcome.status,
                            "audit_saved": payload.get("audit_saved", False)}
                if "recommendation" in payload:
                    response["proposal"] = payload["recommendation"]
                if "error" in payload:
                    response["error"] = payload["error"]
                return _response(200, response)
            if "recommendation" in payload:
                return _response(200, payload["recommendation"])
        return _response(HTTP_STATUS.get(outcome.status, 500), outcome.payload)
    return _response(400, {"error": {"code": "UNKNOWN_ACTION"}})
