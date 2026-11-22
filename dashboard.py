"""Builds a self-contained HTML dashboard (no internet needed to view it) from screener results."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

LAYOUT_VERSION = "13"  # bump when the page design changes

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
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 48px;display:flex;flex-direction:column;gap:20px}
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
.tf{display:inline-flex;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--panel)}
.tf button{font:600 13px/1 inherit;font-family:inherit;padding:9px 16px;border:0;background:transparent;color:var(--muted);cursor:pointer}
.tf button+button{border-left:1px solid var(--line)}
.tf button.on{background:var(--fg);color:var(--bg)}
.bar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.cell{display:inline-flex;align-items:center;gap:8px;justify-content:flex-end}
.cell .pill{min-width:72px;text-align:center}
.pill.sm{padding:0 7px;font-size:11px;min-width:0}
.star{background:none;border:0;cursor:pointer;font-size:18px;line-height:1;color:var(--mid);padding:2px 4px}
.star.on{color:#d4a017}
.agree{font-size:12px;color:var(--muted)}
.agree.full.Bullish{color:var(--ok);font-weight:600}.agree.full.Bearish{color:var(--bad);font-weight:600}
.favgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.fav{border:1px solid var(--line);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:8px;background:var(--bg)}
.fav .hd{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.fav .sym{font-weight:700;font-size:15px}
.fav .px{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13px}
.tfrow{display:grid;grid-template-columns:22px 1fr 44px 70px;align-items:center;gap:8px;font-size:12px;font-variant-numeric:tabular-nums}
.tfrow .lab{color:var(--muted);font-weight:600}
.gauge{position:relative;height:8px;border-radius:4px;background:linear-gradient(90deg,var(--badbg) 0 40%,var(--line) 40% 60%,var(--okbg) 60% 100%)}
.gauge i{position:absolute;top:-3px;width:3px;height:14px;border-radius:2px;transform:translateX(-50%)}
.favhd{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.favmsg{font-size:12px;color:var(--bad);min-height:1em}
.empty{color:var(--muted);font-size:14px;padding:6px 0}
.search{position:relative}
.search input{width:100%;font:inherit;font-size:16px;padding:12px 14px 12px 40px;border-radius:12px;border:1px solid var(--line);background:var(--panel);color:var(--fg)}
.search input:focus{outline:none;border-color:var(--fg)}
.search .ic{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none}
.results{margin-top:8px;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.res{display:grid;grid-template-columns:32px minmax(0,1fr) auto;align-items:center;gap:10px;padding:9px 12px;border-top:1px solid var(--line)}
.res:first-child{border-top:0}
.res.hl{background:var(--bg)}
.res .nm{min-width:0}
.res .nm b{font-size:14px}
.res .nm div{font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.res .vals{display:flex;gap:6px;align-items:center;font-size:12px;font-variant-numeric:tabular-nums;flex-wrap:wrap;justify-content:flex-end}
.res .vals .px{color:var(--muted);margin-right:4px}
.res .tfv{display:inline-flex;align-items:center;gap:4px}
.res .tfv i{font-style:normal;color:var(--muted);font-weight:600}
.resmore{padding:9px 12px;font-size:12px;color:var(--muted);border-top:1px solid var(--line)}
.lt{display:inline-flex;border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:12px}
.lt button{font:600 13px/1 inherit;font-family:inherit;padding:8px 14px;border:0;background:transparent;color:var(--muted);cursor:pointer}
.lt button+button{border-left:1px solid var(--line)}
.lt button.on{background:var(--fg);color:var(--bg)}
tr.favrow td{background:rgba(212,160,23,.07)}
#chart{overflow-y:auto;overscroll-behavior:contain}
#tblwrap{overflow:auto;overscroll-behavior:contain}
#tbl thead th{position:sticky;top:0;background:var(--panel);z-index:1}
.more{font-size:12px;color:var(--muted);margin-top:8px;min-height:1em}
.tag{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.04em;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-left:6px;vertical-align:1px}
@media (max-width:640px){.res{grid-template-columns:32px minmax(0,1fr)}.res .vals{grid-column:2;justify-content:flex-start}.cards{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div><h1>RSI Screener</h1><p class="sub" id="summary"></p></div>
    <div id="rbox" hidden><label class="rstat" style="margin:0 8px 0 0">Fetch from <select class="dash-src" id="srcsel"></select></label><button class="refresh" id="refresh" title="Fresh prices for the watchlist (about 20 seconds). Other NSE stocks keep the date of their last full load.">Refresh data</button> <button class="refresh" id="refreshall" title="Reload every NSE stock from Yahoo (10 to 20 minutes)">Refresh all NSE</button><div class="rstat" id="rstat">Last fetched __GENERATED__</div></div>
  </header>
  <section class="panel" id="limits" hidden>
    <h2>Data source &amp; limits</h2>
    <div class="tablewrap"><table id="ltbl">
      <thead><tr><th>Source</th><th>Status</th><th class="num">Calls today</th><th class="num">Daily limit</th><th class="num">Left today</th><th>Notes</th></tr></thead>
      <tbody></tbody>
    </table></div>
    <p class="note" id="limnote" style="margin:10px 0 0">Calls are counted on this Mac and reset at midnight. Yahoo uses 1 call per refresh for all stocks; Tapetide and Angel One use 1 call per stock.</p>
  </section>
  <section class="search" id="searchbox">
    <span class="ic" aria-hidden="true">⌕</span>
    <input id="q" type="search" autocomplete="off" spellcheck="false" placeholder="Search all NSE stocks by symbol or company name" aria-label="Search all NSE stocks" aria-controls="results">
    <div class="results" id="results" role="listbox" hidden></div>
  </section>
  <section class="panel" id="favs">
    <div class="favhd"><h2>★ Favourites <span class="note" id="favcount"></span></h2><div class="favmsg" id="favmsg"></div></div>
    <div class="favgrid" id="favgrid"></div>
  </section>
  <div class="bar">
    <div class="tf" id="tfbar" role="tablist" aria-label="Timeframe">
      <button data-tf="d" class="on">Daily</button><button data-tf="w">Weekly</button><button data-tf="m">Monthly</button>
    </div>
    <div class="note" id="tfnote"></div>
  </div>
  <section class="cards">
    <div class="card bull" data-f="Bullish"><h3>Bullish</h3><div class="big" id="n-Bullish">0</div><div class="rule">RSI above 60</div></div>
    <div class="card" data-f="Sideways"><h3>Sideways</h3><div class="big" id="n-Sideways">0</div><div class="rule">RSI 40 to 60</div></div>
    <div class="card bear" data-f="Bearish"><h3>Bearish</h3><div class="big" id="n-Bearish">0</div><div class="rule">RSI below 40</div></div>
  </section>
  <section class="panel">
    <h2 id="charttitle">Daily RSI by stock</h2>
    <div class="lt listtabs" role="tablist" aria-label="Which stocks to show"><button data-l="all" role="tab">All</button><button data-l="fav" role="tab">★ Favourites</button></div>
    <div class="chart" id="chart"></div>
    <div class="more" id="chartmore"></div>
  </section>
  <section class="panel">
    <h2>Signals</h2>
    <div class="lt listtabs" id="listtabs" role="tablist" aria-label="Which stocks to list"><button data-l="all" role="tab">All</button><button data-l="fav" role="tab">★ Favourites</button></div>
    <div class="tablewrap" id="tblwrap"><table id="tbl">
      <thead><tr>
        <th title="Favourite">★</th><th data-k="symbol">Stock</th><th data-k="close" class="num">Close (₹)</th>
        <th data-k="rsi" class="num">Daily RSI</th><th data-k="change" class="num">Day change</th>
        <th data-k="rsi_w" class="num">Weekly RSI</th><th data-k="rsi_m" class="num">Monthly RSI</th>
        <th data-k="agree_n">Agreement</th><th id="trendhd">Daily RSI trend</th><th data-k="date">Date</th>
      </tr></thead><tbody></tbody>
    </table></div>
    <div class="more" id="tblmore"></div>
  </section>
  <p class="note">RSI(14) on daily, weekly (Friday close) and monthly closing prices; the current week and month count as "so far". Agreement shows how many timeframes match the daily signal. Search covers every NSE-listed stock that has price data; stocks outside the watchlist appear in the chart and table once you star them. Favourites are saved in this browser only. Click a card to filter; click a column to sort. Data: __SOURCE__. Generated __GENERATED__. A screen, not trading advice.</p>
</div>
<div class="tip" id="tip"></div>
<script>
const DATA = __DATA__;
const LO = 40, HI = 60;
let filter = null, sortK = "rsi", sortDir = -1;
const fmt = (v, d=2) => v == null || Number.isNaN(+v) ? "—" : Number(v).toLocaleString("en-IN", {minimumFractionDigits:d, maximumFractionDigits:d});
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const col = s => s === "Bullish" ? css("--ok") : s === "Bearish" ? css("--bad") : css("--mid");
const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs={}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };

const TF = {d: {rsi: "rsi", prev: "prev_rsi", sig: "signal", name: "Daily", span: "60 days"},
            w: {rsi: "rsi_w", prev: "prev_rsi_w", sig: "signal_w", name: "Weekly", span: "52 weeks"},
            m: {rsi: "rsi_m", prev: "prev_rsi_m", sig: "signal_m", name: "Monthly", span: "36 months"}};
const store = {
  get(k, d) { try { const v = localStorage.getItem("rsi-screener:" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("rsi-screener:" + k, JSON.stringify(v)); } catch (e) {} }
};
const MAX_FAVS = 10;
const ALL = DATA.rows;
const BY_SYM = new Map(ALL.map(r => [r.symbol, r]));
const symbols = new Set(BY_SYM.keys());
const inList = r => r.in_list !== false;  // older data has no flag: every row is the watchlist
let listTab = store.get("listtab", "all") === "fav" ? "fav" : "all";
let favs = store.get("favs", []).filter(s => symbols.has(s)).slice(0, MAX_FAVS);
let tf = ["d", "w", "m"].includes(store.get("tf", "d")) ? store.get("tf", "d") : "d";
if (!DATA.rows.some(r => r.rsi_w != null)) tf = "d";  // older data without weekly/monthly

ALL.forEach(r => {
  r.change = r.prev_rsi == null ? null : +(r.rsi - r.prev_rsi).toFixed(2);
  const m = /(\w+) (\d)\/(\d)/.exec(r.alignment || "");
  r.agree_n = m ? (m[1] === "Bullish" ? 10 : m[1] === "Bearish" ? -10 : 0) + +m[2] : -99;
});
const K = () => TF[tf];
const hist = (sym, t) => { const h = DATA.history[sym]; return Array.isArray(h) ? (t === "d" ? h : []) : ((h && h[t]) || []); };

// The stocks shown in the cards, chart and table: the watchlist plus any starred stock.
const VIEW = () => ALL.filter(r => inList(r) || favs.includes(r.symbol));

function summary() {
  const k = K(), view = VIEW(), withV = view.filter(r => r[k.rsi] != null);
  const nList = ALL.filter(inList).length, nExtra = view.length - nList;
  const count = (nExtra ? `${nList} watchlist + ${nExtra} starred` : `${view.length} stocks`) + (ALL.length > nList ? ` · ${ALL.length.toLocaleString("en-IN")} NSE stocks searchable` : "");
  const s = withV.slice().sort((a,b) => b[k.rsi] - a[k.rsi]);
  const hi = s[0], lo = s[s.length-1];
  document.getElementById("summary").textContent = hi
    ? `${count} · ${k.name.toLowerCase()} RSI strongest ${hi.symbol} (${fmt(hi[k.rsi])}), weakest ${lo.symbol} (${fmt(lo[k.rsi])}) · data as of ${DATA.asof}`
    : `${count} · data as of ${DATA.asof}`;
  for (const g of ["Bullish","Sideways","Bearish"])
    document.getElementById("n-"+g).textContent = view.filter(r => r[k.sig] === g).length;
  document.getElementById("charttitle").textContent = `${k.name} RSI by stock`;
  document.getElementById("trendhd").textContent = `${k.name} RSI trend`;
  document.getElementById("tfnote").textContent = tf === "d" ? "Cards, chart and filters use daily RSI"
    : `Cards, chart and filters use ${k.name.toLowerCase()} RSI (current ${tf === "w" ? "week" : "month"} so far)`;
  document.querySelectorAll("#tfbar button").forEach(b => b.classList.toggle("on", b.dataset.tf === tf));
}

function rows() { const k = K(); return VIEW().filter(r => !filter || r[k.sig] === filter); }

function chart() {
  const box = document.getElementById("chart"); box.innerHTML = "";
  const k = K();
  const fav = r => favs.includes(r.symbol);
  const data = rows().filter(r => r[k.rsi] != null && (listTab !== "fav" || fav(r)))
    .sort((a,b) => (fav(b) - fav(a)) || b[k.rsi] - a[k.rsi]);  // favourites first, then strongest RSI
  const SHOW = 10;
  box.style.maxHeight = data.length > SHOW ? (22 + SHOW * 28 + 4) + "px" : "";
  document.getElementById("chartmore").textContent = data.length > SHOW ? `Showing ${SHOW} of ${data.length} · scroll for more` : "";
  if (!data.length) { box.textContent = listTab === "fav" && !favs.length ? "No favourites yet. Tap ☆ next to a stock, or search for one above." : "No stocks in this group."; return; }
  const W = Math.max(300, box.clientWidth), bh = 28, top = 22, bottom = 26;
  const svg = el("svg", {viewBox:`0 0 ${W} ${top + data.length*bh + bottom}`, width:"100%", role:"img", "aria-label":`${k.name} RSI per stock with 40 and 60 lines`}, box);
  const probe = el("text", {class:"lbl"}, svg); let lw = 0;
  data.forEach(r => { probe.textContent = (favs.includes(r.symbol) ? "★ " : "") + r.symbol; lw = Math.max(lw, probe.getComputedTextLength()); }); probe.remove();
  const L = lw + 14, R = W - 44, x = v => L + (R - L) * v / 100, H = top + data.length*bh;
  el("rect", {x:x(0), y:top, width:x(LO)-x(0), height:data.length*bh, fill:css("--badbg")}, svg);
  el("rect", {x:x(HI), y:top, width:x(100)-x(HI), height:data.length*bh, fill:css("--okbg")}, svg);
  for (const v of [0,20,40,60,80,100]) { const t = el("text", {x:x(v), y:H+18, "text-anchor":"middle"}, svg); t.textContent = v; }
  for (const v of [LO,HI]) {
    el("line", {x1:x(v), x2:x(v), y1:top-4, y2:H, stroke:css("--mid"), "stroke-dasharray":"4 3"}, svg);
    const t = el("text", {x:x(v), y:top-8, "text-anchor":"middle"}, svg); t.textContent = v;
  }
  const tip = document.getElementById("tip");
  data.forEach((r,i) => {
    const y = top + i*bh, v0 = r[k.rsi];
    const t = el("text", {x:L-8, y:y+bh/2, dy:"0.35em", "text-anchor":"end", class:"lbl"}, svg); t.textContent = (favs.includes(r.symbol) ? "★ " : "") + r.symbol;
    el("rect", {x:x(0), y:y+5, width:Math.max(1, x(v0)-x(0)), height:bh-10, rx:3, fill:col(r[k.sig])}, svg);
    const v = el("text", {x:x(v0)+5, y:y+bh/2, dy:"0.35em"}, svg); v.textContent = fmt(v0,1);
    const hit = el("rect", {x:0, y, width:W, height:bh, fill:"transparent"}, svg);
    hit.addEventListener("pointermove", ev => {
      tip.textContent = `${r.symbol} · D ${fmt(r.rsi,1)} · W ${fmt(r.rsi_w,1)} · M ${fmt(r.rsi_m,1)} · ₹${fmt(r.close)}`;
      tip.style.display = "block";
      tip.style.left = Math.min(ev.pageX + 12, window.scrollX + document.documentElement.clientWidth - tip.offsetWidth - 8) + "px";
      tip.style.top = (ev.pageY + 14) + "px";
    });
    hit.addEventListener("pointerleave", () => tip.style.display = "none");
  });
}

function spark(h, label, w = 120) {
  const ht = 28, svg = el("svg", {width:w, height:ht, viewBox:`0 0 ${w} ${ht}`, role:"img", "aria-label":label});
  if (!h || h.length < 2) return svg;
  const y = v => ht - 2 - (ht - 4) * v / 100, x = i => 2 + (w - 4) * i / (h.length - 1);
  el("rect", {x:0, y:y(HI), width:w, height:y(LO)-y(HI), fill:css("--line"), opacity:.5}, svg);
  el("polyline", {points:h.map((v,i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" "), fill:"none", stroke:css("--fg"), "stroke-width":1.4}, svg);
  const last = h[h.length-1];
  el("circle", {cx:x(h.length-1), cy:y(last), r:2.6, fill:col(last > HI ? "Bullish" : last < LO ? "Bearish" : "Sideways")}, svg);
  return svg;
}

function rsiCell(v, sig, small) {
  const wrap = document.createElement("span"); wrap.className = "cell";
  const n = document.createElement("span"); n.textContent = fmt(v); wrap.appendChild(n);
  if (sig) { const p = document.createElement("span"); p.className = "pill " + sig + (small ? " sm" : ""); p.textContent = sig; wrap.appendChild(p); }
  return wrap;
}

function agreeTag(r) {
  const a = document.createElement("span");
  const m = /(\w+) (\d)\/(\d)/.exec(r.alignment || "");
  a.className = "agree" + (m && m[2] === m[3] ? " full " + m[1] : "");
  a.textContent = !m ? "—" : m[2] === m[3] ? `All ${m[3]} ${m[1].toLowerCase()}` : `${m[2]} of ${m[3]} ${m[1].toLowerCase()}`;
  a.title = "How many timeframes (daily, weekly, monthly) match the daily signal";
  return a;
}

function starBtn(sym) {
  const b = document.createElement("button"); const on = favs.includes(sym);
  b.className = "star" + (on ? " on" : ""); b.textContent = on ? "★" : "☆";
  b.title = on ? "Remove from favourites" : "Add to favourites"; b.setAttribute("aria-label", b.title + ": " + sym);
  b.addEventListener("click", e => { e.stopPropagation(); toggleFav(sym); });
  return b;
}

function toggleFav(sym) {
  const msg = document.getElementById("favmsg"); msg.textContent = "";
  if (favs.includes(sym)) favs = favs.filter(s => s !== sym);
  else if (favs.length >= MAX_FAVS) { msg.textContent = `You can keep up to ${MAX_FAVS} favourites. Remove one first.`; return; }
  else favs.push(sym);
  store.set("favs", favs); summary(); renderFavs(); table(); chart(); search();
}

function gaugeRow(label, v, sig) {
  const row = document.createElement("div"); row.className = "tfrow";
  const l = document.createElement("span"); l.className = "lab"; l.textContent = label; row.appendChild(l);
  const g = document.createElement("div"); g.className = "gauge";
  if (v != null) { const i = document.createElement("i"); i.style.left = Math.max(0, Math.min(100, v)) + "%"; i.style.background = col(sig); g.appendChild(i); }
  row.appendChild(g);
  const n = document.createElement("span"); n.style.textAlign = "right"; n.textContent = fmt(v, 1); row.appendChild(n);
  const p = document.createElement("span"); if (sig) { p.className = "pill sm " + sig; p.textContent = sig; } row.appendChild(p);
  return row;
}

function renderFavs() {
  const grid = document.getElementById("favgrid"); grid.innerHTML = "";
  document.getElementById("favcount").textContent = `${favs.length} of ${MAX_FAVS}`;
  if (!favs.length) {
    const e = document.createElement("div"); e.className = "empty";
    e.textContent = `Search for any NSE stock above, or tap ☆ next to a stock in the table, to pin it here. You can keep up to ${MAX_FAVS}.`;
    grid.appendChild(e); return;
  }
  for (const sym of favs) {
    const r = BY_SYM.get(sym); if (!r) continue;
    const c = document.createElement("div"); c.className = "fav";
    const hd = document.createElement("div"); hd.className = "hd";
    const left = document.createElement("div");
    const sy = document.createElement("span"); sy.className = "sym"; sy.textContent = sym; sy.title = r.name || ""; left.appendChild(sy);
    const px = document.createElement("div"); px.className = "px";
    px.textContent = `₹${fmt(r.close)}` + (r.change == null ? "" : ` · day ${r.change > 0 ? "+" : ""}${fmt(r.change)}`);
    left.appendChild(px); hd.appendChild(left); hd.appendChild(starBtn(sym)); c.appendChild(hd);
    c.appendChild(gaugeRow("D", r.rsi, r.signal));
    c.appendChild(gaugeRow("W", r.rsi_w, r.signal_w));
    c.appendChild(gaugeRow("M", r.rsi_m, r.signal_m));
    const ft = document.createElement("div"); ft.className = "hd";
    ft.appendChild(agreeTag(r)); ft.appendChild(spark(hist(sym, "d"), "Daily RSI over the last 60 days", 110));
    c.appendChild(ft);
    grid.appendChild(c);
  }
}

function syncTabs() {
  const n = rows().length;
  document.querySelectorAll(".listtabs button").forEach(b => {
    b.classList.toggle("on", b.dataset.l === listTab); b.setAttribute("aria-selected", b.dataset.l === listTab);
    b.textContent = b.dataset.l === "fav" ? `★ Favourites (${favs.length})` : `All (${n})`;
  });
}
function table() {
  const tb = document.querySelector("#tbl tbody"); tb.innerHTML = "";
  syncTabs();
  const val = (r, k) => r[k] == null ? -Infinity : r[k];
  const isFav = r => favs.includes(r.symbol);
  let data = rows();
  if (listTab === "fav") data = data.filter(isFav);
  // Favourites always stay at the top; the chosen column sorts within each group.
  data = data.slice().sort((a,b) => (isFav(b) - isFav(a)) || (val(a,sortK) > val(b,sortK) ? 1 : val(a,sortK) < val(b,sortK) ? -1 : 0) * sortDir);
  if (!data.length) {
    const tr = document.createElement("tr"), td = document.createElement("td"); td.colSpan = 10; td.className = "empty";
    td.textContent = listTab === "fav" ? (favs.length ? "None of your favourites are in this group." : "No favourites yet. Tap ☆ next to a stock, or search for one above.") : "No stocks in this group.";
    tr.appendChild(td); tb.appendChild(tr); return;
  }
  for (const r of data) {
    const tr = document.createElement("tr"); if (isFav(r)) tr.className = "favrow";
    const td = (t, c) => { const d = document.createElement("td"); if (c) d.className = c; if (t instanceof Node) d.appendChild(t); else d.textContent = t; tr.appendChild(d); return d; };
    td(starBtn(r.symbol));
    const s = td(r.symbol); s.title = r.name || "";
    if (!inList(r)) { const t = document.createElement("span"); t.className = "tag"; t.textContent = "STARRED"; t.title = "Not in the watchlist: shown because you starred it"; s.appendChild(t); }
    if (r.source && r.source !== DATA.source) { const sm = document.createElement("div"); sm.className = "src"; sm.textContent = "via " + r.source; s.appendChild(sm); }
    td(fmt(r.close), "num");
    td(rsiCell(r.rsi, r.signal), "num");
    td(r.change == null ? "—" : (r.change > 0 ? "+" : "") + fmt(r.change), "num " + (r.change > 0 ? "up" : r.change < 0 ? "down" : ""));
    td(rsiCell(r.rsi_w, r.signal_w), "num");
    td(rsiCell(r.rsi_m, r.signal_m), "num");
    td(agreeTag(r));
    td(spark(hist(r.symbol, tf), `${K().name} RSI over the last ${K().span}`));
    td(new Date(r.date + "T00:00:00").toLocaleDateString("en-IN", {day:"2-digit", month:"short", year:"numeric"}));
    tb.appendChild(tr);
  }
  fitTable(data.length);
}

// Show 10 rows; the rest scroll inside the table (the header stays visible).
function fitTable(n) {
  const SHOW = 10, wrap = document.getElementById("tblwrap"), trs = [...document.querySelectorAll("#tbl tbody tr")];
  wrap.style.maxHeight = "";
  if (n > SHOW) {
    const h = document.querySelector("#tbl thead").offsetHeight + trs.slice(0, SHOW).reduce((a, r) => a + r.offsetHeight, 0);
    wrap.style.maxHeight = (h + 2) + "px";
  }
  document.getElementById("tblmore").textContent = n > SHOW ? `Showing ${SHOW} of ${n} · scroll for more` : "";
}

// ---- Search over every NSE stock ----
const MAX_RESULTS = 20;
const norm = t => (t || "").toLowerCase().replace(/[^a-z0-9&]+/g, " ").replace(/\b(limited|ltd)\b/g, "").trim();
ALL.forEach(r => { r._s = r.symbol.toLowerCase(); r._n = norm(r.name); });
let hl = 0, lastHits = [];
function matches(q) {
  const s = q.toLowerCase().replace(/\s+/g, ""), n = norm(q);
  if (!s) return [];
  const scored = [];
  for (const r of ALL) {
    let sc = r._s === s ? 0 : r._s.startsWith(s) ? 1 : (n && (" " + r._n).includes(" " + n)) ? 2 : r._s.includes(s) ? 3 : (n && r._n.includes(n)) ? 4 : -1;
    if (sc >= 0) scored.push([sc, r]);
  }
  scored.sort((a, b) => a[0] - b[0] || a[1].symbol.length - b[1].symbol.length || a[1].symbol.localeCompare(b[1].symbol));
  return scored.map(x => x[1]);
}
function tfv(label, v, sig) {
  const w = document.createElement("span"); w.className = "tfv";
  const i = document.createElement("i"); i.textContent = label; w.appendChild(i);
  const n = document.createElement("span"); n.textContent = fmt(v, 1); w.appendChild(n);
  if (sig) { const p = document.createElement("span"); p.className = "pill sm " + sig; p.textContent = sig; w.appendChild(p); }
  return w;
}
function search() {
  const q = document.getElementById("q").value.trim(), box = document.getElementById("results");
  box.innerHTML = "";
  if (!q) { box.hidden = true; lastHits = []; return; }
  const hits = matches(q); lastHits = hits.slice(0, MAX_RESULTS);
  hl = Math.min(hl, Math.max(lastHits.length - 1, 0));
  box.hidden = false;
  if (!hits.length) { const e = document.createElement("div"); e.className = "resmore"; e.textContent = `No NSE stock matches "${q}".`; box.appendChild(e); return; }
  lastHits.forEach((r, i) => {
    const row = document.createElement("div"); row.className = "res" + (i === hl ? " hl" : ""); row.setAttribute("role", "option");
    const sb = starBtn(r.symbol); sb.addEventListener("click", closeSearch); row.appendChild(sb);
    const nm = document.createElement("div"); nm.className = "nm";
    const b = document.createElement("b"); b.textContent = r.symbol; nm.appendChild(b);
    if (inList(r)) { const t = document.createElement("span"); t.className = "tag"; t.textContent = "WATCHLIST"; nm.appendChild(t); }
    const d = document.createElement("div"); d.textContent = r.name || ""; nm.appendChild(d);
    row.appendChild(nm);
    const v = document.createElement("div"); v.className = "vals";
    const px = document.createElement("span"); px.className = "px"; px.textContent = "₹" + fmt(r.close) + (r.date && r.date !== DATA.asof ? " · " + new Date(r.date + "T00:00:00").toLocaleDateString("en-IN", {day: "2-digit", month: "short"}) : ""); v.appendChild(px);
    v.appendChild(tfv("D", r.rsi, r.signal)); v.appendChild(tfv("W", r.rsi_w, r.signal_w)); v.appendChild(tfv("M", r.rsi_m, r.signal_m));
    row.appendChild(v);
    row.addEventListener("mouseenter", () => { hl = i; document.querySelectorAll("#results .res").forEach((x, j) => x.classList.toggle("hl", j === i)); });
    box.appendChild(row);
  });
  if (hits.length > MAX_RESULTS) { const m = document.createElement("div"); m.className = "resmore"; m.textContent = `Showing ${MAX_RESULTS} of ${hits.length} matches. Type more to narrow it down.`; box.appendChild(m); }
}
const qEl = document.getElementById("q");
function closeSearch() { qEl.value = ""; hl = 0; search(); qEl.blur(); }
// Click anywhere outside the search box: close the results.
document.addEventListener("click", e => { if (qEl.value && !document.getElementById("searchbox").contains(e.target)) closeSearch(); });
qEl.addEventListener("input", () => { hl = 0; search(); });
qEl.addEventListener("keydown", e => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (lastHits.length) { hl = (hl + (e.key === "ArrowDown" ? 1 : -1) + lastHits.length) % lastHits.length; search(); } }
  else if (e.key === "Enter" && lastHits[hl]) { e.preventDefault(); toggleFav(lastHits[hl].symbol); closeSearch(); }
  else if (e.key === "Escape") { qEl.value = ""; search(); }
});
if (ALL.length <= ALL.filter(inList).length) qEl.placeholder = "Search the watchlist (refresh to load all NSE stocks)";

function render() { summary(); renderFavs(); chart(); table(); search(); }

document.querySelectorAll("#tfbar button").forEach(b => b.addEventListener("click", () => {
  tf = b.dataset.tf; store.set("tf", tf);
  if (["rsi", "rsi_w", "rsi_m"].includes(sortK)) sortK = K().rsi;
  render();
}));
document.querySelectorAll(".listtabs button").forEach(b => b.addEventListener("click", () => {
  listTab = b.dataset.l; store.set("listtab", listTab); chart(); table();
}));
document.querySelectorAll(".card").forEach(c => c.addEventListener("click", () => {
  filter = filter === c.dataset.f ? null : c.dataset.f;
  document.querySelectorAll(".card").forEach(x => x.classList.toggle("on", x.dataset.f === filter));
  chart(); table();
}));
document.querySelectorAll("th[data-k]").forEach(th => th.addEventListener("click", () => {
  const k = th.dataset.k;
  if (sortK === k) sortDir *= -1; else { sortK = k; sortDir = (k === "symbol" || k === "date") ? 1 : -1; }
  table();
}));
let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(chart, 120); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
sortK = K().rsi;
render();
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
  btn.addEventListener("click", () => onRefresh(sel.value, btn, st, "list"));
  const all = document.getElementById("refreshall");
  all.addEventListener("click", () => onRefresh(sel.value, all, st, "all"));
}

if (["127.0.0.1", "localhost"].includes(location.hostname)) {
  // On the Mac: the local server fetches new data.
  fetch("/sources").then(r => r.json()).then(d => setupControls(d, async (source, btn, st, scope) => {
    const btns = [document.getElementById("refresh"), document.getElementById("refreshall")], label = btn.textContent;
    btns.forEach(b => b.disabled = true); btn.textContent = "Fetching…";
    st.textContent = scope === "all" ? "Loading every NSE stock from Yahoo (10 to 20 minutes). You can keep using this page meanwhile."
                                     : "Getting fresh prices for the watchlist (about 20 seconds)";
    try {
      const r = await fetch("/refresh", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({source, scope})});
      if (r.ok) { location.reload(); return; }
      st.textContent = r.status === 409 ? "Already refreshing…" : "Refresh failed: " + (await r.text()).slice(-160);
    } catch (e) { st.textContent = "Can't reach the dashboard server. Is its Terminal window still open?"; }
    btns.forEach(b => b.disabled = false); btn.textContent = label;
  })).catch(() => {});
} else if (DATA.online) {
  // Online (shared page): updates run automatically on a schedule, so there is no Refresh button.
  const on = DATA.online;
  setupControls(on, () => {}, null);
  document.getElementById("refresh").hidden = true;
  document.getElementById("refreshall").hidden = true;
  document.getElementById("srcsel").closest("label").hidden = true;
  const nextUpdate = () => {
    // Scheduled runs: Mon–Fri at 12:17 and 16:47 India time (UTC+5:30).
    const IST = 330 * 60000, slots = [[12, 17], [16, 47]];
    const nowIst = new Date(Date.now() + IST);
    for (let d = 0; d < 8; d++) {
      const day = new Date(Date.UTC(nowIst.getUTCFullYear(), nowIst.getUTCMonth(), nowIst.getUTCDate() + d));
      const wd = day.getUTCDay();
      if (wd === 0 || wd === 6) continue;
      for (const [h, m] of slots) {
        const t = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), h, m) - IST;
        if (t > Date.now()) return new Date(t);
      }
    }
    return null;
  };
  const nu = nextUpdate();
  const fmtIst = dt => dt.toLocaleString("en-IN", {timeZone: "Asia/Kolkata", weekday: "short", day: "2-digit", month: "short", hour: "numeric", minute: "2-digit"}) + " IST";
  const st = document.getElementById("rstat");
  st.innerHTML = "";
  const line = (label, value) => { const d = document.createElement("div"); const b = document.createElement("b"); b.textContent = label + " "; d.appendChild(b); d.appendChild(document.createTextNode(value)); st.appendChild(d); };
  line("Last updated:", "__GENERATED__");
  if (nu) line("Next update:", fmtIst(nu) + " (about 2 minutes to appear)");
  line("Schedule:", "Mon–Fri, 12:17 PM (provisional, market open) and 4:47 PM (final, after close)");
  st.style.textAlign = "left"; st.style.fontSize = "13px"; st.style.lineHeight = "1.6";
  document.getElementById("limnote").textContent = "Calls counted for today's updates of this page. Each update uses 1 Yahoo Finance call for all stocks.";
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


def _clean(v):
    """NaN (missing value from pandas) -> None, so the page gets null instead of NaN."""
    return None if isinstance(v, float) and v != v else v


def build_html_from_payload(payload: dict, generated: str | None = None) -> str:
    payload = dict(payload, rows=[{k: _clean(v) for k, v in r.items()} for r in payload.get("rows", [])])
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
    sources = [
        {"id": "yahoo", "label": "Yahoo Finance", "ready": True, "note": "Free, no limit · used for this page"},
        {"id": "tapetide", "label": "Tapetide", "ready": False, "note": "Not set up online (needs a paid plan)"},
        {"id": "angel", "label": "Angel One", "ready": False, "note": "Not set up online (needs an Angel One account)"},
    ]
    for o in sources:
        u = usage.summary(o["id"])
        o["usage"], o["quota"] = u, u["text"]
    return {
        "sources": sources,
        "last": "yahoo",
        "schedule": "Updates Mon–Fri at 12:17 PM and 4:47 PM IST (the midday numbers are provisional until the close)",
    }
