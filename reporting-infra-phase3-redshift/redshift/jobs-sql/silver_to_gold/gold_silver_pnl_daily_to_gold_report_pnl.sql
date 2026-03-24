BEGIN;

DELETE FROM gold.gold_report_pnl
WHERE (:load_mode = 'full' OR session_date = :session_date);

INSERT INTO gold.gold_report_pnl (
  session_date, book_id, instrument_id, custody_country, currency_code,
  market_price_close, nominal_close, market_value_close,
  pnl_daily, pnl_mtd, pnl_ytd, pnl_itd, row_type, etl_loaded_at
)
SELECT
  session_date,
  book_id,
  instrument_id,
  custody_country,
  currency_code,
  market_price_close,
  nominal_close,
  market_value_close,
  total_pnl_daily AS pnl_daily,
  pnl_mtd,
  pnl_ytd,
  pnl_itd,
  'position' AS row_type,
  GETDATE() AS etl_loaded_at
FROM gold.silver_pnl_daily
WHERE (:load_mode = 'full' OR session_date = :session_date);

COMMIT;
