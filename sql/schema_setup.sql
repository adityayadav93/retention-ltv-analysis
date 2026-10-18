-- =============================================================================
-- schema_setup.sql  |  Customer Retention & LTV warehouse
-- Dialect: ANSI / PostgreSQL (also runs unchanged on DuckDB, used for local runs)
-- =============================================================================

DROP TABLE IF EXISTS usage_monthly;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS onboarding;
DROP TABLE IF EXISTS marketing_spend;
DROP TABLE IF EXISTS customers;

-- One row per customer (static attributes) -----------------------------------
CREATE TABLE customers (
    customer_id          VARCHAR(10) PRIMARY KEY,
    signup_date          DATE        NOT NULL,
    region               VARCHAR(20) NOT NULL,
    plan_at_signup       VARCHAR(20) NOT NULL,
    acquisition_channel  VARCHAR(20) NOT NULL
);

-- Date the customer finished the guided onboarding (NULL = never completed) ---
CREATE TABLE onboarding (
    customer_id                VARCHAR(10) PRIMARY KEY REFERENCES customers (customer_id),
    onboarding_completed_date  DATE
);

-- One row per customer per billed month. A customer is "churned" the month
-- after their final invoice (grain: customer x month) -------------------------
CREATE TABLE invoices (
    invoice_id     VARCHAR(12) PRIMARY KEY,
    customer_id    VARCHAR(10) NOT NULL REFERENCES customers (customer_id),
    invoice_month  DATE        NOT NULL,          -- first day of billed month
    plan           VARCHAR(20) NOT NULL,
    mrr            NUMERIC(10, 2) NOT NULL
);

-- Product usage per customer per lifecycle month (month_number 1 = first
-- billed month, used as a proxy for the first-30-day window) ------------------
CREATE TABLE usage_monthly (
    customer_id      VARCHAR(10) NOT NULL REFERENCES customers (customer_id),
    month_number     INTEGER     NOT NULL,
    usage_month      DATE        NOT NULL,
    logins           INTEGER     NOT NULL,
    features_used    INTEGER     NOT NULL,
    last_login_date  DATE,
    PRIMARY KEY (customer_id, month_number)
);

-- Monthly acquisition spend by channel (for CAC) ------------------------------
CREATE TABLE marketing_spend (
    spend_month  DATE        NOT NULL,
    channel      VARCHAR(20) NOT NULL,
    spend        NUMERIC(12, 2) NOT NULL,
    PRIMARY KEY (spend_month, channel)
);

CREATE INDEX idx_invoices_customer_month ON invoices (customer_id, invoice_month);
CREATE INDEX idx_usage_customer         ON usage_monthly (customer_id);
