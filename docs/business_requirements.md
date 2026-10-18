# Business Requirements Document: Retention & LTV Analytics

| | |
|---|---|
| **Project** | Customer Retention & Revenue LTV Optimization |
| **Status** | Final (portfolio case study; fictional company "Nimbus", data is synthetic) |
| **Analyst** | Portfolio author |
| **Stakeholders** | CFO (sponsor), VP Growth, Head of Customer Success, Product Lead (onboarding), Marketing Ops |

## 1. Background and problem statement

Nimbus is a B2B SaaS company with three plans (Starter $49, Growth $149, Enterprise $499 per month) and five acquisition
channels. Recurring revenue is growing quickly, but leadership suspects growth is being bought rather than retained: finance sees
roughly 4-5% of customers cancel every month and has no shared view of which channels or customers are worth the money.

**Problem statement.** We cannot currently answer: *which customers should we acquire, where does revenue leak, and what is the
cheapest intervention that reduces churn?*

## 2. Business objectives

| # | Objective | Success measure |
|---|---|---|
| O1 | Give finance and growth one trusted set of retention and revenue KPIs | Metric definitions agreed (section 4); monthly KPI table reproducible from SQL |
| O2 | Identify where revenue leaks and which segments churn | Cohort retention curves and churn by segment available |
| O3 | Rank acquisition channels by profitability | LTV:CAC and CAC payback per channel |
| O4 | Identify early, actionable drivers of churn | Interpretable model with hold-out AUC > 0.70 |
| O5 | Quantify the ROI of the top retention lever | Scenario model with explicit assumptions and sensitivity |

**Out of scope:** pricing changes, product-feature roadmap, forecasting beyond the observed window, causal estimation (a randomised
pilot is recommended instead).

## 3. Stakeholders and decisions supported

| Stakeholder | Decision this work informs |
|---|---|
| CFO | Is growth durable? How much recurring revenue is at risk? |
| VP Growth | How to reallocate acquisition budget across channels |
| Head of Customer Success | Which accounts to contact this week; who to enrol in onboarding |
| Product Lead | Whether to invest in faster onboarding |

## 4. KPI and metric definitions

Observation window: Jan 2024 to Dec 2025. Snapshot month: Dec 2025. A customer is **active** in month *M* if they have an invoice
dated *M*, and **churned in month M** if their last invoice was in *M-1*. The snapshot month cannot show churn and is excluded
from churn numerators and denominators.

| KPI | Definition | Source |
|---|---|---|
| **MRR** | Sum of monthly invoice amounts for active customers | `invoices.mrr` |
| **New / Expansion / Contraction / Churned MRR** | MRR from first invoices / increases on existing customers / decreases / MRR of customers lost | `kpi_monthly` query (LAG / LEAD) |
| **Logo churn rate** | Customers churned in M / customers active in M-1 | `kpi_monthly` |
| **Net revenue retention (monthly)** | (Begin MRR + expansion - contraction - churned) / begin MRR | `kpi_monthly` |
| **ARPA** | MRR / active customers | `kpi_monthly` |
| **CAC** | Channel acquisition spend / customers acquired from that channel | `marketing_spend`, `customers` |
| **LTV** | ARPA x gross margin / monthly logo churn rate (observed per segment) | `unit_economics_*` |
| **LTV:CAC** | LTV / CAC; target >= 3x | `unit_economics_by_channel` |
| **CAC payback** | CAC / (ARPA x gross margin), in months; target < 12 | `unit_economics_by_channel` |
| **6-month churn** | Customer billed for <= 6 months, among cohorts with >= 7 months of history | `churn_features` |
| **RFM** | Recency (days since last login), Frequency (logins in last 3 months), Monetary (lifetime billed revenue), each scored 1-5 with `NTILE(5)` | `rfm_base` |

## 5. Assumptions

| ID | Assumption | Value | Rationale / risk |
|---|---|---|---|
| A1 | Gross margin | 80% | Typical SaaS range; used in LTV, payback and ROI. LTV scales linearly with it. |
| A2 | LTV uses a constant churn rate per segment | observed | Early-life churn is higher than late-life, so this *understates* LTV for retained customers and overstates it for new ones. |
| A3 | Marketing spend is attributed 1:1 to the channel of the customers it acquired | n/a | Ignores shared brand spend and multi-touch effects (see the attribution project). |
| A4 | First billed month approximates the first-30-day window | n/a | Slight misalignment for mid-month signups. |
| A5 | Onboarding programme cost | $40 per enrolled customer | Placeholder for automation plus part-time specialist time; replace with a finance estimate. |
| A6 | Onboarding effect | 50% of the covariate-adjusted estimate | Observational data cannot rule out self-selection; sensitivity shown down to 25%. |
| A7 | Value of a retained customer | 12 months of gross profit | Conservative cap versus full LTV. |
| A8 | Marginal referral efficiency | 50% of historical average | Referral volume has diminishing returns. |

## 6. User stories

| # | As a... | I want... | So that... | Delivered by |
|---|---|---|---|---|
| U1 | CFO | one view of MRR, churn and NRR with an MRR bridge | I can explain revenue changes to the board | Dashboard: Executive view |
| U2 | VP Growth | LTV:CAC and payback by channel | I can shift budget to profitable channels | `unit_economics_by_channel`, dashboard |
| U3 | Head of CS | a list of high-value accounts with falling usage | my team calls the right customers first | `rfm_segments.csv` |
| U4 | Product Lead | evidence of how onboarding speed relates to churn | I can size the case for investing in onboarding | Notebook section 5, deck slide 3 |
| U5 | Analyst | modular, reproducible SQL | numbers can be audited and re-run | `sql/`, `make all` |
| U6 | Any stakeholder | filters by region and plan | I can see my own segment | Dashboard slicers |

## 7. Data requirements

| Table | Grain | Key fields |
|---|---|---|
| `customers` | customer | signup_date, region, plan_at_signup, acquisition_channel |
| `onboarding` | customer | onboarding_completed_date (NULL = never) |
| `invoices` | customer x billed month | invoice_month, plan, mrr |
| `usage_monthly` | customer x lifecycle month | logins, features_used, last_login_date |
| `marketing_spend` | month x channel | spend |

Data is synthetic (seeded, `src/generate_data.py`) because real billing data is confidential. Churn is generated from a hazard model
with known drivers, so results are a demonstration of method, not evidence about any real company.

## 8. Deliverables and acceptance criteria

| Deliverable | Acceptance criterion |
|---|---|
| SQL layer | Runs end to end from `make warehouse`; CTEs plus LAG / LEAD / DENSE_RANK / NTILE |
| Analysis notebook | Executes top to bottom without error; every headline number written to `results/metrics.json` |
| Dashboard | Executive view above diagnostic view; region and plan slicers; tiles reconcile to the SQL KPI table |
| Executive deck | 5 slides; every figure traceable to `metrics.json` |
| Recommendations | Quantified, with assumptions and sensitivity, and a validation step |

## 9. Risks and limitations

- **Correlation is not causation.** The onboarding association is partly self-selection; the case uses a haircut and a pilot is recommended.
- **Synthetic data.** Effect sizes reflect the simulator's parameters.
- **Single observation window.** Seasonality cannot be separated from trend over 24 months.
- **Static LTV formula.** It is a planning heuristic, not a forecast.
