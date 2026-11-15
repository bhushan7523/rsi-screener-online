"""Builds a self-contained HTML dashboard (no internet needed to view it) from screener results."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

LAYOUT_VERSION = "5"  # bump when the page design changes

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="rsi-layout" content="__LAYOUT__">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RSI Screener · __DATE__</title>
<style>
:root{--bg:#f7f7f5;--panel:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e4e3de;--ok:#1f8a4c;--bad:#c2410c;--mid:#8a8a84;--okbg:rgba(31,138,76,.08);--badbg:rgba(194,65,12,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--panel:#1f1f1d;--fg:#ededea;--muted:#a3a39d;--line:#34342f;--ok:#4ade80;--bad:#fb923c;--mid:#8f8f88;--okbg:rgba(74,222,128,.08);--badbg:rgba(251,146,60,.09)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:28px 20px 48px;display:flex;flex-direction:column;gap:20px}
h1{font:400 30px/1.15 Georgia,"Times New Roman",serif;margin:0}
.sub{color:var(--muted);margin:6px 0 0}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}
.card{cursor:pointer;transition:border-color .15s}
.card.on{border-color:var(--fg)}
.card h3{margin:0;font-size:13px;font-weight:600;color:var(--muted)}
.big{font:400 40px/1.1 Georgia,serif;margin-top:4px;font-variant-numeric:tabular-nums}
.rule{font-size:12px;color:var(--muted)}
.bull .big{color:var(--ok)}.bear .big{color:var(--bad)}
.panel h2{margin:0 0 12px;font-size:17px;font-weight:600}
.chart{position:relative}
.chart svg text{fill:var(--muted);font-size:12px}
.chart svg .lbl{fill:var(--fg)}
.tip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--line);box-shadow:0 4px 14px rgba(0,0,0,.12);border-radius:8px;padding:6px 10px;font-size:12px;white-space:nowrap;display:none}
.tablewrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-size:12px;color:var(--muted);font-weight:600;cursor:pointer;user-select:none}
th.num,td.num{text-align:right}
.pill{display:inline-block;padding:1px 10px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid}
.pill.Bullish{color:var(--ok);border-color:var(--ok)}
.pill.Bearish{color:var(--bad);border-color:var(--bad)}
.pill.Sideways{color:var(--muted);border-color:var(--line)}
.up{color:var(--ok)}.down{color:var(--bad)}
.note{font-size:12px;color:var(--muted)}
.src{font-size:11px;color:var(--muted)}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
.refresh{font:600 14px/1 inherit;font-family:inherit;padding:10px 16px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--fg);cursor:pointer}
.refresh:hover{border-color:var(--fg)}
.refresh[disabled]{opacity:.6;cursor:wait}
.rstat{font-size:12px;color:var(--muted);margin-top:6px;text-align:right}
.dash-src{font:inherit;font-size:13px;padding:8px 10px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--fg);margin-left:4px}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div><h1>RSI Screener</h1><p class="sub" id="summary"></p></div>
    <div id="rbox" hidden><label class="rstat" style="margin:0 8px 0 0">Fetch from <select class="dash-src" id="srcsel"></select></label><button class="refresh" id="refresh">Refresh data</button><div class="rstat" id="rstat">Last fetched __GENERATED__</div></div>
  </header>
  <section class="panel" id="limits" hidden>
    <h2>Data source &amp; limits</h2>
    <div class="tablewrap"><table id="ltbl">
      <thead><tr><th>Source</th><th>Status</th><th class="num">Calls today</th><th class="num">Daily limit</th><th class="num">Left today</th><th>Notes</th></tr></thead>
      <tbody></tbody>
    </table></div>
    <p class="note" style="margin:10px 0 0">Calls are counted on this Mac and reset at midnight. Yahoo uses 1 call per refresh for all stocks; Tapetide and Angel One use 1 call per stock.</p>
  </section>
  <section class="cards">
    <div class="card bull" data-f="Bullish"><h3>Bullish</h3><div class="big" id="n-Bullish">0</div><div class="rule">RSI above 60</div></div>
    <div class="card" data-f="Sideways"><h3>Sideways</h3><div class="big" id="n-Sideways">0</div><div class="rule">RSI 40 to 60</div></div>
    <div class="card bear" data-f="Bearish"><h3>Bearish</h3><div class="big" id="n-Bearish">0</div><div class="rule">RSI below 40</div></div>
  </section>
  <section class="panel">
    <h2>RSI by stock</h2>
    <div class="chart" id="chart"></div>
  </section>
  <section class="panel">
    <h2>Signals</h2>
    <div class="tablewrap"><table id="tbl">
      <thead><tr>
        <th data-k="symbol">Stock</th><th data-k="close" class="num">Close (₹)</th>
        <th data-k="rsi" class="num">RSI</th><th data-k="change" class="num">Change</th>
        <th data-k="signal">Signal</th><th>Last 60 days of RSI</th><th data-k="date">Date</th>
      </tr></thead><tbody></tbody>
    </table></div>
  </section>
  <p class="note">Daily RSI(14) on closing prices. Click a card to filter; click a column to sort. Data: __SOURCE__. Generated __GENERATED__. A screen, not trading advice.</p>
</div>
<div class="tip" id="tip"></div>
<script>
const DATA = __DATA__;
const LO = 40, HI = 60;
let filter = null, sortK = "rsi", sortDir = -1;
const fmt = (v, d=2) => v == null ? "—" : Number(v).toLocaleString("en-IN", {minimumFractionDigits:d, maximumFractionDigits:d});
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const col = s => s === "Bullish" ? css("--ok") : s === "Bearish" ? css("--bad") : css("--mid");
const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs={}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };

DATA.rows.forEach(r => r.change = r.prev_rsi == null ? null : +(r.rsi - r.prev_rsi).toFixed(2));

function summary() {
  const s = DATA.rows.slice().sort((a,b) => b.rsi - a.rsi);
  const hi = s[0], lo = s[s.length-1];
  document.getElementById("summary").textContent =
    `${DATA.rows.length} stocks · strongest ${hi.symbol} (${fmt(hi.rsi)}), weakest ${lo.symbol} (${fmt(lo.rsi)}) · data as of ${DATA.asof}`;
  for (const k of ["Bullish","Sideways","Bearish"])
    document.getElementById("n-"+k).textContent = DATA.rows.filter(r => r.signal === k).length;
}

function rows() { return DATA.rows.filter(r => !filter || r.signal === filter); }

function chart() {
  const box = document.getElementById("chart"); box.innerHTML = "";
  const data = rows().slice().sort((a,b) => b.rsi - a.rsi);
  if (!data.length) { box.textContent = "No stocks in this group."; return; }
  const W = Math.max(300, box.clientWidth), bh = 28, top = 22, bottom = 26;
  const svg = el("svg", {viewBox:`0 0 ${W} ${top + data.length*bh + bottom}`, width:"100%", role:"img", "aria-label":"RSI per stock with 40 and 60 lines"}, box);
  const probe = el("text", {class:"lbl"}, svg); let lw = 0;
  data.forEach(r => { probe.textContent = r.symbol; lw = Math.max(lw, probe.getComputedTextLength()); }); probe.remove();
  const L = lw + 14, R = W - 44, x = v => L + (R - L) * v / 100, H = top + data.length*bh;
  el("rect", {x:x(0), y:top, width:x(LO)-x(0), height:data.length*bh, fill:css("--badbg")}, svg);
  el("rect", {x:x(HI), y:top, width:x(100)-x(HI), height:data.length*bh, fill:css("--okbg")}, svg);
  for (const v of [0,20,40,60,80,100]) {
    const t = el("text", {x:x(v), y:H+18, "text-anchor":"middle"}, svg); t.textContent = v;
  }
  for (const v of [LO,HI]) {
    el("line", {x1:x(v), x2:x(v), y1:top-4, y2:H, stroke:css("--mid"), "stroke-dasharray":"4 3"}, svg);
    const t = el("text", {x:x(v), y:top-8, "text-anchor":"middle"}, svg); t.textContent = v;
  }
  const tip = document.getElementById("tip");
  data.forEach((r,i) => {
    const y = top + i*bh;
    const t = el("text", {x:L-8, y:y+bh/2, dy:"0.35em", "text-anchor":"end", class:"lbl"}, svg); t.textContent = r.symbol;
    el("rect", {x:x(0), y:y+5, width:Math.max(1, x(r.rsi)-x(0)), height:bh-10, rx:3, fill:col(r.signal)}, svg);
    const v = el("text", {x:x(r.rsi)+5, y:y+bh/2, dy:"0.35em"}, svg); v.textContent = fmt(r.rsi,1);
    const hit = el("rect", {x:0, y, width:W, height:bh, fill:"transparent"}, svg);
    hit.addEventListener("pointermove", ev => {
      tip.textContent = `${r.symbol}: RSI ${fmt(r.rsi)} (prev ${fmt(r.prev_rsi)}) · ${r.signal} · ₹${fmt(r.close)}`;
      tip.style.display = "block";
      tip.style.left = Math.min(ev.pageX + 12, window.scrollX + document.documentElement.clientWidth - tip.offsetWidth - 8) + "px";
      tip.style.top = (ev.pageY + 14) + "px";
    });
    hit.addEventListener("pointerleave", () => tip.style.display = "none");
  });
}

function spark(hist) {
  const w = 120, h = 28, svg = el("svg", {width:w, height:h, viewBox:`0 0 ${w} ${h}`, role:"img", "aria-label":"RSI over the last 60 days"});
  if (!hist || hist.length < 2) return svg;
  const y = v => h - 2 - (h - 4) * v / 100, x = i => 2 + (w - 4) * i / (hist.length - 1);
  el("rect", {x:0, y:y(HI), width:w, height:y(LO)-y(HI), fill:css("--line"), opacity:.5}, svg);
  el("polyline", {points:hist.map((v,i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" "), fill:"none", stroke:css("--fg"), "stroke-width":1.4}, svg);
  const last = hist[hist.length-1];
  el("circle", {cx:x(hist.length-1), cy:y(last), r:2.6, fill:col(last > HI ? "Bullish" : last < LO ? "Bearish" : "Sideways")}, svg);
  return svg;
}

function table() {
  const tb = document.querySelector("#tbl tbody"); tb.innerHTML = "";
  const data = rows().slice().sort((a,b) => (a[sortK] > b[sortK] ? 1 : a[sortK] < b[sortK] ? -1 : 0) * sortDir);
  for (const r of data) {
    const tr = document.createElement("tr");
    const td = (t, c) => { const d = document.createElement("td"); if (c) d.className = c; if (t instanceof Node) d.appendChild(t); else d.textContent = t; tr.appendChild(d); return d; };
    const s = td(r.symbol); if (r.source && r.source !== DATA.source) { const sm = document.createElement("div"); sm.className = "src"; sm.textContent = "via " + r.source; s.appendChild(sm); }
    td(fmt(r.close), "num");
    td(fmt(r.rsi), "num");
    td(r.change == null ? "—" : (r.change > 0 ? "+" : "") + fmt(r.change), "num " + (r.change > 0 ? "up" : r.change < 0 ? "down" : ""));
    const p = document.createElement("span"); p.className = "pill " + r.signal; p.textContent = r.signal; td(p);
    td(spark(DATA.history[r.symbol]));
    td(new Date(r.date + "T00:00:00").toLocaleDateString("en-IN", {day:"2-digit", month:"short", year:"numeric"}));
    tb.appendChild(tr);
  }
}

function render() { chart(); table(); }

document.querySelectorAll(".card").forEach(c => c.addEventListener("click", () => {
  filter = filter === c.dataset.f ? null : c.dataset.f;
  document.querySelectorAll(".card").forEach(x => x.classList.toggle("on", x.dataset.f === filter));
  render();
}));
document.querySelectorAll("th[data-k]").forEach(th => th.addEventListener("click", () => {
  const k = th.dataset.k;
  if (sortK === k) sortDir *= -1; else { sortK = k; sortDir = (k === "symbol" || k === "signal" || k === "date") ? 1 : -1; }
  table();
}));
let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(chart, 120); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
summary(); render();
function setupControls(d, onRefresh, noteLine) {
  const box = document.getElementById("rbox"), btn = document.getElementById("refresh"), st = document.getElementById("rstat"), sel = document.getElementById("srcsel");
  box.hidden = false;
  for (const o of d.sources) {
    const op = new Option(o.label + (o.ready ? "" : " (not set up)"), o.id);
    op.disabled = !o.ready; op.title = o.note; sel.add(op);
  }
  sel.value = d.last;
  const showQuota = () => {
    const o = d.sources.find(x => x.id === sel.value);
    if (o) st.textContent = `${o.label}: ${o.quota} · Last fetched __GENERATED__` + (noteLine ? ` · ${noteLine}` : "");
  };
  sel.addEventListener("change", showQuota); showQuota();
  const lt = document.querySelector("#ltbl tbody"); lt.innerHTML = "";
  for (const o of d.sources) {
    const q = o.usage || {};
    const tr = document.createElement("tr");
    const cells = [o.label + (o.id === d.last ? "  (selected)" : ""),
      o.ready ? "Ready" : "Not set up",
      String(q.calls ?? 0),
      q.plan_based ? "Set by plan" : q.limit == null ? "No limit" : String(q.limit),
      q.plan_based ? "—" : q.limit == null && q.remaining == null ? "Unlimited" : String(q.remaining ?? "—"),
      o.note + (q.resets ? ` · resets ${new Date(q.resets).toLocaleTimeString("en-IN", {hour: "2-digit", minute: "2-digit"})}` : "")];
    cells.forEach((t, i) => { const td = document.createElement("td"); td.textContent = t; if (i >= 2 && i <= 4) td.className = "num"; tr.appendChild(td); });
    lt.appendChild(tr);
  }
  document.getElementById("limits").hidden = false;
  btn.addEventListener("click", () => onRefresh(sel.value, btn, st));
}

if (["127.0.0.1", "localhost"].includes(location.hostname)) {
  // On the Mac: the local server fetches new data.
  fetch("/sources").then(r => r.json()).then(d => setupControls(d, async (source, btn, st) => {
    btn.disabled = true; btn.textContent = "Fetching…"; st.textContent = "Getting fresh prices (about 20 seconds)";
    try {
      const r = await fetch("/refresh", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({source})});
      if (r.ok) { location.reload(); return; }
      st.textContent = r.status === 409 ? "Already refreshing…" : "Refresh failed: " + (await r.text()).slice(-160);
    } catch (e) { st.textContent = "Can't reach the dashboard server. Is its Terminal window still open?"; }
    btn.disabled = false; btn.textContent = "Refresh data";
  })).catch(() => {});
} else if (DATA.online) {
  // Online (GitHub Pages): updates run on GitHub; the button opens the "Run workflow" page.
  const on = DATA.online;
  setupControls(on, (source, btn, st) => {
    window.open(on.run_url, "_blank", "noopener");
    st.textContent = "On GitHub, press \u201cRun workflow\u201d. Reload this page in about 2 minutes.";
  }, on.schedule);
  document.getElementById("refresh").title = "Opens GitHub to run an update";
}
</script>
</body>
</html>
"""


