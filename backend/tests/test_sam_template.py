"""Actual SAM translation regression; static lint alone missed the reported defect.

Run via unittest in the SAM CLI bundled Python, or install aws-sam-translator
from the development requirements to include these tests in normal pytest runs.
"""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

try:
    from samtranslator.translator.transform import transform
    from samtranslator.yaml_helper import yaml_parse
    from samtranslator.model.exceptions import InvalidDocumentException
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

TEMPLATE = Path(__file__).resolve().parents[1] / "template.yaml"
POLICY_ARN = "arn:aws:iam::123456789012:policy/AlphaForgeRuntimeTest"


class StaticManagedPolicies:
    def load(self):
        # Offline lookup: no IAM API calls or real credentials.
        return {"AWSLambdaBasicExecutionRole": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"}


@unittest.skipUnless(HAS_TRANSLATOR, "Install aws-sam-translator or use SAM CLI bundled Python")
class SamPolicyTranslationTests(unittest.TestCase):
    def template(self):
        template = yaml_parse(TEMPLATE.read_text(encoding="utf-8"))
        # SAM build normally adds this; translation tests don't build/push an image.
        template["Resources"]["AlphaForgeFunction"]["Properties"]["ImageUri"] = (
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test:fixture"
        )
        return template

    def translate(self, template, policy):
        with patch.dict(os.environ, {"AWS_DEFAULT_REGION": "us-east-1",
                                     "AWS_EC2_METADATA_DISABLED": "true"}):
            return transform(template, {"RuntimePolicyArn": policy}, StaticManagedPolicies())

    def test_previous_property_level_conditional_reproduces_deployment_error(self):
        template = self.template()
        template["Resources"]["AlphaForgeFunction"]["Properties"]["Policies"] = {
            "Fn::If": ["HasRuntimePolicy", [{"Ref": "RuntimePolicyArn"}], {"Ref": "AWS::NoValue"}]
        }
        with self.assertRaises(InvalidDocumentException) as failure:
            self.translate(template, "")
        self.assertIn("Policies", str(failure.exception))
        self.assertIn("not valid", str(failure.exception))

    def test_list_item_conditional_translates_with_and_without_runtime_policy(self):
        for policy in ("", POLICY_ARN):
            with self.subTest(policy_present=bool(policy)):
                output = self.translate(self.template(), policy)
                role = output["Resources"]["AlphaForgeFunctionRole"]
                self.assertEqual(role["Type"], "AWS::IAM::Role")
                managed = role["Properties"]["ManagedPolicyArns"]
                self.assertIn("arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole", managed)
                conditional = next(item["Fn::If"] for item in managed if isinstance(item, dict) and "Fn::If" in item)
                self.assertEqual(conditional[0], "HasRuntimePolicy")
                self.assertEqual(conditional[1], {"Ref": "RuntimePolicyArn"})
                self.assertEqual(conditional[2], {"Ref": "AWS::NoValue"})


if __name__ == "__main__":
    unittest.main()
