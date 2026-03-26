"""
Punto de entrada Lambda: Step Functions 04 envía p.ej.
{"job": "trade_event/ingest.py", "table": "trade_event"}.
Variables de entorno: RAW_BUCKET (Terraform), ENVIRONMENT (dev|test|prod).

Los mensajes van a stdout → grupo de logs de CloudWatch de la función Lambda.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_JOB_TABLE = {
    "trade_event/ingest.py": "trade_event",
    "price_history/ingest.py": "price_history",
}


def _payload(event: Any) -> dict[str, Any]:
    if isinstance(event, dict) and "Payload" in event:
        inner = event["Payload"]
        return inner if isinstance(inner, dict) else {}
    if isinstance(event, dict) and "body" in event:
        try:
            body = event["body"]
            if isinstance(body, str):
                return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            pass
    return event if isinstance(event, dict) else {}


def handler(event: Any, context: Any) -> dict[str, Any]:
    try:
        payload = _payload(event)
        job = (payload.get("job") or "").strip()
        if not job:
            raise ValueError("Payload.job requerido (ej. trade_event/ingest.py)")

        if job not in _JOB_TABLE:
            raise ValueError(f"job desconocido: {job!r}. Válidos: {sorted(_JOB_TABLE)}")

        env = os.environ.get("ENVIRONMENT", "dev")
        raw_bucket = (os.environ.get("RAW_BUCKET") or "").strip() or None
        batch_id = (payload.get("batch_id") or "").strip() or str(uuid.uuid4())

        logger.info(
            "ingest_start job=%s batch_id=%s env=%s",
            job,
            batch_id,
            env,
        )

        if _JOB_TABLE[job] == "trade_event":
            from trade_event.ingest import run as run_trade_event

            result = run_trade_event(environment=env, raw_bucket=raw_bucket, batch_id=batch_id)
        else:
            from price_history.ingest import run as run_price_history

            result = run_price_history(environment=env, raw_bucket=raw_bucket, batch_id=batch_id)

        _maybe_record_pipeline_dynamo(env, batch_id, result)
        logger.info(
            "ingest_ok table=%s lane=%s business_date=%s",
            result.get("table"),
            result.get("lane"),
            result.get("business_date"),
        )
        return result
    except Exception:
        logger.exception("ingest_failed")
        raise


def _maybe_record_pipeline_dynamo(env: str, batch_id: str, result: dict) -> None:
    if not os.environ.get("PIPELINE_RUNS_TABLE"):
        return
    bd = result.get("business_date")
    if not bd:
        return
    project = os.environ.get("PROJECT", "reporting")
    from lib.pipeline_dynamo import record_raw_ingest_result

    record_raw_ingest_result(
        project=project,
        environment=env,
        business_date=bd,
        batch_id=batch_id,
        table=str(result.get("table") or ""),
        lane=str(result.get("lane") or ""),
        s3_key=str(result.get("s3_key") or ""),
        contract_set_version=os.environ.get("CONTRACT_SET_VERSION"),
    )
