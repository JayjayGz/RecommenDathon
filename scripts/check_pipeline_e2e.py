"""Exercise the real Node proxy and Lambda handler locally, with real CSVs and disk audits."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import argparse
from datetime import date
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--as-of", default=date.today().isoformat())
parser.add_argument("--output-dir", type=Path)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = args.output_dir.resolve() if args.output_dir else ROOT / ".local-runs/e2e-verification"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "backend/src"))
from alphaforge.application.audit import ARTIFACTS
from alphaforge.application.evidence import fallback_draft, release_errors, validate_draft
from alphaforge.application.investor_requests import InvestorRequest
from alphaforge.presentation.lambda_handler import handler, get_orchestrator

AUDIT = OUTPUT / f"audit-{time.time_ns()}"
os.environ.update(ALPHAFORGE_MODE="local", DATA_DIR=str(ROOT / "dataset"),
                  PROFILES_PATH=str(ROOT / "profiles.json"), AUDIT_DIR=str(AUDIT), BEDROCK_MODEL_ID="")
get_orchestrator.cache_clear()
report = {"scope": "Local HTTP proxy -> real Lambda handler -> real CSV engine -> disk audit; no AWS or LLM calls", "audit_directory": str(AUDIT),
          "as_of": args.as_of, "checks": [], "requests": [], "audits": []}


def check(name, passed, **detail):
    entry = {"name": name, "passed": bool(passed), **detail}
    report["checks"].append(entry)
    print(json.dumps(entry), flush=True)


class Bridge(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
        response = handler({"requestContext": {"http": {"method": "POST"}},
                            "rawPath": self.path, "headers": {"Content-Type": "application/json"},
                            "body": body}, None)
        payload = json.loads(response["body"])
        report["requests"].append({"path": self.path, "http_status": response["statusCode"],
                                   "error": payload.get("error"), "status": payload.get("status"),
                                   "run_id": payload.get("runId", payload.get("run_id"))})
        data = response["body"].encode()
        self.send_response(response["statusCode"])
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def request(base, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(base + path, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=40) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def frontend_valid(value):
    script = "import {validateRecommendation} from './plateforme/src/integration.js';let s='';for await(const c of process.stdin)s+=c;process.exit(validateRecommendation(JSON.parse(s))?0:1);"
    return subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(value),
                          text=True, cwd=ROOT, capture_output=True).returncode == 0


bridge = ThreadingHTTPServer(("127.0.0.1", 0), Bridge)
threading.Thread(target=bridge.serve_forever, daemon=True).start()
with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
base = f"http://127.0.0.1:{port}"
upstream = f"http://127.0.0.1:{bridge.server_port}"
env = {**os.environ, "PORT": str(port), "PORTFOLIO_API_URL": upstream + "/portfolio",
       "AGENT_API_URL": upstream + "/chat", "PORTFOLIO_API_TOKEN": "", "AGENT_API_TOKEN": ""}
original_hash = hashlib.sha256((ROOT / "dataset/prices_weekly.csv").read_bytes()).hexdigest()
log = (OUTPUT / "node.log").open("w", encoding="utf-8")
node = subprocess.Popen(["node", "plateforme/server.mjs"], cwd=ROOT, env=env, stdout=log, stderr=log,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
try:
    for _ in range(100):
        try:
            status, config = request(base, "/api/config")
            break
        except OSError:
            if node.poll() is not None:
                raise RuntimeError("Node proxy failed; inspect node.log")
            time.sleep(.1)
    else:
        raise RuntimeError("Node proxy did not become ready")
    check("Local frontend proxy connects to both handler routes", status == 200 and all(config.values()))

    script = """import {QUESTIONS,fieldVisible,validateAnswers,makeQuestionnairePayload} from './plateforme/src/data.js';
