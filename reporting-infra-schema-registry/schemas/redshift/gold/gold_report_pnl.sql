CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.gold_report_pnl (
  session_date DATE NOT NULL,
  book_id VARCHAR(50) NOT NULL,
  instrument_id VARCHAR(80) NOT NULL,
  custody_country VARCHAR(60),
  currency_code VARCHAR(10),
  market_price_close NUMERIC(20,8),
  nominal_close NUMERIC(20,6),
  market_value_close NUMERIC(20,2),
  pnl_daily NUMERIC(20,2),
  pnl_mtd NUMERIC(20,2),
  pnl_ytd NUMERIC(20,2),
  pnl_itd NUMERIC(20,2),
  row_type VARCHAR(20),
  etl_loaded_at TIMESTAMP
);
