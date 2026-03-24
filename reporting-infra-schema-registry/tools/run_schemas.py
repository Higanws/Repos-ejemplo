from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
MANIFEST = SCHEMAS / "manifest.json"

RE_GLUE_EXTERNAL = re.compile(
    r"CREATE\s+EXTERNAL\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)",
    re.IGNORECASE | re.DOTALL,
)
RE_RS_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)",
    re.IGNORECASE | re.DOTALL,
)


def _read_manifest() -> dict:
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
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower()


def _parse_redshift_table(sql: str):
    m = RE_RS_CREATE.search(_strip_sql_comments(sql))
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower()


def _glue_table_exists(glue, db: str, tbl: str) -> bool:
    try:
        glue.get_table(DatabaseName=db, Name=tbl)
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


def _run_redshift(redshift_data, sql: str, workgroup: str, database: str, secret_arn: str) -> str:
    sid = redshift_data.execute_statement(
        WorkgroupName=workgroup,
        Database=database,
        SecretArn=secret_arn,
        Sql=sql,
    )["Id"]
    while True:
        d = redshift_data.describe_statement(Id=sid)
        st = d["Status"]
        if st in ("FINISHED", "FAILED", "ABORTED"):
            break
        time.sleep(1.5)
    if st != "FINISHED":
        raise RuntimeError(f"Redshift falló statement_id={sid}: {d.get('Error', st)}")
    return sid


def _redshift_table_exists(redshift_data, workgroup: str, database: str, secret_arn: str, schema: str, table: str) -> bool:
    check_sql = (
        "SELECT 1 FROM information_schema.tables "
        f"WHERE table_schema = '{schema}' AND table_name = '{table}' LIMIT 1"
    )
    sid = _run_redshift(redshift_data, check_sql, workgroup, database, secret_arn)
    desc = redshift_data.describe_statement(Id=sid)
    if not desc.get("HasResultSet"):
        return False
    rs = redshift_data.get_statement_result(Id=sid)
    return int(rs.get("TotalNumRows", 0) or 0) > 0


def run_glue(args, manifest: dict) -> None:
    required = [
        args.standardized_bucket,
        args.silver_bucket,
        args.athena_workgroup,
        args.athena_output_s3,
    ]
    if any(not x for x in required):
        raise ValueError("Faltan parámetros Glue: standardized/silver bucket + athena workgroup/output.")

    session = boto3.session.Session(region_name=args.aws_region)
    glue = session.client("glue")
    athena = session.client("athena")

    for rel in manifest["glue"]:
        sql = (
            _load_sql(rel)
            .replace("{{standardized_bucket}}", args.standardized_bucket)
            .replace("{{silver_bucket}}", args.silver_bucket)
        )
        parsed = _parse_glue_table(sql)
        if args.dry_run:
            print(f"[DRY-RUN][GLUE] {rel}")
            continue
        if parsed and not args.force_ddl and _glue_table_exists(glue, parsed[0], parsed[1]):
            print(f"[SKIP][GLUE] {rel} tabla ya existe {parsed[0]}.{parsed[1]}")
            continue
        qid = _run_athena(athena, sql, args.athena_workgroup, args.athena_output_s3)
        print(f"[OK][GLUE] {rel} query_id={qid}")


def run_redshift(args, manifest: dict) -> None:
    required = [args.redshift_workgroup, args.redshift_database, args.redshift_secret_arn]
    if any(not x for x in required):
        raise ValueError("Faltan parámetros Redshift: workgroup/database/secret_arn.")

    session = boto3.session.Session(region_name=args.aws_region)
    rdata = session.client("redshift-data")

    for rel in manifest["redshift"]:
        sql = _load_sql(rel)
        parsed = _parse_redshift_table(sql)
        if args.dry_run:
            print(f"[DRY-RUN][REDSHIFT] {rel}")
            continue
        if (
            parsed
            and not args.force_ddl
            and _redshift_table_exists(
                rdata,
                args.redshift_workgroup,
                args.redshift_database,
                args.redshift_secret_arn,
                parsed[0],
                parsed[1],
            )
        ):
            print(f"[SKIP][REDSHIFT] {rel} tabla ya existe {parsed[0]}.{parsed[1]}")
            continue
        sid = _run_redshift(
            rdata,
            sql,
            args.redshift_workgroup,
            args.redshift_database,
            args.redshift_secret_arn,
        )
        print(f"[OK][REDSHIFT] {rel} statement_id={sid}")


def parse_args(argv: list[str]):
    p = argparse.ArgumentParser(description="Ejecutor on-demand de schemas Glue/Athena y Redshift.")
    p.add_argument("--target", choices=["glue", "redshift", "all"], required=True)
    p.add_argument("--aws-region", required=True)
    p.add_argument("--force-ddl", action="store_true")
    p.add_argument("--dry-run", action="store_true")

    p.add_argument("--standardized-bucket")
    p.add_argument("--silver-bucket")
    p.add_argument("--athena-workgroup")
    p.add_argument("--athena-output-s3")

    p.add_argument("--redshift-workgroup")
    p.add_argument("--redshift-database")
    p.add_argument("--redshift-secret-arn")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    manifest = _read_manifest()
    if args.target in ("glue", "all"):
        run_glue(args, manifest)
    if args.target in ("redshift", "all"):
        run_redshift(args, manifest)
    print("Ejecución finalizada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
