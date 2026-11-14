# AWS Services

The stack is deliberately small for a 24-hour hackathon. Nothing is deployed yet. Confirm the region and available Bedrock models before building.

## Use now

| Service | Layer | Purpose |
| --- | --- | --- |
| AWS Lambda (with a Function URL) | Application | Runs the orchestrator and pipeline agents in one function |
| Amazon Bedrock | Application | LLM for the Explanation Agent (and the optional wording check in the Compliance Gate). Teammates' questionnaire agent may also use it |
| Amazon S3 | Infrastructure | Holds the source CSVs, the audit trail (`runs/{run_id}/`) and optionally the static UI |

Notes:

- Load the CSVs once per Lambda container, or package them with the function, so each request works from memory. The dataset has about 40,000 price rows.
- S3 does not speed up generation. LLM latency dominates, so keep Bedrock calls few.
- Use an IAM role with least privilege: read on the data prefix, write on `runs/`, and invoke on the chosen Bedrock model.

## Not used (add later only if needed)

| Service | Why skipped |
| --- | --- |
| Step Functions | The pipeline is short and linear. A Python loop handles ordering and the compliance retry |
| DynamoDB | S3 JSON files cover the audit trail |
| API Gateway, CloudFront, Cognito | The Function URL covers the endpoint, and the demo does not need sign-in or a CDN |
| Secrets Manager | No external API keys. Bedrock uses the IAM role |
| CDK / CloudFormation | Setup time is better spent on the product. Use the console or a small script |

CloudWatch Logs is enabled for Lambda automatically.
