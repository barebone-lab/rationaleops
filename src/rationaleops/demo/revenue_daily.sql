SELECT
    customer_id,
    activity_at,
    billing_type,
    country_code,
    account_status
FROM analytics.revenue_daily
WHERE activity_at >= current_date - interval '37 days'
  AND country_code <> 'DE'
  AND account_status NOT IN ('trial', 'refunded');
