CREATE EXTERNAL TABLE IF NOT EXISTS silver_s3.price_history (
  session_date DATE,
  instrument_id VARCHAR(80),
  price_datetime TIMESTAMP,
  price DECIMAL(20,8),
  currency_code VARCHAR(10),
  price_source_id VARCHAR(30),
  is_closing_price BOOLEAN,
  is_opening_price BOOLEAN,
  source_system VARCHAR(30),
  etl_loaded_at TIMESTAMP
)
PARTITIONED BY (load_date DATE)
STORED AS PARQUET
LOCATION 's3://{{silver_bucket}}/price_history/';
