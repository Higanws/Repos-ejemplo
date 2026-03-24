BEGIN;

DELETE FROM silver.fact_trade_event
WHERE (__LOAD_MODE__ = 'full' OR session_date = __SESSION_DATE__);

COPY silver.fact_trade_event
FROM '__S3_TRADE_EVENT_PATH__'
IAM_ROLE '__REDSHIFT_IAM_ROLE_ARN__'
FORMAT AS PARQUET;

COMMIT;
