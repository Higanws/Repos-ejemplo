-- Spark SQL: vista `src` = raw CSV.
SELECT
  to_date(CAST(session_date AS STRING)) AS session_date,
  instrument_id,
  to_timestamp(CAST(price_datetime AS STRING)) AS price_datetime,
  CAST(price AS DECIMAL(20,8)) AS price,
  UPPER(COALESCE(currency_code, '')) AS currency_code,
  price_source_id,
  CAST(is_closing_price AS BOOLEAN) AS is_closing_price,
  CAST(is_opening_price AS BOOLEAN) AS is_opening_price,
  to_timestamp(CAST(ingestion_ts AS STRING)) AS ingestion_ts,
  current_timestamp() AS etl_standardized_at,
  to_date(to_timestamp(CAST(ingestion_ts AS STRING))) AS load_date
FROM src
