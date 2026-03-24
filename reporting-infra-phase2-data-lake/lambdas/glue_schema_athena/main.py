"""
Aplica DDL de Glue (Hive) via Athena sobre el catalogo AwsDataCatalog.
Scripts en s3://{ARTIFACTS_BUCKET}/glue-ddl/{script}
Sustituye {{raw_bucket}}, {{standardized_bucket}} y {{silver_bucket}}.

Si el script es CREATE EXTERNAL TABLE y la tabla ya existe en Glue Data Catalog,
omite Athena (salvo force_ddl=true en el payload).

Logs → CloudWatch (grupo de la Lambda).
"""
from __future__ import annotations

import logging
import os
import re
import time

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
athena = boto3.client("athena")
glue = boto3.client("glue")

BUCKET = os.environ["ARTIFACTS_BUCKET"]
RAW_BUCKET = os.environ["RAW_BUCKET"]
STANDARDIZED_BUCKET = os.environ["STANDARDIZED_BUCKET"]
SILVER_BUCKET = os.environ["SILVER_BUCKET"]
WORKGROUP = os.environ["ATHENA_WORKGROUP"]
OUTPUT_S3 = os.environ["ATHENA_OUTPUT_S3"]

_EXTERNAL_CREATE = re.compile(
    r"CREATE\s+EXTERNAL\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)",
    re.IGNORECASE | re.DOTALL,
)


def _payload(event):
    if isinstance(event, dict) and "Payload" in event:
        return event["Payload"]
    return event if isinstance(event, dict) else {}


def _strip_sql_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _parse_external_table(sql: str) -> tuple[str, str] | None:
    cleaned = _strip_sql_comments(sql)
    m = _EXTERNAL_CREATE.search(cleaned)
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower()


def _glue_table_exists(database: str, name: str) -> bool:
    try:
        glue.get_table(DatabaseName=database, Name=name)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("EntityNotFoundException", "GlueEntityNotFoundException"):
            return False
        raise


def handler(event, context):
    payload = _payload(event)
    script = payload.get("script")
    if not script:
        raise ValueError("Payload.script requerido")

    logger.info("glue_schema_athena_start script=%s", script)

    key = f"glue-ddl/{script}"
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    sql = (
        obj["Body"]
        .read()
        .decode("utf-8")
        .replace("{{raw_bucket}}", RAW_BUCKET)
        .replace("{{standardized_bucket}}", STANDARDIZED_BUCKET)
        .replace("{{silver_bucket}}", SILVER_BUCKET)
    )

    force_ddl = payload.get("force_ddl") is True
    if not force_ddl:
        parsed = _parse_external_table(sql)
        if parsed:
            db, tbl = parsed
            if _glue_table_exists(db, tbl):
                logger.info(
                    "glue_schema_athena_skipped reason=glue_table_already_exists db=%s table=%s",
                    db,
                    tbl,
                )
                return {
                    "skipped": True,
                    "reason": "glue_table_already_exists",
                    "database": db,
                    "name": tbl,
                    "script": script,
                }

    qid = athena.start_query_execution(
        QueryString=sql,
        WorkGroup=WORKGROUP,
        ResultConfiguration={"OutputLocation": OUTPUT_S3},
        QueryExecutionContext={"Catalog": "AwsDataCatalog"},
    )["QueryExecutionId"]

    while True:
        state = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1.5)

    if state != "SUCCEEDED":
        reason = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"].get(
            "StateChangeReason", state
        )
        logger.error(
            "glue_schema_athena_failed script=%s query_id=%s state=%s reason=%s",
            script,
            qid,
            state,
            reason,
        )
        raise RuntimeError(reason)

    logger.info("glue_schema_athena_ok script=%s query_id=%s", script, qid)
    return {"query_execution_id": qid, "state": state}
