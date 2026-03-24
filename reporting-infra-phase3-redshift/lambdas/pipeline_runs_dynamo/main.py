"""
Lambda **pipeline_runs_dynamo** (fase 3) — paralelo a ``glue_job_status_dynamo`` en fase 2.

Responsabilidad única: leer/escribir ``pipeline_runs`` en DynamoDB y validar contratos silver en S3
antes del COPY. No ejecuta SQL en Redshift (eso es ``redshift_sql``).

Disparo: invocación síncrona desde la Lambda ``redshift_sql`` (``lambda:InvokeFunction``), no EventBridge.
El encadenamiento al siguiente paso lo hace ``redshift_sfn_stream_router`` vía DynamoDB Stream.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- capas relevantes para gate de fase 3 ---
LAYER_LAKE_STANDARDIZED_TO_SILVER = "lake_standardized_to_silver"
LAYER_REDSHIFT_SILVER = "redshift_silver"
LAYER_GOLD = "gold"

PREVIOUS_BY_LAYER: dict[str, str] = {
    LAYER_REDSHIFT_SILVER: LAYER_LAKE_STANDARDIZED_TO_SILVER,
    LAYER_GOLD: LAYER_REDSHIFT_SILVER,
}


def previous_layer(layer: str) -> str | None:
    return PREVIOUS_BY_LAYER.get(layer)


def redshift_script_target_layer(script: str) -> str | None:
    s = script.replace("\\", "/").lower()
    if "copy_s3_to_silver" in s:
        return LAYER_REDSHIFT_SILVER
    if "silver_to_gold" in s or "silver_facts_to_gold" in s or "to_gold_" in s:
        return LAYER_GOLD
    return None


def put_pipeline_layer_succeeded(
    *,
    layer: str,
    project: str,
    environment: str,
    business_date: str,
    batch_id: str,
    extra: dict[str, Any] | None = None,
) -> bool:
    """Compat: no se usa PutEvents para encadenar; el estado vive en Dynamo."""
    _ = (layer, project, environment, business_date, batch_id, extra)
    return False


# --- contratos silver S3 ---
_s3 = boto3.client("s3")


def _load_json(bucket: str, key: str) -> dict[str, Any]:
    body = _s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return json.loads(body)


def _first_object_key(bucket: str, prefix: str) -> str | None:
    r = _s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=50)
    for obj in r.get("Contents") or []:
        k = obj.get("Key") or ""
        if k.endswith("/"):
            continue
        return k
    return None


def _prefix_has_parquet(bucket: str, prefix: str) -> bool:
    r = _s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=80)
    for obj in r.get("Contents") or []:
        k = (obj.get("Key") or "").lower()
        if k.endswith(".parquet"):
            return True
    return False


def _check_json_payload(data: dict[str, Any], contract: dict[str, Any]) -> None:
    required = contract.get("required") or []
    props = contract.get("properties") or {}
    for key in required:
        if key not in data:
            raise RuntimeError(f"contrato JSON: falta campo requerido {key!r}")
        typ = (props.get(key) or {}).get("type")
        val = data[key]
        if typ == "string" and not isinstance(val, str):
            raise RuntimeError(f"contrato JSON: {key!r} debe ser string, no {type(val).__name__}")
        if typ == "number" and not isinstance(val, (int, float)):
            raise RuntimeError(f"contrato JSON: {key!r} debe ser number")


def _check_csv_sample(body: bytes, contract: dict[str, Any]) -> None:
    required_cols = contract.get("required_columns") or []
    if not required_cols:
        return
    text = body.decode("utf-8", errors="replace")
    first = text.splitlines()[0] if text else ""
    reader = csv.reader(io.StringIO(first))
    row = next(reader, [])
    headers = [c.strip() for c in row]
    for col in required_cols:
        if col not in headers:
            raise RuntimeError(f"contrato CSV: falta columna requerida {col!r} en cabecera {headers!r}")


def _validate_one_input(
    *,
    data_bucket: str,
    prefix: str,
    art_bucket: str,
    contract_rel: str,
    contracts_root: str,
) -> None:
    rel = contract_rel.strip().lstrip("/")
    ckey = f"{contracts_root.rstrip('/')}/{rel}"
    contract = _load_json(art_bucket, ckey)
    fmt = (contract.get("format") or "").lower()
    key = _first_object_key(data_bucket, prefix)
    if not key:
        raise RuntimeError(f"contrato: sin objetos bajo s3://{data_bucket}/{prefix}")

    obj = _s3.get_object(Bucket=data_bucket, Key=key)
    body = obj["Body"].read()

    if fmt == "json":
        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError("contrato JSON: raíz debe ser objeto")
        _check_json_payload(data, contract)
        return
    if fmt == "csv":
        _check_csv_sample(body, contract)
        return
    if fmt in ("parquet_logical", "parquet"):
        if not _prefix_has_parquet(data_bucket, prefix):
            raise RuntimeError(f"contrato parquet: sin .parquet bajo s3://{data_bucket}/{prefix}")
        return

    logger.info("contract_validation_skip_unknown_format format=%s key=%s", fmt, ckey)


def validate_silver_s3_for_copy(
    *,
    business_date: str,
    silver_bucket: str,
    art_bucket: str,
    registry_key: str,
    contracts_root: str,
) -> None:
    reg = _load_json(art_bucket, registry_key)
    root = contracts_root
    for load in reg.get("loads") or []:
        table = (load.get("table") or "").strip()
        cr = (load.get("input_contract") or "").strip()
        if not table:
            continue
        prefix = f"{table}/load_date={business_date}/"
        if not cr:
            if not _first_object_key(silver_bucket, prefix):
                logger.warning(
                    "silver sin objetos (opcional según carga): s3://%s/%s",
                    silver_bucket,
                    prefix,
                )
            continue
        _validate_one_input(
            data_bucket=silver_bucket,
            prefix=prefix,
            art_bucket=art_bucket,
            contract_rel=cr,
            contracts_root=root,
        )


# --- DynamoDB ---
_TABLE = None


def _table():
    name = (os.environ.get("PIPELINE_RUNS_TABLE") or "").strip()
    if not name:
        return None
    global _TABLE
    if _TABLE is None:
        _TABLE = boto3.resource("dynamodb").Table(name)
    return _TABLE


def _run_keys(project: str, env: str, business_date: str, batch_id: str) -> dict[str, str]:
    return {
        "pk": f"PIPE#{project}#{env}#BDATE#{business_date}",
        "sk": f"RUN#{batch_id}",
    }


def _layer_status_ok(layers: dict, layer_key: str) -> bool:
    doc = layers.get(layer_key) or {}
    if (doc.get("status") or "").upper() == "SUCCEEDED":
        return True
    if layer_key == LAYER_REDSHIFT_SILVER:
        legacy = layers.get("redshift") or {}
        if (legacy.get("status") or "").upper() == "SUCCEEDED":
            return True
    return False


def require_previous_layer_for_redshift_script(
    *,
    script: str,
    project: str,
    env: str,
    business_date: str,
    batch_id: str,
) -> None:
    if (os.environ.get("PIPELINE_SKIP_LAYER_CHECK") or "").lower() in ("1", "true", "yes"):
        return
    target = redshift_script_target_layer(script)
    if not target:
        return
    prev = previous_layer(target)
    if not prev:
        return
    tbl = _table()
    if tbl is None:
        return
    k = _run_keys(project, env, business_date, batch_id)
    resp = tbl.get_item(Key=k)
    item = resp.get("Item") or {}
    layers = item.get("layers") or {}
    if _layer_status_ok(layers, prev):
        return
    raise RuntimeError(
        f"Capa anterior {prev!r} no OK para pk={k['pk']} sk={k['sk']} "
        f"(script={script!r} requiere éxito previo antes de capa {target!r})."
    )


def record_redshift_layer(
    *,
    project: str,
    env: str,
    business_date: str,
    batch_id: str,
    script: str,
    result_summary: dict[str, Any],
) -> None:
    target = redshift_script_target_layer(script)
    if not target:
        return
    tbl = _table()
    if tbl is None:
        return
    k = _run_keys(project, env, business_date, batch_id)
    env_key = f"PIPE#{project}#{env}"
    now = datetime.now(timezone.utc).isoformat()
    layer_doc = {
        "status": "SUCCEEDED",
        "updated_at": now,
        "script": script,
        "detail": result_summary,
    }
    log_entry = [
        {
            "t": now,
            "layer": target,
            "action": "pipeline_runs_dynamo",
            "script": script,
        }
    ]
    tbl.update_item(
        Key=k,
        UpdateExpression=(
            "SET env_key = :ek, business_date = :bd, updated_at = :ua, "
            "layers.#lr = :ldoc, "
            "execution_log = list_append(if_not_exists(execution_log, :empty), :elog)"
        ),
        ExpressionAttributeNames={"#lr": target},
        ExpressionAttributeValues={
            ":ek": env_key,
            ":bd": business_date,
            ":ua": now,
            ":ldoc": layer_doc,
            ":empty": [],
            ":elog": log_entry,
        },
    )


def record_redshift_layer_failed(
    *,
    project: str,
    env: str,
    business_date: str,
    batch_id: str,
    script: str,
    error: str,
) -> None:
    target = redshift_script_target_layer(script)
    if not target:
        return
    tbl = _table()
    if tbl is None:
        return
    k = _run_keys(project, env, business_date, batch_id)
    env_key = f"PIPE#{project}#{env}"
    now = datetime.now(timezone.utc).isoformat()
    layer_doc = {
        "status": "FAILED",
        "updated_at": now,
        "script": script,
        "error": error[:2000],
    }
    tbl.update_item(
        Key=k,
        UpdateExpression="SET env_key = :ek, business_date = :bd, updated_at = :ua, layers.#lr = :ldoc",
        ExpressionAttributeNames={"#lr": target},
        ExpressionAttributeValues={
            ":ek": env_key,
            ":bd": business_date,
            ":ua": now,
            ":ldoc": layer_doc,
        },
    )


def require_silver_layer_succeeded(
    *,
    project: str,
    env: str,
    business_date: str,
    batch_id: str,
) -> None:
    if (os.environ.get("PIPELINE_SKIP_LAYER_CHECK") or "").lower() in ("1", "true", "yes"):
        return
    tbl = _table()
    if tbl is None:
        return
    k = _run_keys(project, env, business_date, batch_id)
    resp = tbl.get_item(Key=k)
    item = resp.get("Item") or {}
    layers = item.get("layers") or {}
    if _layer_status_ok(layers, LAYER_LAKE_STANDARDIZED_TO_SILVER):
        return
    raise RuntimeError(
        f"Capa anterior {LAYER_LAKE_STANDARDIZED_TO_SILVER!r} no OK para pk={k['pk']} sk={k['sk']}: "
        "se requiere SUCCEEDED antes de COPY Redshift."
    )


def handler(event, context):
    """Invocación directa: ``{"action": "...", ...}`` (payload según acción)."""
    if not isinstance(event, dict):
        raise ValueError("event debe ser objeto JSON")
    action = (event.get("action") or "").strip()
    if not action:
        raise ValueError("action requerido")

    if action == "validate_silver_s3_for_copy":
        validate_silver_s3_for_copy(
            business_date=str(event["business_date"]),
            silver_bucket=str(event["silver_bucket"]),
            art_bucket=str(event["art_bucket"]),
            registry_key=str(
                event.get("registry_key")
                or os.environ.get("REDSHIFT_REGISTRY_KEY", "redshift/contracts/registry.input.json")
            ),
            contracts_root=str(
                event.get("contracts_root")
                or os.environ.get("REDSHIFT_CONTRACTS_ROOT", "redshift/contracts")
            ),
        )
        return {"ok": True}

    if action == "require_previous_layer_for_redshift_script":
        require_previous_layer_for_redshift_script(
            script=str(event["script"]),
            project=str(event["project"]),
            env=str(event["env"]),
            business_date=str(event["business_date"]),
            batch_id=str(event["batch_id"]),
        )
        return {"ok": True}

    if action == "record_redshift_layer":
        record_redshift_layer(
            project=str(event["project"]),
            env=str(event["env"]),
            business_date=str(event["business_date"]),
            batch_id=str(event["batch_id"]),
            script=str(event["script"]),
            result_summary=event.get("result_summary") or {},
        )
        return {"ok": True}

    if action == "record_redshift_layer_failed":
        record_redshift_layer_failed(
            project=str(event["project"]),
            env=str(event["env"]),
            business_date=str(event["business_date"]),
            batch_id=str(event["batch_id"]),
            script=str(event["script"]),
            error=str(event.get("error") or ""),
        )
        return {"ok": True}

    raise ValueError(f"action desconocida: {action!r}")
