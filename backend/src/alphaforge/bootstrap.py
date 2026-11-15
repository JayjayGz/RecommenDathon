"""Composition root: connect application ports to local infrastructure."""
from .application.portfolio_engine import PortfolioEngine
from .infrastructure.local_data import LocalPortfolioRepository


def create_engine():
    return PortfolioEngine(LocalPortfolioRepository())


class ConfigurationError(ValueError):
    pass


def create_orchestrator():
    """Compose clients once; load inputs and create run state separately per invocation."""
    import os
    from pathlib import Path
    from .application.orchestrator import RecommendationOrchestrator
    from .infrastructure.local_data import DEFAULT_DATA_DIR, DEFAULT_PROFILES_PATH
    from .infrastructure.workflow_storage import (
        LocalAuditStore, LocalSnapshotSource, S3AuditStore, S3SnapshotSource,
    )

    mode = os.environ.get("ALPHAFORGE_MODE", "")
    model_id = os.environ.get("BEDROCK_MODEL_ID", "")
    llm = None
    if mode == "local":
        source = LocalSnapshotSource(os.environ.get("DATA_DIR", DEFAULT_DATA_DIR),
                                     os.environ.get("PROFILES_PATH", DEFAULT_PROFILES_PATH))
        audit = LocalAuditStore(os.environ.get("AUDIT_DIR", Path.cwd() / ".local-runs"))
    elif mode == "s3":
        bucket, audit_bucket = os.environ.get("DATA_BUCKET", ""), os.environ.get("AUDIT_BUCKET", "")
        prefix = os.environ.get("DATA_PREFIX", "inputs")
        if not bucket or not audit_bucket or not prefix or any(c in prefix for c in "*?\\"):
            raise ConfigurationError("S3 workflow configuration is incomplete")
        import boto3
        from botocore.config import Config
        session = boto3.Session()
        # Bound transport attempts separately from the application's explanation repair budget.
        read_client = session.client("s3", config=Config(connect_timeout=2, read_timeout=5,
                                    retries={"total_max_attempts": 1, "mode": "standard"}))
        audit_client = session.client("s3", config=Config(connect_timeout=1, read_timeout=2,
                                     retries={"total_max_attempts": 1, "mode": "standard"}))
        source, audit = S3SnapshotSource(read_client, bucket, prefix), S3AuditStore(audit_client, audit_bucket)
    else:
        raise ConfigurationError("Set ALPHAFORGE_MODE to local or s3")
    if model_id:
        import boto3
        from botocore.config import Config
        from .infrastructure.bedrock import BedrockLLMClient, BedrockSettings
        settings = BedrockSettings(model_id=model_id, region=os.environ.get("AWS_REGION", "us-east-1"))
        runtime = boto3.Session().client("bedrock-runtime", region_name=settings.region,
                    config=Config(connect_timeout=2, read_timeout=12,
                                  retries={"total_max_attempts": 1, "mode": "standard"}))
        llm = BedrockLLMClient(settings, runtime)
    return RecommendationOrchestrator(source, audit, llm)
