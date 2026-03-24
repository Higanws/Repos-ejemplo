"""
Validación de contratos de entrada (registry + JSON en artefactos) para jobs Glue.
Solo se usa dentro de este repositorio (glue-data-lake/jobs).
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any, Callable

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")


def _load_json(bucket: str, key: str) -> dict[str, Any]:
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return json.loads(body)


def _first_object_key(bucket: str, prefix: str) -> str | None:
    r = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=50)
    for obj in r.get("Contents") or []:
        k = obj.get("Key") or ""
        if k.endswith("/"):
            continue
        return k
    return None


def _prefix_has_parquet(bucket: str, prefix: str) -> bool:
    r = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=80)
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

    obj = s3.get_object(Bucket=data_bucket, Key=key)
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


def validate_glue_job_inputs_from_registry(
    *,
    job_id: str,
    art_bucket: str,
    registry_key: str,
    contracts_root: str,
    data_bucket: str,
    path_for_dataset: Callable[[str], str],
) -> None:
    """
    Valida contratos contra objetos en S3.

    `name` en el registry es el **identificador de dataset** (segmento de prefijo S3:
    p.ej. trade_event, price_history). No implica tabla Glue en RAW; RAW son archivos
    crudos bajo validated/<dataset>/.
    """
    reg = _load_json(art_bucket, registry_key)
    job = next((j for j in reg.get("jobs", []) if j.get("id") == job_id), None)
    if not job:
        raise RuntimeError(f"registry: job {job_id!r} no encontrado")

    # input_datasets preferido; input_tables alias retrocompatible
    inputs = job.get("input_datasets") or job.get("input_tables") or []
    for t in inputs:
        name = (t.get("name") or "").strip()
        cr = (t.get("input_contract") or "").strip()
        if not name or not cr:
            continue
        prefix = path_for_dataset(name)
        logger.info("contract_check job=%s dataset=%s prefix=%s", job_id, name, prefix)
        _validate_one_input(
            data_bucket=data_bucket,
            prefix=prefix,
            art_bucket=art_bucket,
            contract_rel=cr,
            contracts_root=contracts_root,
        )
