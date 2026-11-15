"""Explicit live Bedrock connection test. Run in the credentialed terminal."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from alphaforge.application.llm import LLMCallError
from alphaforge.infrastructure.bedrock import BedrockLLMClient, BedrockSettings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="global.amazon.nova-2-lite-v1:0",
                        help="An accessible model/profile ID; default is the team's test model.")
    args = parser.parse_args()
    settings = BedrockSettings(model_id=args.model_id)
    session = boto3.Session()
    try:
        identity = session.client("sts", region_name=settings.region).get_caller_identity()
        print(f"Account: {identity['Account']}")
        print(f"Region: {settings.region}; model/profile: {settings.model_id}")
        print("Sending one live connection-test request (AWS usage is billable).", flush=True)
        llm = BedrockLLMClient.connect(settings, session)
        response = llm.generate(
            system="You are a connection-test assistant. Return only the requested phrase.",
            prompt="Reply with exactly: Bedrock connection successful",
        )
    except LLMCallError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        if error.code in {"AccessDeniedException", "UnauthorizedException"}:
            print("Check event-account model access, InvokeModel permission and inference-profile permissions.",
                  file=sys.stderr)
        elif error.code in {"ExpiredTokenException", "ExpiredToken", "InvalidClientTokenId",
                            "UnrecognizedClientException", "NoCredentialsError"}:
            print("Refresh the event PowerShell credentials in this same terminal.", file=sys.stderr)
        elif error.code == "IncompleteResponse":
            print("Model output was truncated, blocked or incomplete; no success claimed.", file=sys.stderr)
        return 1
    except (BotoCoreError, ClientError) as error:
        # Do not dump credential data or arbitrary service response bodies.
        print(f"FAILED: AWS authentication/client setup ({type(error).__name__}). "
              "Check the credentials in this terminal.", file=sys.stderr)
        return 1
    print(response.text)
    print(f"Converse completed. Usage: {response.usage}; request ID: {response.request_id}")
    print("This verifies connectivity only, not evidence validation or portfolio correctness.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
