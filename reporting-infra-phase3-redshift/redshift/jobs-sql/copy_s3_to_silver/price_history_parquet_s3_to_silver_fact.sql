BEGIN;

DELETE FROM silver.fact_price_history
WHERE (__LOAD_MODE__ = 'full' OR session_date = __SESSION_DATE__);

COPY silver.fact_price_history
FROM '__S3_PRICE_HISTORY_PATH__'
IAM_ROLE '__REDSHIFT_IAM_ROLE_ARN__'
FORMAT AS PARQUET;

COMMIT;
