-- =============================================================================
-- analytics_queries.sql  |  Retention & LTV analytics layer
-- Each query is tagged `-- name: <id>`; src/build_warehouse.py runs them all
-- and writes data/processed/<id>.csv. Dialect: PostgreSQL-compatible.
--
-- Definitions (see docs/business_requirements.md):
--   * Active customer in month M  = has an invoice dated M
--   * Churned in month M          = last invoice was M-1 (no invoice in M or later)
--   * Final observed month (2025-12) cannot show churn, so it is excluded from
--     churn denominators/numerators where noted.
-- =============================================================================


-- name: kpi_monthly_segmented
-- Monthly MRR movements and logo counts by region x plan-at-signup.
-- Segmenting on static attributes keeps customers in one segment for life.
-- Window functions: LAG / LEAD over each customer's billing history.
WITH invoice_history AS (
    SELECT
        i.customer_id,
        c.region,
        c.plan_at_signup,
        i.invoice_month,
        i.mrr,
        LAG(i.mrr)           OVER w AS prev_mrr,
        LEAD(i.invoice_month) OVER w AS next_month
    FROM invoices i
    JOIN customers c USING (customer_id)
    WINDOW w AS (PARTITION BY i.customer_id ORDER BY i.invoice_month)
),
active_and_movements AS (
    SELECT
        invoice_month                                              AS month,
        region,
        plan_at_signup,
        1                                                          AS active_customers,
        mrr                                                        AS mrr,
        CASE WHEN prev_mrr IS NULL THEN 1 ELSE 0 END               AS new_customers,
        CASE WHEN prev_mrr IS NULL THEN mrr ELSE 0 END             AS new_mrr,
        CASE WHEN prev_mrr IS NOT NULL AND mrr > prev_mrr
             THEN mrr - prev_mrr ELSE 0 END                        AS expansion_mrr,
        CASE WHEN prev_mrr IS NOT NULL AND mrr < prev_mrr
             THEN prev_mrr - mrr ELSE 0 END                        AS contraction_mrr,
        0                                                          AS churned_customers,
        0                                                          AS churned_mrr
    FROM invoice_history
),
churn_events AS (
    -- a customer whose final invoice is M churns in M+1 (booked in M+1)
    SELECT
        CAST(invoice_month + INTERVAL '1 month' AS DATE)           AS month,
        region,
        plan_at_signup,
        0, 0, 0, 0, 0, 0,
        1                                                          AS churned_customers,
        mrr                                                        AS churned_mrr
    FROM invoice_history
    WHERE next_month IS NULL
      AND invoice_month < (SELECT MAX(invoice_month) FROM invoices)
),
unioned AS (
    SELECT * FROM active_and_movements
    UNION ALL
    SELECT * FROM churn_events
)
SELECT
    month,
    region,
    plan_at_signup,
    SUM(active_customers)  AS active_customers,
    SUM(mrr)               AS mrr,
    SUM(new_customers)     AS new_customers,
    SUM(new_mrr)           AS new_mrr,
    SUM(expansion_mrr)     AS expansion_mrr,
    SUM(contraction_mrr)   AS contraction_mrr,
    SUM(churned_customers) AS churned_customers,
    SUM(churned_mrr)       AS churned_mrr
FROM unioned
GROUP BY month, region, plan_at_signup
ORDER BY month, region, plan_at_signup;


