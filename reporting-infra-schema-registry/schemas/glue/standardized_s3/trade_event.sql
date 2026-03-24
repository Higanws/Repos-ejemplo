-- Capa STANDARDIZED: Parquet (salida Glue validated_to_standardized).
CREATE EXTERNAL TABLE IF NOT EXISTS standardized_s3.trade_event (
  external_event_id VARCHAR(100),
  session_date DATE,
  event_datetime TIMESTAMP,
  settlement_datetime TIMESTAMP,
  book_id VARCHAR(50),
  instrument_id VARCHAR(80),
  event_type_id VARCHAR(40),
  custody_country VARCHAR(60),
  currency_code VARCHAR(10),
  nominal_delta DECIMAL(20,6),
  price DECIMAL(20,8),
  fees DECIMAL(20,2),
  fx_rate DECIMAL(20,8),
  source_file VARCHAR(200),
  ingestion_ts TIMESTAMP,
  etl_standardized_at TIMESTAMP
)
PARTITIONED BY (load_date DATE)
STORED AS PARQUET
LOCATION 's3://{{standardized_bucket}}/trade_event/';
