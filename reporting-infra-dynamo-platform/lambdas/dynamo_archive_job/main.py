"""
Exporta ítems de pipeline_runs con business_date anterior al umbral de retención a S3 y los borra en DynamoDB.
Ejecutado por EventBridge (p. ej. lunes 00:00 UTC).

Logs → CloudWatch (grupo de la Lambda).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.types import TypeDeserializer

deser = TypeDeserializer()

TABLE = os.environ["TABLE_NAME"]
BUCKET = os.environ["ARCHIVE_BUCKET"]
ENV_KEY = os.environ["ENV_KEY"]
GSI_NAME = os.environ.get("GSI_NAME", "gsi_env_business_date")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "30"))

ddb = boto3.client("dynamodb")
s3 = boto3.client("s3")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _item_to_dict(item: dict) -> dict:
    return {k: deser.deserialize(v) for k, v in item.items()}


def handler(event, context):
    now = datetime.now(timezone.utc)
    cutoff_date = (now.date() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")

    archived = 0
    deleted = 0
    errors: list[str] = []

    kwargs = {
        "TableName": TABLE,
        "IndexName": GSI_NAME,
        "KeyConditionExpression": "env_key = :e AND business_date < :c",
        "ExpressionAttributeValues": {
            ":e": {"S": ENV_KEY},
            ":c": {"S": cutoff_date},
        },
    }

    while True:
        resp = ddb.query(**kwargs)
        for item in resp.get("Items", []):
            plain = _item_to_dict(item)
            pk = plain.get("pk", "")
            sk = plain.get("sk", "")
            bd = plain.get("business_date", "unknown")
            key_safe = f"{pk}__{sk}".replace("/", "_").replace("#", "_")[:512]
            s3_key = (
                f"dynamo-archive/{bd[:4]}/{bd[5:7]}/{bd[8:10]}/{key_safe}.json"
            )

            body = json.dumps(plain, default=str, ensure_ascii=False).encode("utf-8")

            try:
                s3.put_object(
                    Bucket=BUCKET,
                    Key=s3_key,
                    Body=body,
                    ContentType="application/json",
                )
            except Exception as ex:
                errors.append(f"s3_put:{pk}:{sk}:{ex}")
                continue

            try:
                ddb.delete_item(
                    TableName=TABLE,
                    Key={"pk": {"S": item["pk"]["S"]}, "sk": {"S": item["sk"]["S"]}},
                )
                archived += 1
                deleted += 1
            except Exception as ex:
                errors.append(f"ddb_delete:{pk}:{sk}:{ex}")

        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek

    if errors:
        logger.warning(
            "dynamo_archive_completed_with_errors count=%s sample=%s",
            len(errors),
            errors[:5],
        )
    else:
        logger.info(
            "dynamo_archive_ok cutoff=%s archived=%s deleted=%s",
            cutoff_date,
            archived,
            deleted,
        )

    return {
        "cutoff_date": cutoff_date,
        "retention_days": RETENTION_DAYS,
        "archived_uploaded": archived,
        "ddb_deleted": deleted,
        "errors": errors[:20],
        "error_count": len(errors),
    }
