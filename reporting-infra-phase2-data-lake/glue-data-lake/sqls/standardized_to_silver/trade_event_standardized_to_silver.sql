-- Spark SQL: vista `src` = parquet standardized.
SELECT
  external_event_id,
  session_date,
  event_datetime,
  settlement_datetime,
  book_id,
  instrument_id,
  event_type_id,
  custody_country,
  currency_code,
  nominal_delta,
  price,
  CAST(nominal_delta * price AS DECIMAL(20,2)) AS gross_amount,
  fees,
  CAST(
    CAST(nominal_delta * price AS DECIMAL(20,2)) + fees AS DECIMAL(20,2)
  ) AS net_amount,
  fx_rate,
  CAST(
    (CAST(nominal_delta * price AS DECIMAL(20,2)) + fees) / fx_rate AS DECIMAL(20,2)
  ) AS net_amount_usd,
  'finanzas_api' AS source_system,
  current_timestamp() AS etl_loaded_at,
  load_date
FROM src
