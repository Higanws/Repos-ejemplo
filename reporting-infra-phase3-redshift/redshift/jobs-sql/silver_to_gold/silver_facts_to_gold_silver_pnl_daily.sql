BEGIN;

DELETE FROM gold.silver_pnl_daily
WHERE (:load_mode = 'full' OR session_date = :session_date);

INSERT INTO gold.silver_pnl_daily (
  session_date, book_id, instrument_id, custody_country, currency_code,
  nominal_close, market_price_close, market_value_close,
  realized_pnl_session, unrealized_pnl_session, total_pnl_daily,
  pnl_mtd, pnl_ytd, pnl_itd, fees_session, etl_loaded_at
)
SELECT
  e.session_date,
  e.book_id,
  e.instrument_id,
  MAX(e.custody_country) AS custody_country,
  MAX(e.currency_code) AS currency_code,
  SUM(e.nominal_delta) AS nominal_close,
  MAX(CASE WHEN p.is_closing_price THEN p.price END) AS market_price_close,
  SUM(e.nominal_delta) * MAX(CASE WHEN p.is_closing_price THEN p.price END) AS market_value_close,
  SUM(CASE WHEN e.event_type_id IN ('SELL', 'MATURITY', 'DIVIDEND', 'COUPON') THEN e.net_amount ELSE 0 END) AS realized_pnl_session,
  SUM(CASE WHEN e.event_type_id IN ('PRICE_UPDATE', 'FX_REVALUATION') THEN e.net_amount ELSE 0 END) AS unrealized_pnl_session,
  SUM(CASE WHEN e.event_type_id IN ('SELL', 'MATURITY', 'DIVIDEND', 'COUPON', 'PRICE_UPDATE', 'FX_REVALUATION') THEN e.net_amount ELSE 0 END) AS total_pnl_daily,
  SUM(CASE WHEN DATE_TRUNC('month', e.session_date) = DATE_TRUNC('month', :session_date::date) THEN e.net_amount ELSE 0 END) AS pnl_mtd,
  SUM(CASE WHEN DATE_TRUNC('year', e.session_date) = DATE_TRUNC('year', :session_date::date) THEN e.net_amount ELSE 0 END) AS pnl_ytd,
  SUM(e.net_amount) AS pnl_itd,
  SUM(COALESCE(e.fees, 0)) AS fees_session,
  GETDATE() AS etl_loaded_at
FROM silver.fact_trade_event e
LEFT JOIN silver.fact_price_history p
  ON e.session_date = p.session_date
 AND e.instrument_id = p.instrument_id
WHERE e.session_date = :session_date
   OR :load_mode = 'full'
GROUP BY e.session_date, e.book_id, e.instrument_id;

COMMIT;
