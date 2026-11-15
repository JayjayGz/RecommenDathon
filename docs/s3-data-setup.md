# S3 input configuration

The local `backend/samconfig.toml` selects the existing bucket
`recommendathon-825765422596-us-east-1-an` for inputs and audit records,
with `DataPrefix=data`. The config is ignored by Git; this document preserves
the deployment settings for review.

Required object keys (case-sensitive):

```text
data/prices_daily.csv
data/fx_usdcad_daily.csv
data/profiles.json
```

The existing `S3SnapshotSource` reads all three objects per invocation and records
their hashes and returned version metadata. Other CSVs are not consumed by this
source. Uploading a file at the bucket root does not put it under `data/`.

The same bucket receives audit JSON at `runs/{run_id}/`. This is separate from the
input prefix. Storage and request charges apply; keep the bucket private, encrypted,
and accessed over HTTPS. The stack references the bucket without managing its
contents or bucket policy.

## Activation still required

The template only enables S3 mode when `DataBucketName`, `AuditBucketName`, and
`RuntimePolicyArn` are all provided. The saved bucket/prefix settings do not create
or attach an IAM policy. Add the reviewed runtime policy ARN to the saved
`parameter_overrides` without removing the existing three overrides, then build
and deploy using [the Lambda setup guide](lambda-setup.md).

The policy must permit reading the three exact input objects and writing audit
objects under `runs/`. Use the baseline generation procedure in
[the workflow guide](orchestrator.md), then narrow and review
it before attachment. The baseline generated on 2026-11-15 included wildcard
resources and optional S3/KMS operations, so it was not applied. Additional KMS
permissions depend on the bucket's actual encryption configuration.

## Verification

Infrastructure owns configuration; data supports input-contract review. Loaded
lessons: L-001, L-002, L-006. No CSV contents or calculation rules were changed.
Offline S3 snapshot, orchestrator and handler checks: 54 passed. Template:
`cfn-lint` passed. These checks do not verify live object existence or IAM access.
No cloud deployment or IAM attachment was performed. Next owner: runtime policy
review and deployment; input data must still satisfy the documented holdings
and observation-frequency checks.