-- name: kpi_monthly
-- Executive KPI table: MRR bridge, logo churn %, net revenue retention (NRR).
WITH seg AS (
    SELECT
        i.customer_id, i.invoice_month, i.mrr,
        LAG(i.mrr)            OVER w AS prev_mrr,
        LEAD(i.invoice_month) OVER w AS next_month
    FROM invoices i
    WINDOW w AS (PARTITION BY i.customer_id ORDER BY i.invoice_month)
),
monthly AS (
    SELECT
        invoice_month                                                       AS month,
        COUNT(*)                                                            AS active_customers,
        SUM(mrr)                                                            AS mrr,
        SUM(CASE WHEN prev_mrr IS NULL THEN 1 ELSE 0 END)                   AS new_customers,
        SUM(CASE WHEN prev_mrr IS NULL THEN mrr ELSE 0 END)                 AS new_mrr,
        SUM(CASE WHEN prev_mrr IS NOT NULL AND mrr > prev_mrr THEN mrr - prev_mrr ELSE 0 END) AS expansion_mrr,
        SUM(CASE WHEN prev_mrr IS NOT NULL AND mrr < prev_mrr THEN prev_mrr - mrr ELSE 0 END) AS contraction_mrr
    FROM seg
    GROUP BY invoice_month
),
churned AS (
    SELECT
        CAST(invoice_month + INTERVAL '1 month' AS DATE) AS month,
        COUNT(*)                                          AS churned_customers,
        SUM(mrr)                                          AS churned_mrr
    FROM seg
    WHERE next_month IS NULL
      AND invoice_month < (SELECT MAX(invoice_month) FROM invoices)
    GROUP BY 1
),
joined AS (
    SELECT
        m.month,
        m.active_customers,
        m.mrr,
        m.new_customers, m.new_mrr, m.expansion_mrr, m.contraction_mrr,
        COALESCE(c.churned_customers, 0) AS churned_customers,
        COALESCE(c.churned_mrr, 0)       AS churned_mrr,
        LAG(m.active_customers) OVER (ORDER BY m.month) AS begin_customers,
        LAG(m.mrr)              OVER (ORDER BY m.month) AS begin_mrr
    FROM monthly m
    LEFT JOIN churned c USING (month)
)
SELECT
    month,
    active_customers,
    mrr,
    new_customers, new_mrr, expansion_mrr, contraction_mrr, churned_customers, churned_mrr,
    ROUND(mrr * 1.0 / active_customers, 2)                                              AS arpa,
    ROUND(100.0 * churned_customers / NULLIF(begin_customers, 0), 2)                    AS logo_churn_pct,
    ROUND(100.0 * (begin_mrr + expansion_mrr - contraction_mrr - churned_mrr)
          / NULLIF(begin_mrr, 0), 2)                                                    AS nrr_pct
FROM joined
ORDER BY month;


-- name: cohort_retention
-- Monthly signup cohorts: logo retention and revenue retention by months since signup.
WITH cohorts AS (
    SELECT customer_id, MIN(invoice_month) AS cohort_month
    FROM invoices
    GROUP BY customer_id
),
activity AS (
    SELECT
        c.cohort_month,
        i.customer_id,
        i.mrr,
        (EXTRACT(YEAR FROM i.invoice_month) - EXTRACT(YEAR FROM c.cohort_month)) * 12
        + (EXTRACT(MONTH FROM i.invoice_month) - EXTRACT(MONTH FROM c.cohort_month)) AS months_since_signup
    FROM invoices i
    JOIN cohorts c USING (customer_id)
),
cohort_base AS (
    SELECT cohort_month,
           COUNT(DISTINCT customer_id) AS cohort_size,
           SUM(mrr)                    AS cohort_start_mrr
    FROM activity
    WHERE months_since_signup = 0
    GROUP BY cohort_month
)
SELECT
    a.cohort_month,
    CAST(a.months_since_signup AS INTEGER)                      AS months_since_signup,
    b.cohort_size,
    COUNT(DISTINCT a.customer_id)                               AS active_customers,
    ROUND(100.0 * COUNT(DISTINCT a.customer_id) / b.cohort_size, 2)  AS logo_retention_pct,
    ROUND(100.0 * SUM(a.mrr) / b.cohort_start_mrr, 2)           AS revenue_retention_pct
FROM activity a
JOIN cohort_base b USING (cohort_month)
GROUP BY a.cohort_month, a.months_since_signup, b.cohort_size, b.cohort_start_mrr
ORDER BY a.cohort_month, a.months_since_signup;


