"""Build dashboard/index.html: a self-contained, interactive executive + diagnostic dashboard.

No server or CDN needed: data is embedded as JSON and charts are drawn with inline SVG.
The same extracts in dashboard/data/ can be loaded into Tableau Public / Power BI
(see dashboard/interactive_link.txt).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "dashboard" / "data"

seg = pd.read_csv(D / "kpi_monthly_segmented.csv")
seg["month"] = seg["month"].str[:7]
coh = pd.read_csv(D / "cohort_retention.csv")
coh["cohort_month"] = coh["cohort_month"].str[:7]
payload = {
    "seg": seg.to_dict(orient="records"),
    "cohort": coh[["cohort_month", "months_since_signup", "logo_retention_pct"]].to_dict(orient="records"),
    "channels": pd.read_csv(D / "unit_economics_by_channel.csv").to_dict(orient="records"),
    "onboarding": pd.read_csv(D / "onboarding_churn.csv").to_dict(orient="records"),
    "importance": pd.read_csv(D / "feature_importance.csv").to_dict(orient="records"),
    "metrics": json.loads((ROOT / "results" / "metrics.json").read_text()),
}

TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Retention &amp; LTV Dashboard</title>
<style>
:root{--bg:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--grid:#e6e5e1;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--muted:#8a8985}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121211;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#34332f;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--muted:#8a8985}}
:root[data-theme="dark"]{--bg:#121211;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#34332f;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--muted:#8a8985}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:22px;margin:0}h2{font-size:15px;margin:0 0 2px}.sub{color:var(--ink2);margin:2px 0 14px}
.bar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:8px 0 16px}
select,button{background:var(--card);color:var(--ink);border:1px solid var(--grid);border-radius:8px;padding:6px 10px;font:inherit}
label{color:var(--ink2);font-size:12px;display:flex;gap:6px;align-items:center}
.tabs button.on{border-color:var(--s1);color:var(--s1);font-weight:600}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:14px}
.tile,.card{background:var(--card);border:1px solid var(--grid);border-radius:12px;padding:14px}
.tile .v{font-size:26px;font-weight:700}.tile .l{color:var(--ink2);font-size:12px}.tile .d{font-size:12px;color:var(--ink2)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:12px}
.card p{margin:0 0 8px;color:var(--ink2);font-size:12px}
svg{width:100%;height:auto;display:block}svg text{fill:var(--ink2);font-size:11px}
.leg{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin-top:6px}.leg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:4px 6px;text-align:right;border-bottom:1px solid var(--grid)}th:first-child,td:first-child{text-align:left}
.heat td{padding:0;height:15px;min-width:20px;border:1px solid var(--bg)}
#tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--grid);border-radius:8px;padding:6px 9px;font-size:12px;display:none;box-shadow:0 4px 14px rgba(0,0,0,.15);z-index:9}
.hide{display:none}.note{font-size:12px;color:var(--ink2);margin-top:18px}
</style></head><body><div class="wrap">
<h1>Customer Retention &amp; LTV</h1>
<div class="sub">Synthetic SaaS billing data, Jan 2024 to Dec 2025. Snapshot: <b id="snap"></b></div>
<div class="bar">
 <div class="tabs"><button id="t1" class="on">Executive summary</button> <button id="t2">Diagnostics</button></div>
 <label>Region <select id="fr"></select></label>
 <label>Plan at signup <select id="fp"></select></label>
 <button id="theme">Toggle theme</button>
</div>

<section id="exec">
 <div class="tiles" id="tiles"></div>
 <div class="grid">
  <div class="card"><h2>Monthly recurring revenue</h2><p>Hover for values. Responds to the filters above.</p><svg id="c_mrr" viewBox="0 0 560 250"></svg></div>
  <div class="card"><h2>MRR bridge</h2><p>New and expansion revenue above the line; churn and contraction below.</p><svg id="c_bridge" viewBox="0 0 560 250"></svg>
   <div class="leg"><span><i style="background:var(--s1)"></i>New</span><span><i style="background:var(--s3)"></i>Expansion</span><span><i style="background:var(--s2)"></i>Churned</span><span><i style="background:var(--s4)"></i>Contraction</span></div></div>
  <div class="card"><h2>Monthly logo churn</h2><p>Share of last month's customers who left.</p><svg id="c_churn" viewBox="0 0 560 250"></svg></div>
 </div>
</section>

<section id="diag" class="hide">
 <div class="grid">
  <div class="card" style="grid-column:1/-1"><h2>Cohort retention heatmap</h2><p>% of each signup cohort still paying, by months since signup (all regions and plans).</p><div style="overflow:auto"><table class="heat" id="heat"></table></div></div>
  <div class="card"><h2>6-month churn by onboarding speed</h2><p>Customers finishing onboarding within 3 days churn at a fraction of the rate of everyone else.</p><svg id="c_onb" viewBox="0 0 560 250"></svg></div>
  <div class="card"><h2>What predicts early churn?</h2><p>Permutation importance on a hold-out set (drop in AUC when shuffled).</p><svg id="c_imp" viewBox="0 0 560 250"></svg></div>
  <div class="card"><h2>LTV : CAC by channel</h2><p>Dashed line marks the 3x rule of thumb.</p><svg id="c_ltv" viewBox="0 0 560 250"></svg></div>
  <div class="card"><h2>Channel unit economics</h2><table id="uetab"></table></div>
 </div>
</section>
<div class="note">Slicers filter the Executive view. Diagnostic views are computed on the full customer base. Definitions and assumptions: <code>docs/business_requirements.md</code>.</div>
</div><div id="tip"></div>
<script>
const DATA = __DATA__;
const $ = s => document.querySelector(s), NS = "http://www.w3.org/2000/svg";
const fmtK = v => v >= 1e6 ? "$" + (v/1e6).toFixed(2) + "M" : "$" + (v/1e3).toFixed(0) + "K";
const fmtN = v => v.toLocaleString("en-US");
const months = [...new Set(DATA.seg.map(r => r.month))].sort();
const regions = ["All", ...new Set(DATA.seg.map(r => r.region))].sort((a,b)=>a==="All"?-1:b==="All"?1:a.localeCompare(b));
const plans = ["All", "Starter", "Growth", "Enterprise"];
$("#fr").innerHTML = regions.map(r => `<option>${r}</option>`).join("");
$("#fp").innerHTML = plans.map(r => `<option>${r}</option>`).join("");
$("#snap").textContent = months[months.length-1];

function series() {
  const fr = $("#fr").value, fp = $("#fp").value;
  const rows = DATA.seg.filter(r => (fr==="All"||r.region===fr) && (fp==="All"||r.plan_at_signup===fp));
  return months.map((m,i) => {
    const s = rows.filter(r => r.month===m).reduce((a,r)=>{for(const k of ["active_customers","mrr","new_customers","new_mrr","expansion_mrr","contraction_mrr","churned_customers","churned_mrr"]) a[k]=(a[k]||0)+r[k]; return a;}, {});
    s.month = m; return s;
  }).map((s,i,arr) => {
    const p = arr[i-1];
    s.logo_churn = p && p.active_customers ? 100*s.churned_customers/p.active_customers : null;
    s.nrr = p && p.mrr ? 100*(p.mrr + s.expansion_mrr - s.contraction_mrr - s.churned_mrr)/p.mrr : null;
    s.arpa = s.active_customers ? s.mrr/s.active_customers : 0; return s;
  });
}
const tip = $("#tip");
function showTip(e, html){ tip.innerHTML = html; tip.style.display="block"; tip.style.left=Math.min(e.clientX+14, innerWidth-200)+"px"; tip.style.top=(e.clientY+14)+"px"; }
function hideTip(){ tip.style.display="none"; }
function el(tag, attrs, parent){ const n=document.createElementNS(NS,tag); for(const k in attrs) n.setAttribute(k,attrs[k]); parent&&parent.appendChild(n); return n; }
function clear(svg){ svg.innerHTML=""; }
const W=560,H=250,M={l:48,r:12,t:10,b:28};

function axes(svg, xs, ymin, ymax, yfmt, nx){
  const iw=W-M.l-M.r, ih=H-M.t-M.b;
  const y = v => M.t + ih*(1-(v-ymin)/(ymax-ymin)), x = i => M.l + iw*(xs.length>1? i/(xs.length-1):0.5);
  for(let k=0;k<=4;k++){ const v=ymin+(ymax-ymin)*k/4; el("line",{x1:M.l,x2:W-M.r,y1:y(v),y2:y(v),stroke:"var(--grid)"},svg);
    const t=el("text",{x:M.l-6,y:y(v)+4,"text-anchor":"end"},svg); t.textContent=yfmt(v); }
  const step=Math.ceil(xs.length/(nx||6));
  xs.forEach((l,i)=>{ if(i%step===0){ const t=el("text",{x:x(i),y:H-8,"text-anchor":"middle"},svg); t.textContent=l; } });
  return {x,y,iw,ih};
}
function lineChart(id, data, key, color, yfmt, ymin0){
  const svg=$(id); clear(svg);
  const pts = data.map((d,i)=>({i,v:d[key],m:d.month})).filter(p=>p.v!=null);
  const vals = pts.map(p=>p.v); const ymax = Math.max(...vals)*1.1; const ymin = ymin0===undefined?0:ymin0;
  const a = axes(svg, data.map(d=>d.month.slice(2)), ymin, ymax, yfmt, 6);
  el("path",{d:pts.map((p,j)=>(j?"L":"M")+a.x(p.i)+","+a.y(p.v)).join(" "),fill:"none",stroke:color,"stroke-width":2},svg);
  const cross=el("line",{y1:M.t,y2:H-M.b,stroke:"var(--muted)","stroke-dasharray":"3 3",opacity:0},svg), dot=el("circle",{r:4,fill:color,stroke:"var(--card)","stroke-width":2,opacity:0},svg);
  const hit=el("rect",{x:M.l,y:M.t,width:a.iw,height:a.ih,fill:"transparent"},svg);
  hit.onmousemove=e=>{const r=svg.getBoundingClientRect(); const px=(e.clientX-r.left)/r.width*W; let best=pts[0]; for(const p of pts) if(Math.abs(a.x(p.i)-px)<Math.abs(a.x(best.i)-px)) best=p;
    cross.setAttribute("x1",a.x(best.i)); cross.setAttribute("x2",a.x(best.i)); cross.setAttribute("opacity",1);
    dot.setAttribute("cx",a.x(best.i)); dot.setAttribute("cy",a.y(best.v)); dot.setAttribute("opacity",1); showTip(e,`<b>${best.m}</b><br>${yfmt(best.v)}`);};
  hit.onmouseleave=()=>{cross.setAttribute("opacity",0);dot.setAttribute("opacity",0);hideTip();};
}
function bridge(data){
  const svg=$("#c_bridge"); clear(svg); const d=data.slice(1);
  const pos=d.map(r=>r.new_mrr+r.expansion_mrr), neg=d.map(r=>r.churned_mrr+r.contraction_mrr);
  const ymax=Math.max(...pos)*1.1, ymin=-Math.max(...neg)*1.2;
  const a=axes(svg,d.map(r=>r.month.slice(2)),ymin,ymax,fmtK,6); const bw=a.iw/d.length*0.7;
  d.forEach((r,i)=>{ const x=a.x(i)-bw/2; let y0=a.y(0);
    [["new_mrr","var(--s1)"],["expansion_mrr","var(--s3)"]].forEach(([k,c])=>{ const h=a.y(0)-a.y(r[k]); y0-=h; if(h>0){const b=el("rect",{x,y:y0,width:bw,height:Math.max(h-1,0),fill:c,rx:1},svg); b.onmousemove=e=>showTip(e,`<b>${r.month}</b><br>${k.replace("_mrr","")}: ${fmtK(r[k])}`); b.onmouseleave=hideTip;}});
    let y1=a.y(0);
    [["churned_mrr","var(--s2)"],["contraction_mrr","var(--s4)"]].forEach(([k,c])=>{ const h=a.y(-r[k])-a.y(0); if(h>0){const b=el("rect",{x,y:y1,width:bw,height:Math.max(h-1,0),fill:c,rx:1},svg); b.onmousemove=e=>showTip(e,`<b>${r.month}</b><br>${k.replace("_mrr","")}: -${fmtK(r[k])}`); b.onmouseleave=hideTip;} y1+=h;});
  });
}
function hbars(id, rows, vfmt, color, refLine, colorFn){
  const svg=$(id); clear(svg); const lw=140, max=Math.max(...rows.map(r=>r.v), refLine||0)*1.15, bh=Math.min(34,(H-20)/rows.length-8);
  rows.forEach((r,i)=>{ const y=10+i*((H-20)/rows.length); const w=(W-lw-60)*r.v/max;
    const t=el("text",{x:lw-8,y:y+bh/2+4,"text-anchor":"end"},svg); t.textContent=r.label;
    const b=el("rect",{x:lw,y,width:Math.max(w,0),height:bh,fill:colorFn?colorFn(r):color,rx:3},svg);
    const v=el("text",{x:lw+w+6,y:y+bh/2+4},svg); v.textContent=vfmt(r.v);
    b.onmousemove=e=>showTip(e,`<b>${r.label}</b><br>${r.tip||vfmt(r.v)}`); b.onmouseleave=hideTip; });
  if(refLine){ const x=lw+(W-lw-60)*refLine/max; el("line",{x1:x,x2:x,y1:4,y2:H-6,stroke:"var(--muted)","stroke-dasharray":"4 3"},svg); }
}
function render(){
  const s=series(), last=s[s.length-1], prev=s[s.length-2], yr=s[s.length-13];
  const avg6=s.slice(-6).reduce((a,r)=>a+r.logo_churn,0)/6, nrr6=s.slice(-6).reduce((a,r)=>a+r.nrr,0)/6;
  const tiles=[["MRR",fmtK(last.mrr),`${(100*(last.mrr/yr.mrr-1)).toFixed(0)}% vs 12 months ago`],["ARR",fmtK(last.mrr*12),"MRR x 12"],
    ["Active customers",fmtN(last.active_customers),`${(last.active_customers-prev.active_customers>=0?"+":"")}${last.active_customers-prev.active_customers} vs prior month`],
    ["ARPA",`$${last.arpa.toFixed(0)}`,"per customer per month"],["Logo churn (6-mo avg)",avg6.toFixed(1)+"%","monthly"],["Net revenue retention",nrr6.toFixed(1)+"%","monthly, 6-mo avg"]];
  $("#tiles").innerHTML=tiles.map(t=>`<div class="tile"><div class="l">${t[0]}</div><div class="v">${t[1]}</div><div class="d">${t[2]}</div></div>`).join("");
  lineChart("#c_mrr",s,"mrr","var(--s1)",fmtK);
  bridge(s);
  lineChart("#c_churn",s.slice(1),"logo_churn","var(--s2)",v=>v.toFixed(1)+"%");
}
function diagnostics(){
  // cohort heatmap
  const cm=[...new Set(DATA.cohort.map(r=>r.cohort_month))].sort(), maxM=Math.max(...DATA.cohort.map(r=>r.months_since_signup));
  const map={}; DATA.cohort.forEach(r=>map[r.cohort_month+"|"+r.months_since_signup]=r.logo_retention_pct);
  let h="<tr><th>Cohort</th>"+Array.from({length:maxM+1},(_,i)=>`<th>${i}</th>`).join("")+"</tr>";
  cm.forEach(c=>{ h+=`<tr><td>${c}</td>`; for(let i=0;i<=maxM;i++){ const v=map[c+"|"+i];
    if(v===undefined) h+="<td></td>"; else { const t=(v-30)/70; h+=`<td data-v="${c}|${i}|${v}" style="background:color-mix(in srgb,var(--s1) ${Math.round(15+t*85)}%,var(--card))"></td>`; } } h+="</tr>"; });
  $("#heat").innerHTML=h;
  document.querySelectorAll("#heat td[data-v]").forEach(td=>{ td.onmousemove=e=>{const [c,i,v]=td.dataset.v.split("|"); showTip(e,`<b>${c}</b>, month ${i}<br>${(+v).toFixed(1)}% retained`)}; td.onmouseleave=hideTip; });
  hbars("#c_onb", DATA.onboarding.map(r=>({label:r.onboarding_bucket,v:r.churn_6m_pct,tip:`${r.customers} customers`})), v=>v.toFixed(0)+"%", "var(--muted)", 0, r=>r.label==="Within 3 days"?"var(--s1)":(r.label==="Never completed"?"var(--s2)":"var(--muted)"));
  hbars("#c_imp", DATA.importance.filter(r=>r.auc_drop>0.001).map(r=>({label:r.feature,v:r.auc_drop})), v=>v.toFixed(3), "var(--s1)");
  const ch=[...DATA.channels].sort((a,b)=>b.ltv_to_cac-a.ltv_to_cac);
  hbars("#c_ltv", ch.map(r=>({label:r.channel,v:r.ltv_to_cac,tip:`LTV $${fmtN(r.ltv)}, CAC $${fmtN(Math.round(r.cac))}`})), v=>v.toFixed(1)+"x", "var(--s1)", 3, r=>r.v<3?"var(--s2)":"var(--s1)");
  $("#uetab").innerHTML="<tr><th>Channel</th><th>CAC</th><th>ARPA</th><th>Churn/mo</th><th>LTV</th><th>Payback (mo)</th></tr>"+ch.map(r=>`<tr><td>${r.channel}</td><td>$${fmtN(Math.round(r.cac))}</td><td>$${r.arpa.toFixed(0)}</td><td>${r.monthly_churn_pct.toFixed(1)}%</td><td>$${fmtN(r.ltv)}</td><td>${r.cac_payback_months.toFixed(1)}</td></tr>`).join("");
}
["#fr","#fp"].forEach(s=>$(s).onchange=render);
$("#t1").onclick=()=>{$("#exec").classList.remove("hide");$("#diag").classList.add("hide");$("#t1").classList.add("on");$("#t2").classList.remove("on");};
$("#t2").onclick=()=>{$("#diag").classList.remove("hide");$("#exec").classList.add("hide");$("#t2").classList.add("on");$("#t1").classList.remove("on");};
$("#theme").onclick=()=>{const r=document.documentElement; const dark=(r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches); r.dataset.theme=dark?"light":"dark";};
render(); diagnostics();
</script></body></html>
"""

html = TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
(ROOT / "dashboard" / "index.html").write_text(html)
print("wrote dashboard/index.html", f"{len(html)/1024:.0f} KB")
