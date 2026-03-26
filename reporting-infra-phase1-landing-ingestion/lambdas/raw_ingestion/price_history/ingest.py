"""Fetch API price_history y escritura CSV en S3 RAW (solo validated/ o rejected/)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3

from lib.secrets import get_bearer_token
from lib.validate_contract import validate_price_history_csv

_ROOT = Path(__file__).resolve().parent


def _load_config(environment: str) -> dict[str, Any]:
    path = _ROOT / "config" / f"{environment}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Config no encontrada: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def fetch(endpoint: str, token: str) -> str:
    req = Request(
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {endpoint}: {e.read().decode('utf-8', errors='replace')}") from e
    except URLError as e:
        raise RuntimeError(f"Error de red {endpoint}: {e}") from e


def write_csv_payload(
    s3_client,
    bucket: str,
    raw_prefix: str,
    payload: str,
    batch_id: str,
    *,
    lane: str,
) -> str:
    now = datetime.now(timezone.utc)
    key = (
        f"{lane}/{raw_prefix}/ingestion_date={now.date()}/"
        f"ingestion_hour={now.hour:02d}/batch_id={batch_id}.csv"
    )
    s3_client.put_object(Bucket=bucket, Key=key, Body=payload.encode("utf-8"))
    return key


def run(
    *,
    environment: str | None = None,
    raw_bucket: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    env = environment or os.environ.get("ENVIRONMENT", "dev")
    cfg = _load_config(env)
    bucket = (raw_bucket or os.environ.get("RAW_BUCKET") or "").strip() or (
        cfg.get("raw_bucket") or ""
    ).strip()
    if not bucket:
        raise ValueError("Definir RAW_BUCKET en Lambda o raw_bucket en config JSON")

    raw_prefix = (cfg.get("raw_prefix") or "price_history").strip().strip("/")
    secret_id = cfg.get("api_secret_name")
    endpoint = cfg.get("api_endpoint")
    if not secret_id or not endpoint:
        raise ValueError("api_secret_name y api_endpoint requeridos en config")

    token = get_bearer_token(secret_id)
    text = fetch(endpoint, token)
    s3 = boto3.client("s3")
    bid = batch_id or os.environ.get("BATCH_ID") or "manual"

    ok, err = validate_price_history_csv(text)
    if ok:
        lane = "validated"
        key = write_csv_payload(s3, bucket, raw_prefix, text, bid, lane=lane)
    else:
        lane = "rejected"
        key = write_csv_payload(s3, bucket, raw_prefix, text, bid, lane=lane)
        print(
            f"[INGEST_REJECTED] table=price_history bucket={bucket} key={key} reason={err}",
            flush=True,
        )

    now = datetime.now(timezone.utc)
    bd = str(now.date())
    return {
        "ok": True,
        "validated": ok,
        "validation_error": None if ok else err,
        "table": "price_history",
        "s3_key": key,
        "bucket": bucket,
        "lane": lane,
        "job_name": cfg.get("job_name"),
        "business_date": bd,
    }
