"""Lambda entry point. Health checks are available before pipeline wiring.

No AWS clients or calculations run at import time. This bootstrap deliberately
does not release portfolio results without evidence, compliance and auditing.
"""

import json


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(payload, allow_nan=False),
        "isBase64Encoded": False,
    }


def handler(event, context):
    """Accept a direct invocation or an HTTP API v2 / Function URL event.

    HTTP event support is a transport contract, not a provisioned public URL.
    Health means the handler runs; it does not test data, Bedrock or S3 access.
    """
    if not isinstance(event, dict):
        return _response(400, {"error": {"code": "INVALID_EVENT"}})

    request_context = event.get("requestContext")
    http = request_context.get("http") if isinstance(request_context, dict) else None
    if isinstance(http, dict):
        method, path = http.get("method"), event.get("rawPath")
        if method == "GET" and path == "/health":
            action = "health"
        elif method == "POST" and path in {"/portfolio", "/chat"}:
            action = "recommend"
        else:
            return _response(404, {"error": {"code": "ROUTE_NOT_FOUND"}})
    else:
        action = event.get("action")

    if action == "health":
        return _response(200, {
            "ok": True,
            "service": "alphaforge-backend",
            "pipelineReady": False,
        })
    if action == "recommend":
        return _response(503, {"error": {
            "code": "PIPELINE_NOT_READY",
            "message": "Orchestration, evidence, compliance and audit wiring are not implemented.",
        }})
    return _response(400, {"error": {"code": "UNKNOWN_ACTION"}})
