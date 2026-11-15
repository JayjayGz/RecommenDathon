"""Boto3 Converse adapter shared by language stages; no AWS calls on import."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from alphaforge.application.llm import LLMCallError, LLMResponse


@dataclass(frozen=True)
class BedrockSettings:
    model_id: str
    region: str = "us-east-1"

    def __post_init__(self):
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("A Bedrock model or inference profile ID is required.")
        if self.region != "us-east-1":
            raise ValueError("The current team configuration uses us-east-1.")


class BedrockLLMClient:
    def __init__(self, settings: BedrockSettings, runtime_client: Any):
        self.settings = settings
        self._client = runtime_client

    @classmethod
    def connect(cls, settings: BedrockSettings,
                session: boto3.Session | None = None) -> "BedrockLLMClient":
        # Uses the SDK credential chain: event terminal credentials locally,
        # Lambda execution role in AWS. Never pass or persist secrets here.
        session = session if session is not None else boto3.Session()
        client = session.client(
            "bedrock-runtime",
            region_name=settings.region,
            config=Config(
                connect_timeout=5,
                read_timeout=60,
                retries={"max_attempts": 5, "mode": "adaptive"},
            ),
        )
        return cls(settings, client)

    def generate(self, *, system: str, prompt: str,
                 max_tokens: int = 1024) -> LLMResponse:
        for name, value in (("system", system), ("prompt", prompt)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty text.")
        if type(max_tokens) is not int or max_tokens < 1000:
            raise ValueError("max_tokens must be an integer of at least 1000.")
        try:
            response = self._client.converse(
                modelId=self.settings.model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                # Do not send temperature/topP: model support differs.
                inferenceConfig={"maxTokens": max_tokens},
            )
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "ClientError")
            request_id = error.response.get("ResponseMetadata", {}).get("RequestId")
            raise LLMCallError(
                code, f"Bedrock Converse failed ({code}).",
                request_id=request_id,
            ) from error
        except BotoCoreError as error:
            code = type(error).__name__
            raise LLMCallError(code, f"AWS connection or credentials failed ({code}).") from error

        if not isinstance(response, dict):
            raise LLMCallError("InvalidResponse", "Bedrock returned an invalid response.")
        snapshot = deepcopy(response)
        metadata = response.get("ResponseMetadata")
        request_id = metadata.get("RequestId") if isinstance(metadata, dict) else None
        reason = response.get("stopReason")
        if reason != "end_turn":
            # Truncation, guardrail blocks and tool requests are not complete
            # explanations. A separate orchestrator must handle tool loops.
            raise LLMCallError(
                "IncompleteResponse", f"Bedrock did not finish normally ({reason}).",
                request_id=request_id, raw_response=snapshot,
            )
        try:
            message = response["output"]["message"]
            if message["role"] != "assistant" or not isinstance(message["content"], list):
                raise ValueError("Invalid assistant message")
            blocks = message["content"]
            if any(not isinstance(block, dict) for block in blocks):
                raise ValueError("Invalid content block")
            text_parts = [block["text"] for block in blocks if "text" in block]
            if not text_parts or any(not isinstance(part, str) for part in text_parts):
                raise ValueError("Missing or invalid text")
            text = "\n".join(text_parts).strip()
            if not text:
                raise ValueError("Empty text")
            usage = response["usage"]
            if not isinstance(usage, dict):
                raise ValueError("Invalid usage metadata")
        except (KeyError, TypeError, ValueError) as error:
            raise LLMCallError(
                "InvalidResponse", "Bedrock response has no valid assistant text/metadata.",
                request_id=request_id, raw_response=snapshot,
            ) from error
        return LLMResponse(
            text=text, model_id=self.settings.model_id, stop_reason=reason,
            request_id=request_id, usage=deepcopy(usage), raw_response=snapshot,
        )
