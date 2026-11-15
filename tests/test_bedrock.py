"""Offline adapter contract and failure tests; no real credentials or calls."""

from copy import deepcopy
import unittest
from unittest.mock import Mock

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.stub import Stubber

from alphaforge.application.llm import LLMCallError
from alphaforge.infrastructure.bedrock import BedrockLLMClient, BedrockSettings


def response():
    return {
        "output": {"message": {"role": "assistant", "content": [
            {"reasoningContent": {"reasoningText": {"text": "internal", "signature": "test"}}},
            {"text": "First."}, {"text": "Second."},
        ]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
        "metrics": {"latencyMs": 1},
        "ResponseMetadata": {"RequestId": "offline-test", "RetryAttempts": 0},
    }


class BedrockTests(unittest.TestCase):
    def setUp(self):
        self.runtime = Mock()
        self.runtime.converse.return_value = response()
        self.settings = BedrockSettings(model_id="test-model")
        self.llm = BedrockLLMClient(self.settings, self.runtime)

    def generate(self):
        return self.llm.generate(system="instructions", prompt="evidence")

    def test_joins_text_after_reasoning_and_keeps_audit_metadata(self):
        result = self.generate()
        self.assertEqual(result.text, "First.\nSecond.")
        self.assertEqual(result.request_id, "offline-test")
        self.assertEqual(result.usage["totalTokens"], 15)
        self.assertEqual(result.model_id, "test-model")
        self.runtime.converse.return_value["usage"]["totalTokens"] = 0
        self.assertEqual(result.raw_response["usage"]["totalTokens"], 15)

    def test_request_matches_real_sdk_schema(self):
        client = boto3.client("bedrock-runtime", region_name="us-east-1",
                              aws_access_key_id="testing", aws_secret_access_key="testing")
        with Stubber(client) as stub:
            stub.add_response("converse", response(), {
                "modelId": "test-model", "system": [{"text": "instructions"}],
                "messages": [{"role": "user", "content": [{"text": "evidence"}]}],
                "inferenceConfig": {"maxTokens": 1024},
            })
            result = BedrockLLMClient(self.settings, client).generate(
                system="instructions", prompt="evidence")
            self.assertEqual(result.text, "First.\nSecond.")
            stub.assert_no_pending_responses()

    def test_truncated_blocked_or_tool_output_is_not_success(self):
        for reason in ("max_tokens", "guardrail_intervened", "content_filtered", "tool_use", None):
            with self.subTest(reason=reason):
                self.runtime.converse.return_value = response()
                self.runtime.converse.return_value["stopReason"] = reason
                with self.assertRaises(LLMCallError) as caught:
                    self.generate()
                self.assertEqual(caught.exception.code, "IncompleteResponse")
                self.assertEqual(caught.exception.raw_response["stopReason"], reason)

    def test_no_text_is_rejected(self):
        for content in ([], [{"text": " "}], [{"text": 5}], [None], "invalid"):
            with self.subTest(content=content):
                self.runtime.converse.return_value = response()
                self.runtime.converse.return_value["output"]["message"]["content"] = content
                with self.assertRaises(LLMCallError):
                    self.generate()

    def test_invalid_response_shape_is_explicit(self):
        for raw in (None, {}, {"stopReason": "end_turn", "output": None}):
            with self.subTest(raw=raw):
                self.runtime.converse.return_value = raw
                with self.assertRaises(LLMCallError):
                    self.generate()

    def test_access_denied_has_one_application_attempt(self):
        self.runtime.converse.side_effect = ClientError({
            "Error": {"Code": "AccessDeniedException", "Message": "private service details"},
            "ResponseMetadata": {"RequestId": "denied"},
        }, "Converse")
        with self.assertRaises(LLMCallError) as caught:
            self.generate()
        self.assertEqual(caught.exception.code, "AccessDeniedException")
        self.assertNotIn("private", str(caught.exception))
        self.runtime.converse.assert_called_once()

    def test_missing_credentials_is_explicit(self):
        self.runtime.converse.side_effect = NoCredentialsError()
        with self.assertRaises(LLMCallError) as caught:
            self.generate()
        self.assertEqual(caught.exception.code, "NoCredentialsError")

    def test_bad_inputs_never_invoke_model(self):
        for kwargs in ({"system": "", "prompt": "ok"},
                       {"system": "ok", "prompt": ""},
                       {"system": "ok", "prompt": "ok", "max_tokens": 100},
                       {"system": "ok", "prompt": "ok", "max_tokens": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.llm.generate(**kwargs)
        self.runtime.converse.assert_not_called()

    def test_connect_uses_credentials_chain_and_team_retry_policy(self):
        session = Mock()
        BedrockLLMClient.connect(self.settings, session)
        kwargs = session.client.call_args.kwargs
        self.assertEqual(kwargs["region_name"], "us-east-1")
        self.assertEqual(kwargs["config"].retries, {"max_attempts": 5, "mode": "adaptive"})
        self.assertNotIn("aws_access_key_id", kwargs)

    def test_settings_require_model_and_team_region(self):
        with self.assertRaises(ValueError):
            BedrockSettings(model_id=" ")
        with self.assertRaises(ValueError):
            BedrockSettings(model_id="test-model", region="wrong-region")


if __name__ == "__main__":
    unittest.main()
