"""
EventBridge (Glue Job State Change) → DynamoDB (este repo, fase 2).

- FAILED: el job Glue no llegó a pipeline_layer_finish → se escribe capa FAILED aquí.
- SUCCEEDED con GLUE_SELF_REPORTS_PIPELINE_STATE: el job ya escribió OK en Dynamo (pipeline_layer_finish);
  esta Lambda no duplica; puede encadenar Glue directo si no hay cadena por DynamoDB Stream.
- SUCCEEDED sin self-report (legado): actualiza Dynamo.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

glue = boto3.client("glue")

# --- capas Glue (alineado con fase 1 / 3) ---
LAYER_LAKE_VALIDATED_TO_STANDARDIZED = "lake_validated_to_standardized"
LAYER_LAKE_STANDARDIZED_TO_SILVER = "lake_standardized_to_silver"


def put_pipeline_layer_succeeded(
    *,
    layer: str,
    project: str,
    environment: str,
    business_date: str,
    batch_id: str,
    extra: dict[str, Any] | None = None,
) -> bool:
    """No se usa PutEvents para encadenar; el estado vive en Dynamo y los routers leen el stream."""
    _ = (layer, project, environment, business_date, batch_id, extra)
    return False


def _maybe_start_next_glue_job(
    *,
    layer: str,
    st: str,
    state: str,
    args: dict,
) -> dict | None:
    """Tras OK en validated→std, arranca std→silver directo (solo si NO hay cadena por DynamoDB Stream)."""
    if (os.environ.get("ENABLE_PIPELINE_DDB_STREAM_CHAIN") or "").lower() in ("1", "true", "yes"):
        return None
    if state != "SUCCEEDED" or st != "SUCCEEDED":
        return None
    if layer != LAYER_LAKE_VALIDATED_TO_STANDARDIZED:
        return None
    next_name = (os.environ.get("GLUE_JOB_NAME_STD_TO_SILVER") or "").strip()
    if not next_name:
        return None
    next_args = {k: v for k, v in (args or {}).items() if k.startswith("--") and v is not None}
    resp = glue.start_job_run(JobName=next_name, Arguments=next_args)
    rid = resp.get("JobRunId")
    logger.info("started_next_glue job=%s run_id=%s", next_name, rid)
    return {"next_glue_job": next_name, "next_job_run_id": rid}


JOB_SUFFIX_TO_LAYER = {
    "validated-to-std": LAYER_LAKE_VALIDATED_TO_STANDARDIZED,
    "std-to-silver": LAYER_LAKE_STANDARDIZED_TO_SILVER,
}


def _layer_from_job_name(name: str) -> str | None:
    n = name.lower()
    for suf, layer in JOB_SUFFIX_TO_LAYER.items():
        if suf in n.replace("_", "-"):
            return layer
    return None


def handler(event, context):
    detail = event.get("detail") or {}
    state = (detail.get("state") or "").upper()
    job_name = detail.get("jobName") or ""
    run_id = detail.get("jobRunId") or ""
    if not job_name or not run_id:
        return {"skipped": True, "reason": "missing jobName/jobRunId"}

    layer = _layer_from_job_name(job_name)
    if not layer:
        return {"skipped": True, "reason": "unknown_job_pattern", "jobName": job_name}

    table_name = (os.environ.get("PIPELINE_RUNS_TABLE") or "").strip()
    if not table_name:
        return {"skipped": True, "reason": "no_PIPELINE_RUNS_TABLE"}

    project = os.environ.get("PROJECT", "reporting")
    env = os.environ.get("ENVIRONMENT", "dev")

    jr = glue.get_job_run(JobName=job_name, RunId=run_id, PredecessorsIncluded=False).get(
        "JobRun", {}
    )
    args = jr.get("Arguments") or {}
    bd = (
        args.get("--PIPELINE_BUSINESS_DATE")
        or args.get("PIPELINE_BUSINESS_DATE")
        or datetime.now(timezone.utc).date().isoformat()
    )
    bid = (
        args.get("--PIPELINE_BATCH_ID")
        or args.get("PIPELINE_BATCH_ID")
        or f"glue-{run_id[:12]}"
    )

    pk = f"PIPE#{project}#{env}#BDATE#{bd}"
    sk = f"RUN#{bid}"
    env_key = f"PIPE#{project}#{env}"
    now = datetime.now(timezone.utc).isoformat()

    st = "SUCCEEDED" if state == "SUCCEEDED" else "FAILED"
    self_reports = (os.environ.get("GLUE_SELF_REPORTS_PIPELINE_STATE") or "").lower() in (
        "1",
        "true",
        "yes",
    )

    if state == "SUCCEEDED" and self_reports:
        out: dict = {
            "pk": pk,
            "sk": sk,
            "layer": layer,
            "status": st,
            "glue_self_reports": True,
        }
        try:
            chain = _maybe_start_next_glue_job(
                layer=layer,
                st=st,
                state=state,
                args=args,
            )
            if chain:
                out["chain"] = chain
        except Exception:
            logger.exception("chain_start_next_glue_failed layer=%s", layer)
        return out

    layer_doc = {
        "status": st,
        "updated_at": now,
        "glue_job_name": job_name,
        "glue_job_run_id": run_id,
        "error_message": detail.get("message"),
    }

    ddb = boto3.resource("dynamodb").Table(table_name)
    log_entry = [
        {
            "t": now,
            "layer": layer,
            "action": "glue_job",
            "status": st,
            "job_name": job_name,
            "run_id": run_id,
        }
    ]

    name_map = {"#lr": layer}
    try:
        ddb.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression=(
                "SET env_key = :ek, business_date = :bd, updated_at = :ua, "
                "layers.#lr = :ldoc, "
                "execution_log = list_append(if_not_exists(execution_log, :empty), :elog)"
            ),
            ExpressionAttributeNames=name_map,
            ExpressionAttributeValues={
                ":ek": env_key,
                ":bd": bd,
                ":ua": now,
                ":ldoc": layer_doc,
                ":empty": [],
                ":elog": log_entry,
            },
        )
    except Exception:
        logger.exception(
            "dynamo_update_failed pk=%s sk=%s layer=%s job=%s",
            pk,
            sk,
            layer,
            job_name,
        )
        raise

    logger.info(
        "layer_recorded layer=%s status=%s business_date=%s batch=%s job=%s",
        layer,
        st,
        bd,
        bid,
        job_name,
    )
    out = {"pk": pk, "sk": sk, "layer": layer, "status": st}
    if st == "SUCCEEDED":
        try:
            put_pipeline_layer_succeeded(
                layer=layer,
                project=project,
                environment=env,
                business_date=bd,
                batch_id=bid,
            )
        except Exception:
            logger.exception("emit_pipeline_event_failed layer=%s", layer)
    try:
        chain = _maybe_start_next_glue_job(
            layer=layer,
            st=st,
            state=state,
            args=args,
        )
        if chain:
            out["chain"] = chain
    except Exception:
        logger.exception("chain_start_next_glue_failed layer=%s", layer)
    return out
