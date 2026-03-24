"""
Job Glue (capa standardized -> silver S3): datasets en orden de glue-sql/config/glue_pipeline.json.

Lee Parquet bajo standardized/<dataset>/; los identificadores son prefijos S3 / nombres de dataset, no tablas RAW.

Transformaciones: sqls/standardized_to_silver/<dataset>_standardized_to_silver.sql.

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

STD_BASE = "s3://__STANDARDIZED_BUCKET__"
SILVER_BASE = "s3://__SILVER_BUCKET__"

LAYER = "standardized_to_silver"
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
    data["dataset_order"] = order
    return data


def _sql_file(table_id: str) -> str:
    return f"{table_id}_standardized_to_silver.sql"


def _load_sql(artifacts_bucket: str, sql_prefix: str, table_id: str) -> str:
    key = f"{sql_prefix}/{LAYER}/{_sql_file(table_id)}"
    return _s3.get_object(Bucket=artifacts_bucket, Key=key)["Body"].read().decode("utf-8")


def _write_silver(spark, df, target_path: str) -> None:
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    (
        df.write.mode("overwrite")
        .partitionBy("load_date")
        .parquet(target_path)
    )


def _pipeline(cfg: dict) -> list[dict]:
    return [
        {
            "id": tid,
            "source_path": f"{STD_BASE}/{tid}/",
            "target_path": f"{SILVER_BASE}/{tid}/",
        }
        for tid in cfg["dataset_order"]
    ]


def run(
    spark,
    artifacts_bucket: str,
    glue_sql_prefix: str,
    pipeline_config_key: str,
) -> None:
    cfg = _load_pipeline_config(artifacts_bucket, pipeline_config_key)
    for step in _pipeline(cfg):
        tid = step["id"]
        t0 = time.perf_counter()
        bkt, pfx = _parse_s3_uri(step["source_path"])
        if not _s3_prefix_has_objects(bkt, pfx):
            logger.info(
                "[standardized_to_silver] SKIP dataset=%s motivo=sin_parquet_en_s3 s3://%s/%s",
                tid,
                bkt,
                pfx,
            )
            continue
        try:
            df_in = spark.read.option("recursiveFileLookup", "true").parquet(
                step["source_path"]
            )
            df_in.createOrReplaceTempView("src")
            sql_text = _load_sql(artifacts_bucket, glue_sql_prefix, tid)
            df_out = spark.sql(sql_text)
            _write_silver(spark, df_out, step["target_path"])
        except Exception as e:
            logger.error(
                "[standardized_to_silver] ERROR dataset=%s: %s\n%s",
                tid,
                e,
                traceback.format_exc(),
            )
            raise
        elapsed = time.perf_counter() - t0
        logger.info(
            "[standardized_to_silver] OK dataset=%s duration_s=%.2f",
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
        LAYER_LAKE_STANDARDIZED_TO_SILVER,
        _argv_opt,
        require_previous_layer_succeeded_for_glue,
    )

    require_previous_layer_succeeded_for_glue(
        current_layer=LAYER_LAKE_STANDARDIZED_TO_SILVER,
        argv=sys.argv,
    )

    args = getResolvedOptions(
        sys.argv,
        ["JOB_NAME", "ARTIFACTS_BUCKET", "GLUE_SQL_S3_PREFIX", "GLUE_PIPELINE_CONFIG_KEY"],
    )

    artifacts = args["ARTIFACTS_BUCKET"]
    registry_key = _argv_opt(sys.argv, "GLUE_REGISTRY_KEY") or "glue-data-lake/contracts/registry.input.json"
    contracts_root = _argv_opt(sys.argv, "GLUE_CONTRACTS_ROOT") or "glue-data-lake/contracts"
    std_bucket, _ = _parse_s3_uri(STD_BASE)
    skip_contract = (_argv_opt(sys.argv, "PIPELINE_SKIP_CONTRACT_CHECK") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not skip_contract:
        validate_glue_job_inputs_from_registry(
            job_id="standardized_to_silver",
            art_bucket=artifacts,
            registry_key=registry_key,
            contracts_root=contracts_root,
            data_bucket=std_bucket,
            path_for_dataset=lambda name: f"{name}/",
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
        pipeline_config_key=args["GLUE_PIPELINE_CONFIG_KEY"],
    )
    job.commit()
    record_layer_succeeded_and_emit_next(
        completed_layer=LAYER_LAKE_STANDARDIZED_TO_SILVER,
        job_name=args["JOB_NAME"],
        argv=sys.argv,
    )
