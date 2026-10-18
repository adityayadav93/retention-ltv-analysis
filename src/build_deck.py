"""Build docs/executive_deck.pdf: a 5-slide executive summary drawn from results/metrics.json."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parents[1]
m = json.loads((ROOT / "results" / "metrics.json").read_text())
kpi = pd.read_csv(ROOT / "dashboard" / "data" / "kpi_monthly.csv", parse_dates=["month"])
ue = pd.read_csv(ROOT / "dashboard" / "data" / "unit_economics_by_channel.csv").sort_values("ltv_to_cac")
onb = pd.read_csv(ROOT / "dashboard" / "data" / "onboarding_churn.csv")

BLUE, ORANGE, AQUA, YELLOW, GREY, INK, INK2 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8a8985", "#0b0b0b", "#52514e"
plt.rcParams.update({"text.parse_math": False, "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "font.size": 11})
sc = m["onboarding_scenario"]


def slide(pdf, title, subtitle=None):
    fig = plt.figure(figsize=(13.33, 7.5))
    fig.text(0.05, 0.92, title, fontsize=24, fontweight="bold", color=INK, va="top")
    if subtitle:
        fig.text(0.05, 0.855, subtitle, fontsize=13, color=INK2, va="top")
    fig.text(0.05, 0.03, "Customer Retention & LTV Optimization | synthetic SaaS data, Jan 2024 to Dec 2025", fontsize=9, color=GREY)
    return fig


def tile(fig, x, y, value, label, color=BLUE):
    fig.text(x, y, value, fontsize=30, fontweight="bold", color=color)
    fig.text(x, y - 0.05, label, fontsize=11, color=INK2)


with PdfPages(ROOT / "docs" / "executive_deck.pdf") as pdf:
    # 1. headline
    f = slide(pdf, "Retention is the growth lever we are underusing",
              "We acquire customers efficiently in some channels, but lose a third of new logos inside six months.")
    tile(f, 0.05, 0.68, f"${m['mrr']/1e6:.2f}M", "MRR (Dec 2025)")
    tile(f, 0.27, 0.68, f"{m['active_customers']:,}", "active customers")
    tile(f, 0.47, 0.68, f"{m['avg_logo_churn_pct_6m']:.1f}%", "monthly logo churn", ORANGE)
    tile(f, 0.70, 0.68, f"{m['churn6m_overall']:.0f}%", "of new customers gone in 6 months", ORANGE)
    ax = f.add_axes([0.07, 0.12, 0.86, 0.38])
    ax.plot(kpi.month, kpi.mrr / 1e3, color=BLUE, lw=2.5)
    ax.set_ylim(0); ax.set_ylabel("MRR ($K)")
    ax.set_title("MRR grew fast, but ~$%.0fK of MRR churned in the last 6 months alone" % (m["churned_mrr_6m"] / 1e3), loc="left", fontsize=12, color=INK)
    pdf.savefig(f); plt.close(f)

    # 2. where revenue leaks
    f = slide(pdf, "New customers are the leakiest bucket",
              f"Only {m['retention_m6_pct']:.0f}% of a cohort is still paying at month 6 and {m['retention_m12_pct']:.0f}% at month 12.")
    ax = f.add_axes([0.07, 0.13, 0.40, 0.58])
    b = kpi.iloc[1:]
    ax.bar(b.month, b.new_mrr / 1e3, 22, color=BLUE, label="New")
    ax.bar(b.month, b.expansion_mrr / 1e3, 22, bottom=b.new_mrr / 1e3, color=AQUA, label="Expansion")
    ax.bar(b.month, -b.churned_mrr / 1e3, 22, color=ORANGE, label="Churned")
    ax.bar(b.month, -b.contraction_mrr / 1e3, 22, bottom=-b.churned_mrr / 1e3, color=YELLOW, label="Contraction")
    ax.axhline(0, color=GREY, lw=.8); ax.legend(frameon=False, ncol=2, fontsize=9); ax.set_title("MRR bridge ($K/month)", loc="left")
    ax2 = f.add_axes([0.56, 0.13, 0.38, 0.58])
    ax2.plot(b.month, b.logo_churn_pct, color=ORANGE, lw=2.5); ax2.set_ylim(0)
    ax2.set_title("Monthly logo churn (%)", loc="left")
    pdf.savefig(f); plt.close(f)

    # 3. why: onboarding
    f = slide(pdf, "Onboarding speed is the strongest early churn signal",
              f"Customers who finish onboarding within 3 days churn at {m['churn6m_fast']:.0f}% vs {m['churn6m_slow']:.0f}% for everyone else "
              f"(relative risk {m['rr_onboarding']:.1f}x, 95% CI {m['rr_lo']:.1f} to {m['rr_hi']:.1f}).")
    ax = f.add_axes([0.07, 0.13, 0.40, 0.58])
    ax.bar(onb.onboarding_bucket, onb.churn_6m_pct, color=[BLUE, GREY, GREY, ORANGE], width=.6)
    for i, v in enumerate(onb.churn_6m_pct):
        ax.text(i, v + 1, f"{v:.0f}%", ha="center", fontweight="bold")
    ax.set_title("6-month churn by onboarding speed", loc="left"); ax.set_ylim(0, 65)
    imp = pd.Series(m["feature_importance"]).sort_values()
    imp = imp[imp > 0.001]
    ax2 = f.add_axes([0.62, 0.13, 0.32, 0.58])
    ax2.barh(imp.index, imp.values, color=[BLUE if v > .1 else GREY for v in imp.values])
    ax2.set_title("Permutation importance (AUC drop)", loc="left")
    f.text(0.05, 0.075, f"Model: logistic regression AUC {m['auc_logit']:.2f}, random forest {m['auc_rf']:.2f} on a hold-out set (n = {m['n_model']:,} customers).",
           fontsize=10, color=INK2)
    pdf.savefig(f); plt.close(f)

    # 4. where to spend
    f = slide(pdf, "Not all acquisition dollars are equal",
              "Referral and organic return 6-8x their cost; paid social barely breaks even and takes a year to pay back.")
    ax = f.add_axes([0.12, 0.13, 0.36, 0.58])
    ax.barh(ue.channel, ue.ltv_to_cac, color=[ORANGE if v < 3 else BLUE for v in ue.ltv_to_cac])
    ax.axvline(3, color=GREY, ls="--", lw=1); ax.set_title("LTV : CAC (dashed = 3x)", loc="left")
    for i, v in enumerate(ue.ltv_to_cac):
        ax.text(v + .1, i, f"{v:.1f}x", va="center")
    ax2 = f.add_axes([0.60, 0.13, 0.34, 0.58])
    ax2.barh(ue.channel, ue.cac_payback_months, color=[ORANGE if v > 12 or r < 3 else BLUE for v, r in zip(ue.cac_payback_months, ue.ltv_to_cac)])
    ax2.axvline(12, color=GREY, ls="--", lw=1); ax2.set_title("CAC payback (months, dashed = 12)", loc="left")
    pdf.savefig(f); plt.close(f)

    # 5. recommendations
    r = m["reallocation"]
    f = slide(pdf, "Recommendations and expected impact", "In priority order; all figures are modelled estimates with stated assumptions.")
    rows = [
        ("1  Guided onboarding programme",
         f"Enrol {sc['assumptions']['share_converted']:.0%} of customers who miss the 3-day window ({sc['enrolled']:,} per year). "
         f"At a 50% haircut to the adjusted effect: ~{sc['retained_customers']} extra customers retained, 6-month churn down {sc['six_month_churn_reduction_pp']:.1f} pts, "
         f"${sc['gross_profit_retained']/1e3:.0f}K gross profit vs ${sc['program_cost']/1e3:.0f}K cost ({sc['roi_multiple']:.1f}x net ROI). Validate with a randomised pilot first."),
        ("2  Reallocate paid social to referral",
         f"Move 20% of 2025 paid-social spend (${r['moved_spend']/1e3:.0f}K). Net lifetime gross profit +${r['net_ltv']/1e6:.1f}M even assuming referral "
         f"converts at half its historical efficiency."),
        ("3  Win back at-risk accounts",
         f"{m['at_risk_customers']} high-value accounts ({m['at_risk_pct_mrr']:.1f}% of MRR, ${m['at_risk_mrr']/1e3:.0f}K/month) show falling recency and frequency. "
         f"Saving 20% protects ~${m['at_risk_save_20pct_annual']/1e3:.0f}K of annual revenue."),
        ("Next steps",
         "Run the onboarding pilot as an A/B test (see companion project for design and sizing); add a day-30 risk score to the CS queue; review paid-social creative and targeting before cutting further."),
    ]
    y = 0.74
    for head, body in rows:
        f.text(0.05, y, head, fontsize=15, fontweight="bold", color=BLUE if head[0].isdigit() else INK)
        import textwrap
        f.text(0.05, y - 0.04, "\n".join(textwrap.wrap(body, 130)), fontsize=11.5, color=INK2, va="top", linespacing=1.4)
        y -= 0.19
    pdf.savefig(f); plt.close(f)
print("wrote docs/executive_deck.pdf")