const a={};for(const q of QUESTIONS){if(q.optional)continue;a[q.id]=q.type==='number'?5000:q.type==='multi'?[q.options[0][0]]:q.options[0][0];for(const d of q.details){if(d.required&&fieldVisible(d,a))a[d.key]=d.type==='number'?100:d.type==='single'?d.options[0][0]:'Example';}}
console.log(JSON.stringify({valid:validateAnswers(a),payload:makeQuestionnairePayload(a)}));"""
    native = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", script], cwd=ROOT, text=True))
    assert native["valid"]
    status, response = request(base, "/api/portfolio", {"questionnaire": native["payload"], "as_of": report["as_of"]})
    try:
        InvestorRequest.from_dict({"questionnaire": native["payload"], "as_of": report["as_of"]})
        reason = None
    except ValueError as error:
        reason = str(error)
    check("Browser-native questionnaire reaches recommendation", status == 200 and frontend_valid(response),
          http_status=status, proxy_error=response.get("code"), backend_reason=reason,
          questionnaire_version=native["payload"]["version"])
    if status == 200 and frontend_valid(response):
        native_audit = json.loads((AUDIT / response["runId"] / "decisions.json").read_text())
        check("Le questionnaire du site utilise le nouveau mapping",
              native_audit["profile_match"]["risk_mapping_source"] == "capacity_tolerance_style_v1"
              and native_audit["profile_match"]["questionnaire_mapping"]["risk_level"] == 1)

    event = json.loads((ROOT / "backend/events/questionnaire-fr.json").read_text())
    form = event["request"]["questionnaire"]
    status, initial = request(base, "/api/portfolio", {"questionnaire": form, "as_of": report["as_of"]})
    check("Supported French questionnaire returns a valid recommendation through proxy", status == 200 and frontend_valid(initial), http_status=status)
    (OUTPUT / "initial-response.json").write_text(json.dumps(initial, indent=2), encoding="utf-8")
    if status == 200 and frontend_valid(initial):
        analysis = initial.get("analysis", {})
        exposures = analysis.get("exposures", {})
        check("Les expositions du catalogue et les pistes traversent le proxy",
              exposures.get("method") == "weighted_catalog_exposures_v1"
              and exposures.get("dimensions", {}).get("sectors", {}).get("covered_pct", 0) > 0
              and all(p["applied"] is False and p["status"] == "to_study" for p in exposures.get("potential_assets", [])))
        review = analysis.get("review", {})
        check("Structured review survives frontend proxy", analysis.get("method") == "portfolio_review_v1"
            and review.get("sectors", {}).get("scope") == "direct_stocks_only"
            and review.get("profile_fit", {}).get("status") == "PASS"
            and review.get("selection", {}).get("optimized") is False,
            method=analysis.get("method"), manifest_hash=analysis.get("manifest_hash"))
        suggestions = analysis.get("suggestions", [])
        checked = bool(suggestions)
        for alternative in suggestions:
            comparison, validation = alternative["comparison"], alternative["validation"]
            checked = checked and (alternative["applied"] is False and validation["passes"]
                and all(c["passes"] is True for c in validation["checks"].values())
                and comparison["holding_hhi"]["after"] < comparison["holding_hhi"]["before"]
                and comparison["volatility_pct"]["after"] <= comparison["volatility_pct"]["before"]
                and comparison["max_drawdown_pct"]["after"] >= comparison["max_drawdown_pct"]["before"]
                and validation["period"] == review["risk"]["period"])
        check("Real-data optional alternative improves concentration and preserves risk checks", checked,
              comparisons=[s["comparison"] for s in suggestions],
              evaluated_candidates=analysis.get("search", {}).get("evaluated_candidates"))
        current = initial["portfolio"]
        for name, message in [("Equity addition", "Add NVDA 1%"), ("Additional stock AAPL", "Add AAPL 1%"),
                              ("Equity ETF VTI", "Add VTI 1%"), ("Bond ETF BND", "Add BND 1%"),
                              ("Commodity ETF GLD", "Add GLD 1%"), ("Canadian equity ETF XEF.TO", "Add XEF.TO 1%"),
                              ("Crypto request under low-risk policy", "Add BTC-USD 1%"),
                              ("Unknown asset rejection", "Add NONEXISTENT-XYZ 5%"), ("Canadian bond ETF XBB.TO", "Add XBB.TO 1%")]:
            trace_start = len(report["requests"])
            status, response = request(base, "/api/agent/chat", {"questionnaire": form, "portfolio": current,
                                        "message": message, "conversation": [], "as_of": report["as_of"]})
            trace = report["requests"][trace_start:][-1]
            proposal = response.get("proposal")
            if name in {"Equity addition", "Additional stock AAPL", "Equity ETF VTI", "Bond ETF BND", "Commodity ETF GLD", "Canadian equity ETF XEF.TO", "Canadian bond ETF XBB.TO"}:
                passed = status == 200 and frontend_valid(proposal)
            elif name == "Crypto request under low-risk policy":
                passed = status == 200 and frontend_valid(proposal) and all(p["symbol"] not in {"BTC-USD", "ETH-USD"} for p in proposal["portfolio"]["positions"])
            elif name == "Unknown asset rejection":
                passed = status == 200 and not proposal and (trace.get("error") or {}).get("code") == "ASSET_NOT_IN_UNIVERSE"
            else:
                passed = status == 200 and not proposal and trace.get("status") == "INVALID_REQUEST"
            check(name, passed, http_status=status, backend_status=trace.get("status"), backend_error=trace.get("error"), proposal=bool(proposal))
            if proposal:
                review = proposal.get("changeReview", {})
                baseline = {p["symbol"]: p["weight"] for p in current["positions"]}
                check("Avis préalable conservé par le proxy : " + name,
                      review.get("method") == "questionnaire_change_review_v1"
                      and review.get("applied") is False and review.get("confirmation_required") is True
                      and review.get("baseline_weights_pct") == baseline
                      and review.get("verdict") in {"compatible", "clarification_required", "not_retained"},
                      verdict=review.get("verdict"))
            (OUTPUT / (name.lower().replace(" ", "-") + ".json")).write_text(json.dumps(response, indent=2), encoding="utf-8")
            # Le banc ne simule une confirmation que pour un avis compatible.
            if name == "Equity addition" and passed and proposal.get("changeReview", {}).get("verdict") == "compatible":
                current = proposal["portfolio"]

        # Isolate ticker parsing from the engine policy by exercising structured backend edits.
        for ticker in ["XEF.TO", "XBB.TO", "BND"]:
            status, response = request(upstream, "/chat", {"questionnaire": form, "portfolio": current,
                "changes": [{"ticker": ticker, "add_pct": 1}], "as_of": report["as_of"]})
            proposal = response.get("proposal")
            passed = status == 200 and frontend_valid(proposal)
            check("Structured backend addition " + ticker, passed, http_status=status, backend_status=response.get("status"),
                  backend_error=response.get("error"), proposal=bool(proposal), response_message=response.get("message") if not passed else None)

    before = len(report["requests"])
    status, response = request(base, "/api/portfolio", {"questionnaire": {"version": "invalid", "answers": {}}})
    check("Malformed questionnaire rejected before backend", status == 400 and len(report["requests"]) == before, http_status=status)

    for folder in sorted(AUDIT.iterdir() if AUDIT.exists() else []):
        if not folder.is_dir():
            continue
        artifacts = {name: json.loads((folder / f"{name}.json").read_text()) for name in ARTIFACTS}
        result = artifacts["result"]
        complete = not list(folder.glob("*.pending"))
        released = result.get("compliance", {}).get("passed") is True
        errors = []
        if released:
            selected = result["assessment"]["selected_branch"]
            errors = release_errors(artifacts["evidence"], artifacts["data_manifest"], artifacts["decisions"], selected)
            errors += validate_draft(fallback_draft(artifacts["evidence"]), artifacts["evidence"])
            assert abs(sum(result["portfolio"]["weights"].values()) - 1) < 1e-6
            for reference in artifacts["data_manifest"]["inputs"].values():
                assert hashlib.sha256(Path(reference["path"]).read_bytes()).hexdigest() == reference["sha256"]
        report["audits"].append({"run_id": folder.name, "status": result["status"], "files": len(ARTIFACTS),
                                  "released": released, "errors": errors, "complete": complete,
                                  "explanation_mode": result.get("explanation_mode")})
    check("Audit artifacts complete and released evidence passes validation", len(report["audits"]) >= 5 and all(x["complete"] and not x["errors"] for x in report["audits"]), runs=len(report["audits"]))
    check("Source CSV unchanged", original_hash == hashlib.sha256((ROOT / "dataset/prices_weekly.csv").read_bytes()).hexdigest())
finally:
    node.terminate()
    node.wait(timeout=10)
    log.close()
    bridge.shutdown()
    bridge.server_close()
    report["passed"] = sum(c["passed"] for c in report["checks"])
    report["failed"] = sum(not c["passed"] for c in report["checks"])
    data = json.dumps(report, indent=2)
    (OUTPUT / "report.json").write_text(data, encoding="utf-8")
    (OUTPUT / (AUDIT.name + "-report.json")).write_text(data, encoding="utf-8")
    lines = ["# Local end-to-end verification", "",
             f"Result: {report['passed']} passed; {report['failed']} failed across {len(report['checks'])} checks.", "",
             report["scope"], "", "| Check | Result |", "| --- | --- |"]
    lines += [f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} |" for c in report["checks"]]
    lines += ["", f"Audit directory: `{AUDIT}`", "", "## Scope limits", "",
              "- Local HTTP bridge invokes the real Lambda handler; deployed AWS routing, S3 and Bedrock are not exercised.",
              "- Browser payload comes from the actual frontend module. Graphical rendering and browser DOM interactions are not tested.",
              "- Explanation uses the checked deterministic fallback; no live model calls."]
    (OUTPUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("REPORT", OUTPUT / "report.json", "PASS", report["passed"], "FAIL", report["failed"], flush=True)

sys.exit(1 if report["failed"] else 0)
