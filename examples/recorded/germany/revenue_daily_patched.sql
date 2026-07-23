SELECT
  customer_id,
  activity_at,
  billing_type,
  country_code,
  account_status
FROM analytics.revenue_daily
WHERE
  activity_at >= CURRENT_DATE - INTERVAL '37 DAYS'
  AND NOT account_status IN ('trial', 'refunded');
