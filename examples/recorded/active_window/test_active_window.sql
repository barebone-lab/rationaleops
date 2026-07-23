-- Generated from Decision Contract: decision-active-window-v1
-- A dbt singular test passes when this query returns zero rows.
WITH cases(case_id, activity_at, billing_type, expected_active) AS (
    VALUES
        ('postpaid_day_37', DATE '2026-06-16', 'postpaid', TRUE),
        ('postpaid_day_38', DATE '2026-06-15', 'postpaid', FALSE),
        ('prepaid_day_30',  DATE '2026-06-23', 'prepaid',  TRUE),
        ('prepaid_day_31',  DATE '2026-06-22', 'prepaid',  FALSE)
),
evaluated AS (
    SELECT
        case_id,
        expected_active,
        activity_at >= DATE '2026-07-23' -
            CASE
                WHEN billing_type = 'prepaid' THEN INTERVAL 30 DAY
                ELSE INTERVAL 37 DAY
            END AS actual_active
    FROM cases
)
SELECT case_id, expected_active, actual_active
FROM evaluated
WHERE actual_active IS DISTINCT FROM expected_active;
