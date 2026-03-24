CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.fact_price_history (
  price_id BIGINT IDENTITY(1,1),
  session_date DATE NOT NULL,
  instrument_id VARCHAR(80) NOT NULL,
  price_datetime TIMESTAMP NOT NULL,
  price NUMERIC(20,8),
  currency_code VARCHAR(10),
  price_source_id VARCHAR(30),
  is_closing_price BOOLEAN,
  is_opening_price BOOLEAN,
  source_system VARCHAR(30),
  etl_loaded_at TIMESTAMP,
  PRIMARY KEY (price_id)
);
