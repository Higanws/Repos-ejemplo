-- Spark SQL: vista `src` = raw JSON (job).
SELECT
  external_event_id,
  to_date(CAST(session_date AS STRING)) AS session_date,
  to_timestamp(CAST(event_datetime AS STRING)) AS event_datetime,
  to_timestamp(CAST(settlement_datetime AS STRING)) AS settlement_datetime,
  book_id,
  instrument_id,
  event_type_id,
  custody_country,
  CAST(nominal_delta AS DECIMAL(20,6)) AS nominal_delta,
  CAST(price AS DECIMAL(20,8)) AS price,
  COALESCE(CAST(fees AS DECIMAL(20,2)), CAST(0 AS DECIMAL(20,2))) AS fees,
  COALESCE(CAST(fx_rate AS DECIMAL(20,8)), CAST(1 AS DECIMAL(20,8))) AS fx_rate,
  UPPER(COALESCE(currency_code, '')) AS currency_code,
  source_file,
  to_timestamp(CAST(ingestion_ts AS STRING)) AS ingestion_ts,
  current_timestamp() AS etl_standardized_at,
  to_date(to_timestamp(CAST(ingestion_ts AS STRING))) AS load_date
FROM src
