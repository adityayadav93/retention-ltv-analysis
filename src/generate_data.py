"""Generate a realistic synthetic SaaS billing & usage dataset.

Outputs (data/raw/):
    customers.csv        one row per customer
    onboarding.csv       onboarding completion date (blank = never completed)
    invoices.csv         one row per customer per billed month
    usage_monthly.csv    product usage per customer per lifecycle month
    marketing_spend.csv  monthly spend by acquisition channel

Observation window: 2024-01 .. 2025-12 (snapshot 2025-12-31).
Churn is simulated month by month from a hazard that depends on plan,
channel, onboarding speed, customer age and *time-varying engagement*, so the
analysis stages have genuine signal to find. Deterministic (seed=42).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
FIRST_MONTH = pd.Timestamp("2024-01-01")
LAST_MONTH = pd.Timestamp("2025-12-01")          # last billed month (snapshot month)
LAST_SIGNUP = pd.Timestamp("2025-12-31")

PLANS = ["Starter", "Growth", "Enterprise"]
PRICE = {"Starter": 49, "Growth": 149, "Enterprise": 499}
BASE_HAZARD = {"Starter": 0.050, "Growth": 0.030, "Enterprise": 0.015}
LOGIN_SCALE = {"Starter": 1.0, "Growth": 2.0, "Enterprise": 5.0}

CHANNELS = ["paid_search", "paid_social", "organic_search", "referral", "outbound"]
CHANNEL_HAZARD = {"paid_search": 1.00, "paid_social": 1.30, "organic_search": 0.85,
                  "referral": 0.70, "outbound": 0.90}
CAC = {"paid_search": 900, "paid_social": 1200, "organic_search": 400,
       "referral": 450, "outbound": 3000}

REGIONS = ["North America", "EMEA", "APAC", "LATAM"]
REGION_P = [0.45, 0.30, 0.17, 0.08]


def months_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def generate(out_dir: Path) -> None:
    rng = np.random.default_rng(SEED)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- signups per month: growing, mild seasonality ------------------------
    signup_months = pd.date_range(FIRST_MONTH, "2025-12-01", freq="MS")
    base = np.linspace(260, 560, len(signup_months))
    season = 1 + 0.08 * np.sin(np.arange(len(signup_months)) / 12 * 2 * np.pi)
    n_per_month = np.round(base * season).astype(int)

    customers, onboarding, invoices, usage = [], [], [], []
    cust_id = 0

    for month, n in zip(signup_months, n_per_month):
        days_in_month = month.days_in_month
        for _ in range(n):
            cust_id += 1
            cid = f"C{cust_id:05d}"
            signup_date = month + pd.Timedelta(days=int(rng.integers(0, days_in_month)))
            if signup_date > LAST_SIGNUP:
                signup_date = LAST_SIGNUP
            plan0 = rng.choice(PLANS, p=[0.55, 0.35, 0.10])
            ch_p = {"Starter": [0.28, 0.27, 0.25, 0.17, 0.03],
                    "Growth": [0.25, 0.20, 0.25, 0.20, 0.10],
                    "Enterprise": [0.10, 0.05, 0.15, 0.20, 0.50]}[plan0]
            channel = rng.choice(CHANNELS, p=ch_p)
            region = rng.choice(REGIONS, p=REGION_P)

            # latent engagement drives onboarding speed *and* later usage / churn
            x = rng.normal(0, 0.4)
            e0 = float(np.exp(x))

            p_never = float(np.clip(0.20 / e0 ** 1.2, 0.05, 0.50))
            if rng.random() < p_never:
                onb_days = None
            else:
                d = rng.lognormal(np.log(6), 0.9) / e0 ** 0.7
                onb_days = int(max(0, round(d)))
                if onb_days > 60:
                    onb_days = None
            if onb_days is None:
                onb_mult = 2.2
            elif onb_days <= 3:
                onb_mult = 0.5
            elif onb_days <= 14:
                onb_mult = 1.0
            else:
                onb_mult = 1.6

            customers.append((cid, signup_date.date(), region, plan0, channel))
            onboarding.append((cid, (signup_date + pd.Timedelta(days=onb_days)).date()
                               if onb_days is not None else None))

            # ---- month-by-month simulation --------------------------------
            plan = plan0
            m = month
            age = 0
            while m <= LAST_MONTH:
                age += 1
                x = 0.85 * x + rng.normal(0, 0.20)
                e = float(np.exp(x))

                invoices.append((f"I{len(invoices) + 1:07d}", cid, m.date(), plan, PRICE[plan]))

                logins = int(rng.poisson(8 * e * LOGIN_SCALE[plan]))
                feats = int(min(12, rng.poisson(3 * e)))
                last_login = (m + pd.Timedelta(days=int(rng.integers(0, 28)))).date() if logins > 0 else None
                usage.append((cid, age, m.date(), logins, feats, last_login))

                # hazard of churning at the end of this month
                age_mult = 1.6 if age <= 3 else (1.2 if age <= 6 else 0.9)
                eng_mult = float(np.clip(e ** -0.7, 0.5, 2.5))
                h = (BASE_HAZARD[plan] * onb_mult * CHANNEL_HAZARD[channel]
                     * age_mult * eng_mult)
                h = float(np.clip(h, 0.003, 0.35))
                if m < LAST_MONTH and rng.random() < h:
                    break

                # plan changes (expansion / contraction)
                u = rng.random()
                p_up = 0.020 * (2 if e > 1.3 else 1)
                p_down = 0.010 * (2 if e < 0.7 else 1)
                if u < p_up and plan != "Enterprise":
                    plan = PLANS[PLANS.index(plan) + 1]
                elif u > 1 - p_down and plan != "Starter":
                    plan = PLANS[PLANS.index(plan) - 1]
                m = m + pd.DateOffset(months=1)

    cust_df = pd.DataFrame(customers, columns=["customer_id", "signup_date", "region",
                                               "plan_at_signup", "acquisition_channel"])
    onb_df = pd.DataFrame(onboarding, columns=["customer_id", "onboarding_completed_date"])
    inv_df = pd.DataFrame(invoices, columns=["invoice_id", "customer_id", "invoice_month",
                                             "plan", "mrr"])
    use_df = pd.DataFrame(usage, columns=["customer_id", "month_number", "usage_month",
                                          "logins", "features_used", "last_login_date"])

    # ---- marketing spend: new customers x CAC x noise ------------------------
    cust_df["signup_month"] = pd.to_datetime(cust_df["signup_date"]).dt.to_period("M").dt.to_timestamp()
    new_by = (cust_df.groupby(["signup_month", "acquisition_channel"]).size()
              .unstack(fill_value=0).reindex(columns=CHANNELS, fill_value=0))
    rows = []
    for month, r in new_by.iterrows():
        for ch in CHANNELS:
            spend = r[ch] * CAC[ch] * rng.normal(1.0, 0.08)
            rows.append((month.date(), ch, round(float(spend), 2)))
    spend_df = pd.DataFrame(rows, columns=["spend_month", "channel", "spend"])
    cust_df = cust_df.drop(columns="signup_month")

    cust_df.to_csv(out_dir / "customers.csv", index=False)
    onb_df.to_csv(out_dir / "onboarding.csv", index=False)
    inv_df.to_csv(out_dir / "invoices.csv", index=False)
    use_df.to_csv(out_dir / "usage_monthly.csv", index=False)
    spend_df.to_csv(out_dir / "marketing_spend.csv", index=False)
    print(f"customers={len(cust_df):,}  invoices={len(inv_df):,}  usage={len(use_df):,}  "
          f"spend rows={len(spend_df):,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "raw"))
    generate(Path(ap.parse_args().out))
