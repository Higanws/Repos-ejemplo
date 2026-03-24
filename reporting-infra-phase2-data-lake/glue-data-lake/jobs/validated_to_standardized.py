"""
Job Glue (capa validated RAW -> standardized): recorre datasets en glue-sql/config/glue_pipeline.json.

RAW no son tablas Glue: son archivos crudos (JSON/CSV) bajo s3://<raw_bucket>/validated/<dataset>/.
Los nombres trade_event / price_history son identificadores de dataset y prefijo S3, no tablas en catálogo.

Transformaciones: sqls/raw_to_standardized/<dataset>_raw_to_standardized.sql (artefactos S3).

Salida de logging → CloudWatch Logs del job Glue (/aws-glue/jobs/...).
"""
from __future__ import annotations

import json
import logging
import time
import traceback

import boto3

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger.setLevel(logging.INFO)

RAW_BASE = "s3://__RAW_BUCKET__"
STD_BASE = "s3://__STANDARDIZED_BUCKET__"

# Carpeta de SQL en artifacts (sin renombrar artefactos existentes).
LAYER = "raw_to_standardized"
_s3 = boto3.client("s3")


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"URI S3 invalida: {uri}")
    rest = uri[5:]
    slash = rest.find("/")
    if slash < 0:
        return rest, ""
    bucket, key = rest[:slash], rest[slash + 1 :].lstrip("/")
    if key and not key.endswith("/"):
        key = key + "/"
    return bucket, key


def _s3_prefix_has_objects(bucket: str, prefix: str) -> bool:
    resp = _s3.list_objects_v2(Bucket=bucket, Prefix=prefix or "", MaxKeys=1)
    return int(resp.get("KeyCount") or 0) > 0


def _load_pipeline_config(artifacts_bucket: str, config_key: str) -> dict:
    raw = _s3.get_object(Bucket=artifacts_bucket, Key=config_key)["Body"].read().decode("utf-8")
    data = json.loads(raw)
    order = data.get("dataset_order") or data.get("table_order")
    formats = data.get("raw_formats")
    if not isinstance(order, list) or not order:
        raise ValueError(
            "glue_pipeline.json: dataset_order (o table_order) debe ser lista no vacía"
        )
    if not isinstance(formats, dict):
        raise ValueError("glue_pipeline.json: raw_formats debe ser objeto")
    if set(formats.keys()) != set(order):
        raise ValueError(
            "glue_pipeline.json: claves de raw_formats deben coincidir exactamente con dataset_order"
        )
    sub = data.get("raw_subprefix", "validated")
    if not isinstance(sub, str) or not sub.strip():
        raise ValueError("glue_pipeline.json: raw_subprefix debe ser string no vacío")
    data["raw_subprefix"] = sub.strip().rstrip("/")
    data["dataset_order"] = order
    for tid in order:
        spec = formats[tid]
        fmt = spec.get("format")
        if fmt not in ("json", "csv"):
            raise ValueError(f"Dataset {tid}: format debe ser json o csv, no {fmt!r}")
    return data


def _sql_file(table_id: str) -> str:
    return f"{table_id}_raw_to_standardized.sql"


def _load_sql(artifacts_bucket: str, sql_prefix: str, table_id: str) -> str:
    key = f"{sql_prefix}/{LAYER}/{_sql_file(table_id)}"
    return _s3.get_object(Bucket=artifacts_bucket, Key=key)["Body"].read().decode("utf-8")


def _read_json(spark, path: str):
    return (
        spark.read.option("multiLine", True)
        .option("recursiveFileLookup", "true")
        .json(path)
    )


def _read_csv(spark, path: str, sep: str):
    return (
        spark.read.option("header", True)
        .option("sep", sep)
        .option("recursiveFileLookup", "true")
        .csv(path)
    )


def _maybe_flatten_payload(df):
    cols = df.columns
    if "payload" in cols and "external_event_id" not in cols:
        return df.select("payload.*")
    return df


def _write_standardized(spark, df, target_path: str) -> None:
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    (
        df.write.mode("overwrite")
        .partitionBy("load_date")
        .parquet(target_path)
    )


