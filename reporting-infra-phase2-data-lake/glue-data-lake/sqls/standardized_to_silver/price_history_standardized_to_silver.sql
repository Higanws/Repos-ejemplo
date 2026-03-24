-- Spark SQL: vista `src` = parquet standardized.
SELECT
  session_date,
  instrument_id,
  price_datetime,
  price,
  currency_code,
  price_source_id,
  is_closing_price,
  is_opening_price,
  ingestion_ts,
  'finanzas_api' AS source_system,
  current_timestamp() AS etl_loaded_at,
  load_date
FROM src
