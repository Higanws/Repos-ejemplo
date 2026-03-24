"""
Ejecuta SQL en Redshift Serverless (Data API).
Lee el script desde s3://{ARTIFACTS_BUCKET}/sql/{script}.

Logs → CloudWatch (grupo de la Lambda).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
rdata = boto3.client("redshift-data")
_lambda_client = None

BUCKET = os.environ["ARTIFACTS_BUCKET"]
WORKGROUP = os.environ["REDSHIFT_WORKGROUP"]
DATABASE = os.environ["REDSHIFT_DATABASE"]
SECRET_ARN = os.environ["REDSHIFT_SECRET_ARN"]
SILVER_BUCKET = os.environ["SILVER_BUCKET"]
ROLE_ARN = os.environ["REDSHIFT_IAM_ROLE_ARN"]

_REDSHIFT_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)",
    re.IGNORECASE | re.DOTALL,
)
_SAFE_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


def _payload(event):
    if isinstance(event, dict) and "Payload" in event:
        return event["Payload"]
    return event if isinstance(event, dict) else {}


def _load_sql(script: str) -> str:
    key = f"sql/{script}"
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return obj["Body"].read().decode("utf-8")


def _strip_sql_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _parse_create_table_target(sql: str) -> tuple[str, str] | None:
    cleaned = _strip_sql_comments(sql)
    m = _REDSHIFT_CREATE.search(cleaned)
    if not m:
        return None
    schema, table = m.group(1).lower(), m.group(2).lower()
    if not _SAFE_IDENT.match(schema) or not _SAFE_IDENT.match(table):
        return None
    return schema, table


def _is_redshift_ddl_script(script_key: str) -> bool:
    return script_key.startswith("silver/") or script_key.startswith("gold/")


def _sql_execution_units(body: str, script_key: str) -> list[str]:
    stripped = body.strip()
    if not stripped:
        return []
    if stripped.upper().startswith("BEGIN"):
        return [stripped]
    if _is_redshift_ddl_script(script_key):
        parts = re.split(r";\s*(?=\n\s*CREATE\b)", stripped, flags=re.IGNORECASE | re.DOTALL)
        units: list[str] = []
        for p in parts:
            p = p.strip()
            if not p or p.lstrip().startswith("--"):
                continue
            if not p.endswith(";"):
                p += ";"
            units.append(p)
        return units if units else [stripped]
    return [stripped]


def _execute_and_wait(sql: str) -> str:
    rid = rdata.execute_statement(
        WorkgroupName=WORKGROUP,
        Database=DATABASE,
        SecretArn=SECRET_ARN,
        Sql=sql,
    )["Id"]
    while True:
        desc = rdata.describe_statement(Id=rid)
        status = desc["Status"]
        if status in ("FINISHED", "FAILED", "ABORTED"):
            break
        time.sleep(1.5)
    if status != "FINISHED":
        raise RuntimeError(desc.get("Error", status))
    return rid


def _select_returns_rows(statement_id: str) -> bool:
    desc = rdata.describe_statement(Id=statement_id)
    if not desc.get("HasResultSet"):
        return False
    res = rdata.get_statement_result(Id=statement_id)
    return int(res.get("TotalNumRows", 0) or 0) > 0


def _redshift_table_exists(schema: str, table: str) -> bool:
    sql = (
        f"SELECT 1 FROM information_schema.tables "
        f"WHERE table_schema = '{schema}' AND table_name = '{table}' LIMIT 1"
    )
    rid = _execute_and_wait(sql)
    return _select_returns_rows(rid)


def _apply_placeholders(body: str, payload: dict) -> str:
    load_mode = payload.get("load_mode", "incremental")
    load_date = payload.get("load_date", "")
    session_date = payload.get("session_date", "")

    script_key = payload.get("script", "")
    if "copy_s3_to_silver" in script_key or "copy_to_silver" in script_key:
        if load_mode == "full":
            te = f"s3://{SILVER_BUCKET}/trade_event/"
            ph = f"s3://{SILVER_BUCKET}/price_history/"
        else:
            te = f"s3://{SILVER_BUCKET}/trade_event/load_date={load_date}/"
            ph = f"s3://{SILVER_BUCKET}/price_history/load_date={load_date}/"
        body = body.replace("__S3_TRADE_EVENT_PATH__", te)
        body = body.replace("__S3_PRICE_HISTORY_PATH__", ph)

    body = body.replace("__REDSHIFT_IAM_ROLE_ARN__", ROLE_ARN)
    body = body.replace("__LOAD_MODE__", f"'{load_mode}'")
    body = body.replace("__SESSION_DATE__", f"'{session_date}'")
    body = body.replace("__LOAD_DATE__", f"'{load_date}'")
    body = body.replace(":load_mode", f"'{load_mode}'")
    body = body.replace(":session_date", f"'{session_date}'")
    body = body.replace(":load_date", f"'{load_date}'")
    return body


def handler(event, context):
    payload = _payload(event)
    script = payload.get("script")
    if not script:
        raise ValueError("Payload.script requerido")

    logger.info("redshift_sql_start script=%s", script)

    _maybe_require_previous_layer(payload)
    _maybe_validate_silver_s3_contracts(payload, script)

    body = _load_sql(script)
    body = _apply_placeholders(body, {**payload, "script": script})

    force_ddl = payload.get("force_ddl") is True
    if not force_ddl and _is_redshift_ddl_script(script):
        parsed = _parse_create_table_target(body)
        if parsed:
            sch, tbl = parsed
            if _redshift_table_exists(sch, tbl):
                logger.info(
                    "redshift_sql_skipped reason=table_already_exists schema=%s table=%s",
                    sch,
                    tbl,
                )
                return {
                    "skipped": True,
                    "reason": "table_already_exists",
                    "schema": sch,
                    "table": tbl,
                    "script": script,
                }

    last_rid: str | None = None
    try:
        for unit in _sql_execution_units(body, script):
            last_rid = _execute_and_wait(unit)
    except Exception as ex:
        logger.exception("redshift_sql_failed script=%s", script)
        _maybe_record_redshift_failed(payload, script, str(ex))
        raise

    out = {"id": last_rid, "status": "FINISHED"}
    _maybe_record_redshift_ok(payload, script, out)
    logger.info("redshift_sql_ok script=%s statement_id=%s", script, last_rid)
    return out


def _lambda_svc():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client


def _invoke_pipeline_runs(payload: dict) -> None:
    """Invoca la Lambda ``pipeline_runs_dynamo`` (responsabilidad única: Dynamo + contratos S3)."""
    fn = (os.environ.get("PIPELINE_RUNS_LAMBDA_NAME") or "").strip()
    if not fn:
        return
    resp = _lambda_svc().invoke(
        FunctionName=fn,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload, default=str).encode("utf-8"),
    )
    pl = resp.get("Payload")
    body = pl.read().decode("utf-8") if pl else "{}"
    if resp.get("FunctionError"):
        try:
            err = json.loads(body)
            msg = err.get("errorMessage") or err.get("errorType") or body
        except json.JSONDecodeError:
            msg = body
        raise RuntimeError(str(msg))
    try:
        out = json.loads(body) if body else {}
    except json.JSONDecodeError:
        out = {}
    if isinstance(out, dict) and out.get("error"):
        raise RuntimeError(str(out["error"]))


def _run_context(payload: dict):
    bd = (payload.get("load_date") or payload.get("session_date") or "").strip()
    if not bd:
        return None
    bid = (payload.get("batch_id") or "default").strip() or "default"
    return {
        "project": os.environ.get("PROJECT", "reporting"),
        "env": os.environ.get("ENVIRONMENT", "dev"),
        "business_date": bd,
        "batch_id": bid,
    }


def _maybe_validate_silver_s3_contracts(payload: dict, script: str) -> None:
    """Antes del SQL: contratos de silver S3 para scripts COPY (Lambda pipeline_runs_dynamo)."""
    if (os.environ.get("PIPELINE_SKIP_CONTRACT_CHECK") or "").lower() in ("1", "true", "yes"):
        return
    s = script.replace("\\", "/").lower()
    if "copy_s3_to_silver" not in s:
        return
    ctx = _run_context(payload)
    if not ctx:
        return
    _invoke_pipeline_runs(
        {
            "action": "validate_silver_s3_for_copy",
            "business_date": ctx["business_date"],
            "silver_bucket": SILVER_BUCKET,
            "art_bucket": BUCKET,
            "registry_key": os.environ.get("REDSHIFT_REGISTRY_KEY", "redshift/contracts/registry.input.json"),
            "contracts_root": os.environ.get("REDSHIFT_CONTRACTS_ROOT", "redshift/contracts"),
        }
    )


def _maybe_require_previous_layer(payload: dict) -> None:
    if (os.environ.get("PIPELINE_SKIP_LAYER_CHECK") or "").lower() in ("1", "true", "yes"):
        return
    ctx = _run_context(payload)
    if not ctx:
        return
    script = (payload.get("script") or "").strip()
    if not script:
        return
    _invoke_pipeline_runs(
        {
            "action": "require_previous_layer_for_redshift_script",
            "script": script,
            "project": ctx["project"],
            "env": ctx["env"],
            "business_date": ctx["business_date"],
            "batch_id": ctx["batch_id"],
        }
    )


def _maybe_record_redshift_ok(payload: dict, script: str, result_summary: dict) -> None:
    ctx = _run_context(payload)
    if not ctx:
        return
    _invoke_pipeline_runs(
        {
            "action": "record_redshift_layer",
            "project": ctx["project"],
            "env": ctx["env"],
            "business_date": ctx["business_date"],
            "batch_id": ctx["batch_id"],
            "script": script,
            "result_summary": result_summary,
        }
    )


def _maybe_record_redshift_failed(payload: dict, script: str, error: str) -> None:
    ctx = _run_context(payload)
    if not ctx:
        return
    _invoke_pipeline_runs(
        {
            "action": "record_redshift_layer_failed",
            "project": ctx["project"],
            "env": ctx["env"],
            "business_date": ctx["business_date"],
            "batch_id": ctx["batch_id"],
            "script": script,
            "error": error,
        }
    )