-- name: unit_economics_by_channel
-- CAC, ARPA, churn, LTV and LTV:CAC per acquisition channel.
--   LTV = ARPA x gross margin / monthly logo churn rate
WITH assumptions AS (
    SELECT 0.80 AS gross_margin
),
inv AS (
    SELECT
        i.customer_id, c.acquisition_channel AS channel, i.invoice_month, i.mrr,
        LEAD(i.invoice_month) OVER (PARTITION BY i.customer_id ORDER BY i.invoice_month) AS next_month
    FROM invoices i
    JOIN customers c USING (customer_id)
),
exposure AS (
    -- customer-months at risk of churning (the last observed month cannot churn)
    SELECT
        channel,
        COUNT(*)                                             AS customer_months,
        SUM(CASE WHEN next_month IS NULL THEN 1 ELSE 0 END)  AS churn_events,
        AVG(mrr)                                             AS arpa
    FROM inv
    WHERE invoice_month < (SELECT MAX(invoice_month) FROM invoices)
    GROUP BY channel
),
acquisition AS (
    SELECT
        c.acquisition_channel AS channel,
        COUNT(*)              AS customers_acquired
    FROM customers c
    GROUP BY c.acquisition_channel
),
spend AS (
    SELECT channel, SUM(spend) AS total_spend
    FROM marketing_spend
    GROUP BY channel
)
SELECT
    a.channel,
    a.customers_acquired,
    ROUND(s.total_spend, 0)                                           AS total_spend,
    ROUND(s.total_spend / a.customers_acquired, 2)                    AS cac,
    ROUND(e.arpa, 2)                                                  AS arpa,
    ROUND(100.0 * e.churn_events / e.customer_months, 2)              AS monthly_churn_pct,
    ROUND(e.arpa * (SELECT gross_margin FROM assumptions)
          / (1.0 * e.churn_events / e.customer_months), 0)            AS ltv,
    ROUND((e.arpa * (SELECT gross_margin FROM assumptions)
          / (1.0 * e.churn_events / e.customer_months))
          / (s.total_spend / a.customers_acquired), 2)                AS ltv_to_cac,
    ROUND((s.total_spend / a.customers_acquired)
          / (e.arpa * (SELECT gross_margin FROM assumptions)), 1)     AS cac_payback_months
FROM acquisition a
JOIN spend s    USING (channel)
JOIN exposure e USING (channel)
ORDER BY ltv_to_cac DESC;


-- name: unit_economics_by_plan
-- Same LTV logic by plan at signup (no CAC: spend is not tracked per plan).
WITH inv AS (
    SELECT
        i.customer_id, c.plan_at_signup AS plan, i.invoice_month, i.mrr,
        LEAD(i.invoice_month) OVER (PARTITION BY i.customer_id ORDER BY i.invoice_month) AS next_month
    FROM invoices i
    JOIN customers c USING (customer_id)
    WHERE c.plan_at_signup IS NOT NULL
),
exposure AS (
    SELECT
        plan,
        COUNT(DISTINCT customer_id)                          AS customers,
        COUNT(*)                                             AS customer_months,
        SUM(CASE WHEN next_month IS NULL THEN 1 ELSE 0 END)  AS churn_events,
        AVG(mrr)                                             AS arpa
    FROM inv
    WHERE invoice_month < (SELECT MAX(invoice_month) FROM invoices)
    GROUP BY plan
)
SELECT
    plan                                                      AS plan_at_signup,
    customers,
    ROUND(arpa, 2)                                            AS arpa,
    ROUND(100.0 * churn_events / customer_months, 2)          AS monthly_churn_pct,
    ROUND(arpa * 0.80 / (1.0 * churn_events / customer_months), 0) AS ltv
FROM exposure
ORDER BY ltv DESC;


-- name: onboarding_impact
-- 6-month churn by onboarding speed. Cohorts with >= 7 months of history only,
-- so every customer has a fair chance to show churn inside the window.
WITH cust AS (
    SELECT
        c.customer_id,
        c.signup_date,
        o.onboarding_completed_date,
        (o.onboarding_completed_date - c.signup_date) AS onboarding_days,
        COUNT(i.invoice_id)                           AS invoices_billed
    FROM customers c
    JOIN onboarding o USING (customer_id)
    JOIN invoices i   USING (customer_id)
    WHERE DATE_TRUNC('month', c.signup_date) <= DATE '2025-06-01'
    GROUP BY c.customer_id, c.signup_date, o.onboarding_completed_date
),
bucketed AS (
    SELECT
        CASE
            WHEN onboarding_completed_date IS NULL THEN '4. Never completed'
            WHEN onboarding_days <= 3              THEN '1. Within 3 days'
            WHEN onboarding_days <= 14             THEN '2. 4-14 days'
            ELSE                                        '3. 15+ days'
        END                                         AS onboarding_bucket,
        CASE WHEN invoices_billed <= 6 THEN 1 ELSE 0 END AS churned_6m
    FROM cust
)
SELECT
    onboarding_bucket,
    COUNT(*)                                         AS customers,
    SUM(churned_6m)                                  AS churned_6m,
    ROUND(100.0 * SUM(churned_6m) / COUNT(*), 2)     AS churn_6m_pct
