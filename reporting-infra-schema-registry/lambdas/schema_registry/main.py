from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

RE_GLUE_EXTERNAL = re.compile(
    r"CREATE\s+EXTERNAL\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)",
    re.IGNORECASE | re.DOTALL,
)
RE_RS_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)",
    re.IGNORECASE | re.DOTALL,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
MANIFEST = SCHEMAS / "manifest.json"


def _load_manifest() -> dict[str, list[str]]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _load_sql(rel: str) -> str:
    p = SCHEMAS / rel
    if not p.is_file():
        raise FileNotFoundError(f"No existe schema: {p}")
    return p.read_text(encoding="utf-8")


def _strip_sql_comments(sql: str) -> str:
    out = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        out.append(line)
    return "\n".join(out)


def _parse_glue_table(sql: str):
    m = RE_GLUE_EXTERNAL.search(_strip_sql_comments(sql))
    return (m.group(1).lower(), m.group(2).lower()) if m else None


def _parse_redshift_table(sql: str):
    m = RE_RS_CREATE.search(_strip_sql_comments(sql))
    return (m.group(1).lower(), m.group(2).lower()) if m else None


def _glue_table_exists(glue, database: str, name: str) -> bool:
    try:
        glue.get_table(DatabaseName=database, Name=name)
        return True
    except ClientError as ex:
        code = ex.response.get("Error", {}).get("Code", "")
        if code in ("EntityNotFoundException", "GlueEntityNotFoundException"):
            return False
        raise


def _run_athena(athena, sql: str, workgroup: str, output_s3: str) -> str:
    qid = athena.start_query_execution(
        QueryString=sql,
        WorkGroup=workgroup,
        ResultConfiguration={"OutputLocation": output_s3},
        QueryExecutionContext={"Catalog": "AwsDataCatalog"},
    )["QueryExecutionId"]
    while True:
        ex = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        st = ex["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1.5)
    if st != "SUCCEEDED":
        reason = ex["Status"].get("StateChangeReason", st)
        raise RuntimeError(f"Athena falló query_id={qid}: {reason}")
    return qid


def _run_redshift(rdata, sql: str, workgroup: str, database: str, secret_arn: str) -> str:
    sid = rdata.execute_statement(
        WorkgroupName=workgroup,
        Database=database,
        SecretArn=secret_arn,
        Sql=sql,
    )["Id"]
    while True:
        d = rdata.describe_statement(Id=sid)
        st = d["Status"]
        if st in ("FINISHED", "FAILED", "ABORTED"):
            break
        time.sleep(1.5)
    if st != "FINISHED":
        raise RuntimeError(f"Redshift falló statement_id={sid}: {d.get('Error', st)}")
    return sid


def _redshift_table_exists(rdata, workgroup: str, database: str, secret_arn: str, schema: str, table: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables "
        f"WHERE table_schema = '{schema}' AND table_name = '{table}' LIMIT 1"
    )
    sid = _run_redshift(rdata, sql, workgroup, database, secret_arn)
    d = rdata.describe_statement(Id=sid)
    if not d.get("HasResultSet"):
        return False
    rs = rdata.get_statement_result(Id=sid)
    return int(rs.get("TotalNumRows", 0) or 0) > 0


def _run_glue(manifest: dict[str, list[str]], *, force_ddl: bool, dry_run: bool) -> list[dict[str, Any]]:
    standardized_bucket = os.environ["STANDARDIZED_BUCKET"]
    silver_bucket = os.environ["SILVER_BUCKET"]
    athena_workgroup = os.environ["ATHENA_WORKGROUP"]
    athena_output_s3 = os.environ["ATHENA_OUTPUT_S3"]

    glue = boto3.client("glue")
    athena = boto3.client("athena")
    out: list[dict[str, Any]] = []

    for rel in manifest["glue"]:
        sql = (
            _load_sql(rel)
            .replace("{{standardized_bucket}}", standardized_bucket)
            .replace("{{silver_bucket}}", silver_bucket)
        )
        item: dict[str, Any] = {"target": "glue", "script": rel}
        if dry_run:
            item["status"] = "DRY_RUN"
            out.append(item)
            continue
        parsed = _parse_glue_table(sql)
        if parsed and not force_ddl and _glue_table_exists(glue, parsed[0], parsed[1]):
            item["status"] = "SKIPPED_EXISTS"
            item["table"] = f"{parsed[0]}.{parsed[1]}"
            out.append(item)
            continue
        qid = _run_athena(athena, sql, athena_workgroup, athena_output_s3)
        item["status"] = "APPLIED"
        item["query_execution_id"] = qid
        out.append(item)
    return out


def _run_redshift(manifest: dict[str, list[str]], *, force_ddl: bool, dry_run: bool) -> list[dict[str, Any]]:
    workgroup = os.environ["REDSHIFT_WORKGROUP"]
    database = os.environ["REDSHIFT_DATABASE"]
    secret_arn = os.environ["REDSHIFT_SECRET_ARN"]
    rdata = boto3.client("redshift-data")
    out: list[dict[str, Any]] = []

    for rel in manifest["redshift"]:
        sql = _load_sql(rel)
        item: dict[str, Any] = {"target": "redshift", "script": rel}
        if dry_run:
            item["status"] = "DRY_RUN"
            out.append(item)
            continue
        parsed = _parse_redshift_table(sql)
        if (
            parsed
            and not force_ddl
            and _redshift_table_exists(rdata, workgroup, database, secret_arn, parsed[0], parsed[1])
        ):
            item["status"] = "SKIPPED_EXISTS"
            item["table"] = f"{parsed[0]}.{parsed[1]}"
            out.append(item)
            continue
        sid = _run_redshift(rdata, sql, workgroup, database, secret_arn)
        item["status"] = "APPLIED"
        item["statement_id"] = sid
        out.append(item)
    return out


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    event = event or {}
    target = str(event.get("target", "all")).strip().lower()
    if target not in ("all", "glue", "redshift"):
        raise ValueError("target debe ser all|glue|redshift")
    force_ddl = bool(event.get("force_ddl", False))
    dry_run = bool(event.get("dry_run", False))
    manifest = _load_manifest()

    result: dict[str, Any] = {"target": target, "force_ddl": force_ddl, "dry_run": dry_run}
    if target in ("all", "glue"):
        result["glue"] = _run_glue(manifest, force_ddl=force_ddl, dry_run=dry_run)
    if target in ("all", "redshift"):
        result["redshift"] = _run_redshift(manifest, force_ddl=force_ddl, dry_run=dry_run)
    return result