def _pipeline(cfg: dict, price_history_sep: str) -> list[dict]:
    sub = cfg["raw_subprefix"]
    steps: list[dict] = []
    for tid in cfg["dataset_order"]:
        spec = cfg["raw_formats"][tid]
        fmt = spec["format"]
        step: dict = {
            "id": tid,
            "raw_path": f"{RAW_BASE}/{sub}/{tid}/",
            "target_path": f"{STD_BASE}/{tid}/",
            "format": fmt,
        }
        if fmt == "csv":
            step["sep"] = price_history_sep
        if spec.get("flatten_payload"):
            step["flatten_payload"] = True
        steps.append(step)
    return steps


def run(
    spark,
    artifacts_bucket: str,
    glue_sql_prefix: str,
    price_history_sep: str,
    pipeline_config_key: str,
) -> None:
    cfg = _load_pipeline_config(artifacts_bucket, pipeline_config_key)
    for step in _pipeline(cfg, price_history_sep):
        tid = step["id"]
        t0 = time.perf_counter()
        bkt, pfx = _parse_s3_uri(step["raw_path"])
        if not _s3_prefix_has_objects(bkt, pfx):
            logger.info(
                "[validated_to_standardized] SKIP dataset=%s motivo=sin_objetos_en_s3 s3://%s/%s",
                tid,
                bkt,
                pfx,
            )
            continue
        try:
            if step["format"] == "json":
                df_in = _read_json(spark, step["raw_path"])
                if step.get("flatten_payload"):
                    df_in = _maybe_flatten_payload(df_in)
            else:
                df_in = _read_csv(spark, step["raw_path"], step["sep"])
            df_in.createOrReplaceTempView("src")
            sql_text = _load_sql(artifacts_bucket, glue_sql_prefix, tid)
            df_out = spark.sql(sql_text)
            _write_standardized(spark, df_out, step["target_path"])
        except Exception as e:
            logger.error(
                "[validated_to_standardized] ERROR dataset=%s: %s\n%s",
                tid,
                e,
                traceback.format_exc(),
            )
            raise
        elapsed = time.perf_counter() - t0
        logger.info(
            "[validated_to_standardized] OK dataset=%s duration_s=%.2f",
            tid,
            elapsed,
        )


if __name__ == "__main__":
    import sys

    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext

    from pipeline_contract_validate import validate_glue_job_inputs_from_registry
    from pipeline_layer_finish import record_layer_succeeded_and_emit_next
    from pipeline_layer_gate import (
        LAYER_LAKE_VALIDATED_TO_STANDARDIZED,
        _argv_opt,
        require_previous_layer_succeeded_for_glue,
    )

    require_previous_layer_succeeded_for_glue(
        current_layer=LAYER_LAKE_VALIDATED_TO_STANDARDIZED,
        argv=sys.argv,
    )

    args = getResolvedOptions(
        sys.argv,
        [
            "JOB_NAME",
            "PRICE_HISTORY_SEP",
            "ARTIFACTS_BUCKET",
            "GLUE_SQL_S3_PREFIX",
            "GLUE_PIPELINE_CONFIG_KEY",
        ],
    )
    sep = args["PRICE_HISTORY_SEP"]
    if sep in ("\\t", "tab"):
        sep = "\t"

    artifacts = args["ARTIFACTS_BUCKET"]
    registry_key = _argv_opt(sys.argv, "GLUE_REGISTRY_KEY") or "glue-data-lake/contracts/registry.input.json"
    contracts_root = _argv_opt(sys.argv, "GLUE_CONTRACTS_ROOT") or "glue-data-lake/contracts"
    raw_bucket, _ = _parse_s3_uri(RAW_BASE)
    skip_contract = (_argv_opt(sys.argv, "PIPELINE_SKIP_CONTRACT_CHECK") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not skip_contract:
        validate_glue_job_inputs_from_registry(
            job_id="validated_to_standardized",
            art_bucket=artifacts,
            registry_key=registry_key,
            contracts_root=contracts_root,
            data_bucket=raw_bucket,
            path_for_dataset=lambda name: f"validated/{name}/",
        )

    sc = SparkContext()
    glue_context = GlueContext(sc)
    spark_session = glue_context.spark_session
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)
    run(
        spark_session,
        artifacts_bucket=artifacts,
        glue_sql_prefix=args["GLUE_SQL_S3_PREFIX"].rstrip("/"),
        price_history_sep=sep,
        pipeline_config_key=args["GLUE_PIPELINE_CONFIG_KEY"],
    )
    job.commit()
    record_layer_succeeded_and_emit_next(
        completed_layer=LAYER_LAKE_VALIDATED_TO_STANDARDIZED,
        job_name=args["JOB_NAME"],
        argv=sys.argv,
    )