FROM bucketed
GROUP BY onboarding_bucket
ORDER BY onboarding_bucket;


-- name: churn_features
-- Modelling table: first-month behaviour -> churned within 6 months.
-- Only information available in the first billed month is used (no leakage).
SELECT
    c.customer_id,
    c.plan_at_signup,
    c.region,
    c.acquisition_channel,
    (o.onboarding_completed_date - c.signup_date)                 AS onboarding_days,
    CASE WHEN o.onboarding_completed_date IS NOT NULL
          AND (o.onboarding_completed_date - c.signup_date) <= 3
         THEN 1 ELSE 0 END                                        AS onboarded_within_3d,
    CASE WHEN o.onboarding_completed_date IS NULL THEN 1 ELSE 0 END AS onboarding_never,
    u.logins                                                      AS logins_m1,
    u.features_used                                               AS features_m1,
    CASE WHEN COUNT(i.invoice_id) <= 6 THEN 1 ELSE 0 END          AS churned_6m
FROM customers c
JOIN onboarding o    USING (customer_id)
JOIN usage_monthly u ON u.customer_id = c.customer_id AND u.month_number = 1
JOIN invoices i      ON i.customer_id = c.customer_id
WHERE DATE_TRUNC('month', c.signup_date) <= DATE '2025-06-01'
GROUP BY c.customer_id, c.plan_at_signup, c.region, c.acquisition_channel,
         c.signup_date, o.onboarding_completed_date, u.logins, u.features_used
ORDER BY c.customer_id;


-- name: top_accounts_by_region
-- Top 5 revenue accounts per region. Window function: DENSE_RANK.
WITH lifetime AS (
    SELECT
        c.customer_id, c.region, c.plan_at_signup, c.acquisition_channel,
        SUM(i.mrr)                 AS lifetime_revenue,
        MAX(i.invoice_month)       AS last_billed_month
    FROM customers c
    JOIN invoices i USING (customer_id)
    GROUP BY c.customer_id, c.region, c.plan_at_signup, c.acquisition_channel
),
ranked AS (
    SELECT *,
           DENSE_RANK() OVER (PARTITION BY region ORDER BY lifetime_revenue DESC) AS revenue_rank
    FROM lifetime
)
SELECT *
FROM ranked
WHERE revenue_rank <= 5
ORDER BY region, revenue_rank, customer_id;


-- name: rfm_base
-- RFM inputs and quintile scores for the ACTIVE base at snapshot 2025-12-31.
--   Recency   = days since last login      (lower is better)
--   Frequency = logins in last 3 months    (higher is better)
--   Monetary  = lifetime billed revenue    (higher is better)
-- Window function: NTILE(5). Score 5 = best on every dimension.
WITH active AS (
    SELECT customer_id, mrr AS current_mrr, plan AS current_plan
    FROM invoices
    WHERE invoice_month = (SELECT MAX(invoice_month) FROM invoices)
),
rfm AS (
    SELECT
        a.customer_id,
        a.current_mrr,
        a.current_plan,
        c.region,
        c.acquisition_channel,
        DATE '2025-12-31' - MAX(u.last_login_date)                          AS recency_days,
        SUM(CASE WHEN u.usage_month >= DATE '2025-10-01' THEN u.logins ELSE 0 END) AS frequency_3m,
        (SELECT SUM(mrr) FROM invoices i WHERE i.customer_id = a.customer_id) AS monetary_lifetime
    FROM active a
    JOIN customers c      USING (customer_id)
    JOIN usage_monthly u  USING (customer_id)
    GROUP BY a.customer_id, a.current_mrr, a.current_plan, c.region, c.acquisition_channel
)
SELECT
    *,
    NTILE(5) OVER (ORDER BY recency_days DESC, customer_id)   AS r_score,
    NTILE(5) OVER (ORDER BY frequency_3m ASC,  customer_id)   AS f_score,
    NTILE(5) OVER (ORDER BY monetary_lifetime ASC, customer_id) AS m_score
FROM rfm
ORDER BY customer_id;
