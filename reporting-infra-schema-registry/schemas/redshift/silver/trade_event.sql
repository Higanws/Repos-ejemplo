CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.fact_trade_event (
  event_id BIGINT IDENTITY(1,1),
  external_event_id VARCHAR(100) NOT NULL,
  session_date DATE NOT NULL,
  event_datetime TIMESTAMP NOT NULL,
  settlement_datetime TIMESTAMP,
  book_id VARCHAR(50) NOT NULL,
  instrument_id VARCHAR(80) NOT NULL,
  event_type_id VARCHAR(40) NOT NULL,
  custody_country VARCHAR(60),
  currency_code VARCHAR(10),
  nominal_delta NUMERIC(20,6),
  price NUMERIC(20,8),
  gross_amount NUMERIC(20,2),
  fees NUMERIC(20,2),
  net_amount NUMERIC(20,2),
  fx_rate NUMERIC(20,8),
  net_amount_usd NUMERIC(20,2),
  source_system VARCHAR(30),
  etl_loaded_at TIMESTAMP,
  PRIMARY KEY (event_id)
);
