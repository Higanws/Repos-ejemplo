"""
Router fase 2 (solo lake / Glue): consume DynamoDB Streams de pipeline_runs.

Cuando las capas `raw` o `lake_validated_to_standardized` pasan a SUCCEEDED en Dynamo,
arranca el siguiente Glue.

Redshift / SFN no están aquí: `redshift_sfn_stream_router` en reporting-infra-phase3.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

glue = boto3.client("glue")
_deser = TypeDeserializer()

LAYERS = frozenset({"raw", "lake_validated_to_standardized"})


def _deserialize_image(image: dict | None) -> dict[str, Any]:
    if not image:
        return {}
    return {k: _deser.deserialize(v) for k, v in image.items()}


def _layer_status(layers: dict[str, Any], layer: str) -> str:
    doc = layers.get(layer)
    if isinstance(doc, dict):
        return (doc.get("status") or "").upper()
    return ""


def _just_succeeded(old_layers: dict[str, Any], new_layers: dict[str, Any], layer: str) -> bool:
    return _layer_status(old_layers, layer) != "SUCCEEDED" and _layer_status(
        new_layers, layer
    ) == "SUCCEEDED"


def _extract_business_date_batch(item: dict[str, Any]) -> tuple[str, str]:
    bd = (item.get("business_date") or "").strip()
    sk = (item.get("sk") or "").strip()
    bid = sk[4:] if sk.startswith("RUN#") else ""
    if not bd:
        pk = item.get("pk") or ""
        if "BDATE#" in str(pk):
            bd = str(pk).split("BDATE#", 1)[-1]
    return bd, bid


def _pipeline_args(bd: str, bid: str) -> dict[str, str]:
    tbl = (os.environ.get("PIPELINE_RUNS_TABLE") or "").strip()
    proj = os.environ.get("PROJECT", "reporting")
    env = os.environ.get("ENVIRONMENT", "dev")
    out: dict[str, str] = {
        "--PIPELINE_BUSINESS_DATE": bd,
        "--PIPELINE_BATCH_ID": bid,
        "--PIPELINE_PROJECT": proj,
        "--PIPELINE_ENVIRONMENT": env,
    }
    if tbl:
        out["--PIPELINE_RUNS_TABLE"] = tbl
    return out


def _start_glue(job_name: str, bd: str, bid: str) -> dict[str, Any]:
    args = _pipeline_args(bd, bid)
    resp = glue.start_job_run(JobName=job_name, Arguments=args)
    return {"action": "StartJobRun", "job": job_name, "job_run_id": resp.get("JobRunId")}


def handler(event: dict, context: Any) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for record in event.get("Records") or []:
        if record.get("eventName") not in ("INSERT", "MODIFY"):
            continue
        ddb = record.get("dynamodb") or {}
        new_image = _deserialize_image(ddb.get("NewImage"))
        old_image = _deserialize_image(ddb.get("OldImage"))
        if not new_image:
            continue
        new_layers = new_image.get("layers") or {}
        old_layers = old_image.get("layers") or {}
        if not isinstance(new_layers, dict):
            continue
        bd, bid = _extract_business_date_batch(new_image)
        if not bd or not bid:
            logger.warning(
                "lake_stream_router skip_missing_bd_bid pk=%s sk=%s",
                new_image.get("pk"),
                new_image.get("sk"),
            )
            continue
        for layer in LAYERS:
            if not _just_succeeded(old_layers, new_layers, layer):
                continue
            if layer == "raw":
                j1 = (os.environ.get("GLUE_JOB_VALIDATED_TO_STD_NAME") or "").strip()
                if not j1:
                    raise RuntimeError("GLUE_JOB_VALIDATED_TO_STD_NAME vacío")
                out = _start_glue(j1, bd, bid)
                logger.info("lake_stream_router raw->%s %s", j1, out)
                results.append(out)
            elif layer == "lake_validated_to_standardized":
                j2 = (os.environ.get("GLUE_JOB_STD_TO_SILVER_NAME") or "").strip()
                if not j2:
                    raise RuntimeError("GLUE_JOB_STD_TO_SILVER_NAME vacío")
                out = _start_glue(j2, bd, bid)
                logger.info("lake_stream_router v2std->%s %s", j2, out)
                results.append(out)
    return {"processed": len(results), "results": results}
