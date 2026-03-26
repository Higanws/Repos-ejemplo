"""
Estado de corridas en DynamoDB (tabla pipeline_runs): capas, tablas y log de ejecución.
Solo actúa si PIPELINE_RUNS_TABLE está definido.

La capa `raw` pasa a SUCCEEDED solo cuando **todas** las tablas listadas en PIPELINE_RAW_TABLES
están en validated; así el router de fase 2 (DynamoDB Stream) dispara Glue una sola vez.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3

from lib.pipeline_layers import LAYER_RAW

_TABLE = None


def _table():
    global _TABLE
    name = (os.environ.get("PIPELINE_RUNS_TABLE") or "").strip()
    if not name:
        return None
    if _TABLE is None:
        _TABLE = boto3.resource("dynamodb").Table(name)
    return _TABLE


def _keys(project: str, environment: str, business_date: str, batch_id: str) -> dict[str, str]:
    pk = f"PIPE#{project}#{environment}#BDATE#{business_date}"
    sk = f"RUN#{batch_id}"
    env_key = f"PIPE#{project}#{environment}"
    return {"pk": pk, "sk": sk, "env_key": env_key}


def _expected_tables() -> list[str]:
    return [
        t.strip()
        for t in (os.environ.get("PIPELINE_RAW_TABLES") or "trade_event,price_history").split(",")
        if t.strip()
    ]


def record_raw_ingest_result(
    *,
    project: str,
    environment: str,
    business_date: str,
    batch_id: str,
    table: str,
    lane: str,
    s3_key: str,
    contract_set_version: str | None = None,
) -> dict[str, Any] | None:
    """
    Registra ingesta RAW por tabla; luego sincroniza layers.raw (PENDING / SUCCEEDED).
    """
    tbl = _table()
    if tbl is None:
        return None

    k = _keys(project, environment, business_date, batch_id)
    now = datetime.now(timezone.utc).isoformat()

    log_entry = [
        {
            "t": now,
            "layer": LAYER_RAW,
            "action": "ingest_table",
            "table": table,
            "lane": lane,
            "s3_key": s3_key,
        }
    ]

    expr_names = {"#tbl": "tables", "#tn": table}
    vals: dict[str, Any] = {
        ":env_key": k["env_key"],
        ":bd": business_date,
        ":ua": now,
        ":tinfo": {
            "lane": lane,
            "status": "validated" if lane == "validated" else "rejected",
            "s3_key": s3_key,
            "updated_at": now,
        },
        ":empty": [],
        ":elog": log_entry,
    }
    update = (
        "SET env_key = :env_key, business_date = :bd, updated_at = :ua, "
        "tables.#tn = :tinfo, "
        "execution_log = list_append(if_not_exists(execution_log, :empty), :elog)"
    )
    if contract_set_version:
        update += ", contract_set_version_phase1 = :csv"
        vals[":csv"] = contract_set_version

    tbl.update_item(
        Key={"pk": k["pk"], "sk": k["sk"]},
        UpdateExpression=update,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=vals,
    )

    _sync_raw_layer_status(tbl=tbl, k=k)

    return {"pk": k["pk"], "sk": k["sk"], "table": table}


def _sync_raw_layer_status(*, tbl, k: dict[str, str]) -> None:
    """Actualiza layers.raw: PENDING hasta que todas las tablas esperadas estén validated → SUCCEEDED."""
    expected = _expected_tables()
    if not expected:
        return

    resp = tbl.get_item(Key={"pk": k["pk"], "sk": k["sk"]})
    item = resp.get("Item") or {}
    tables = item.get("tables") or {}
    now = datetime.now(timezone.utc).isoformat()

    for tn in expected:
        info = tables.get(tn) or {}
        if info.get("status") != "validated":
            layer_raw: dict[str, Any] = {
                "status": "PENDING",
                "updated_at": now,
                "awaiting_tables": [e for e in expected if (tables.get(e) or {}).get("status") != "validated"],
            }
            tbl.update_item(
                Key={"pk": k["pk"], "sk": k["sk"]},
                UpdateExpression="SET layers.#lr = :lraw, updated_at = :ua",
                ExpressionAttributeNames={"#lr": LAYER_RAW},
                ExpressionAttributeValues={
                    ":lraw": layer_raw,
                    ":ua": now,
                },
            )
            return

    layer_ok: dict[str, Any] = {
        "status": "SUCCEEDED",
        "updated_at": now,
    }
    tbl.update_item(
        Key={"pk": k["pk"], "sk": k["sk"]},
        UpdateExpression="SET layers.#lr = :lraw, updated_at = :ua",
        ExpressionAttributeNames={"#lr": LAYER_RAW},
        ExpressionAttributeValues={
            ":lraw": layer_ok,
            ":ua": now,
        },
    )