def _now_ist() -> str:
    """Current time in India (GitHub's servers run on UTC)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return datetime.now().strftime("%d %b %Y, %I:%M %p")


def payload_from_html(html: str) -> dict | None:
    """Recover the saved data from an existing dashboard.html."""
    m = re.search(r"const DATA = (\{.*?\});\nconst LO", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1).replace("<\\/", "</"))
    except ValueError:
        return None


def build_html_from_payload(payload: dict, generated: str | None = None) -> str:
    data_json = json.dumps(payload, default=str).replace("</", "<\\/")
    return (TEMPLATE
            .replace("__LAYOUT__", LAYOUT_VERSION)
            .replace("__DATA__", data_json)
            .replace("__SOURCE__", payload.get("source", ""))
            .replace("__DATE__", payload.get("asof", ""))
            .replace("__GENERATED__", generated or payload.get("generated") or _now_ist()))


def build_html(df, history: dict, source: str) -> str:
    rows = df.to_dict(orient="records")
    payload = {
        "rows": rows,
        "history": history,
        "source": source,
        "asof": max(r["date"] for r in rows) if rows else "",
        "generated": _now_ist(),
    }
    online = online_info(source)
    if online:
        payload["online"] = online
    return build_html_from_payload(payload)


def online_info(source_label: str) -> dict | None:
    """When built on GitHub Actions, describe sources, limits and the refresh link for the online page."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    import usage
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sources = [
        {"id": "yahoo", "label": "Yahoo Finance", "ready": True, "note": "Free, no limit · used for online updates"},
        {"id": "tapetide", "label": "Tapetide", "ready": False, "note": "Not set up online (needs a paid plan)"},
        {"id": "angel", "label": "Angel One", "ready": False, "note": "Not set up online (needs an Angel One account)"},
    ]
    for o in sources:
        u = usage.summary(o["id"])
        o["usage"], o["quota"] = u, u["text"]
    return {
        "sources": sources,
        "last": "yahoo",
        "run_url": f"https://github.com/{repo}/actions/workflows/publish.yml" if repo else "",
        "schedule": "Auto-updates Mon–Fri 4:47 PM IST",
    }
