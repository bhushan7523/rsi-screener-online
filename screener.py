"""RSI screener for Indian (NSE) stocks.

Rules (from the user's sheet, first 3 rows):
    RSI > 60        -> Bullish
    RSI < 40        -> Bearish
    RSI 40 to 60    -> Sideways (inclusive)

Data sources (auto picks the first one configured in .env):
    tapetide - Tapetide API (TAPETIDE_TOKEN). Free plan: 50 calls/day, 1 call per stock.
    angel    - Angel One SmartAPI (ANGEL_* keys). Free with an Angel One account.
    yahoo    - Yahoo Finance via yfinance. Free, no account, unofficial. Also the fallback
               for any stock the chosen source couldn't load.
RSI: 14-period Wilder RSI on daily closing prices.

Usage:
    python screener.py                          # default watchlist, best available source
    python screener.py RELIANCE TCS INFY        # your own NSE symbols
    python screener.py --source yahoo           # force Yahoo (or: tapetide, angel)
    python screener.py --debug                  # show the first raw API answer
    python screener.py --csv results.csv        # also save results to a CSV
    python screener.py --universe list          # only the watchlist (skip the all-NSE search data)

The dashboard's search covers every NSE-listed stock: after the watchlist is loaded from the chosen
source, all other NSE stocks are loaded from Yahoo Finance in batches (a few minutes).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

RSI_PERIOD = 14
BULLISH_ABOVE = 60
BEARISH_BELOW = 40

# Large, liquid NSE stocks. Edit freely.
WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC",
    "BHARTIARTL", "LT", "KOTAKBANK", "AXISBANK", "HINDUNILVR", "BAJFINANCE",
    "MARUTI", "SUNPHARMA", "TITAN", "ASIANPAINT", "ULTRACEMCO", "NTPC",
    "POWERGRID", "TATASTEEL", "WIPRO", "HCLTECH", "ONGC", "ADANIPORTS",
]


def wilder_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)
    return rsi.where(avg_loss != 0, 100.0)


def classify(rsi: float) -> str:
    if rsi > BULLISH_ABOVE:
        return "Bullish"
    if rsi < BEARISH_BELOW:
        return "Bearish"
    return "Sideways"


YAHOO_BATCH = 250  # tickers per Yahoo download


def yahoo_closes(symbols: list[str], quiet: bool = False) -> dict[str, pd.Series]:
    import logging
    import yfinance as yf
    import usage

    if quiet:
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    out = {}
    for i in range(0, len(symbols), YAHOO_BATCH):
        part = symbols[i:i + YAHOO_BATCH]
        tickers = [f"{s.upper()}.NS" for s in part]
        usage.record("yahoo", 1)
        data = yf.download(tickers, period="3y", interval="1d", auto_adjust=True,
                           group_by="ticker", progress=False, threads=True)
        for s, t in zip(part, tickers):
            try:
                close = (data[t]["Close"] if len(tickers) > 1 else data["Close"]).dropna()
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                if len(close):
                    out[s.upper()] = close
            except Exception as e:
                if not quiet:
                    print(f"  ! {t}: {e}", file=sys.stderr)
        if len(symbols) > YAHOO_BATCH:
            print(f"  Yahoo: {min(i + YAHOO_BATCH, len(symbols))} of {len(symbols)} stocks", flush=True)
    return out


def angel_configured() -> bool:
    from angel_source import load_env
    load_env()
    return all(os.environ.get(k) for k in
               ("ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PIN", "ANGEL_TOTP_SECRET"))


def resample_closes(close: pd.Series, rule: str) -> pd.Series:
    """Last close of each week ('W') or month ('M'). The current period counts as 'so far'."""
    if rule == "W":
        return close.resample("W-FRI").last().dropna()
    try:
        return close.resample("ME").last().dropna()
    except ValueError:  # older pandas
        return close.resample("M").last().dropna()


def rsi_pair(close: pd.Series) -> tuple[float | None, float | None, list]:
    """Latest RSI, previous RSI and recent RSI values for a close series (None if too short)."""
    if len(close) <= RSI_PERIOD + 1:
        return None, None, []
    rsi = wilder_rsi(close).dropna()
    if len(rsi) < 2:
        return None, None, []
    return round(float(rsi.iloc[-1]), 2), round(float(rsi.iloc[-2]), 2), [round(float(v), 2) for v in rsi.iloc[-60:]]


def alignment(signals: list) -> str:
    """How many timeframes agree with the daily signal, e.g. 'Bullish 3/3'."""
    known = [x for x in signals if x]
    if not known:
        return ""
    lead = known[0]
    return f"{lead} {sum(1 for x in known if x == lead)}/{len(known)}"


def screen(closes: dict[str, pd.Series], history: dict | None = None,
           names: dict | None = None, in_list: set | None = None) -> pd.DataFrame:
    """One row per stock. `in_list` = watchlist stocks (full detail); others get rounded RSI history
    to keep the page small."""
    rows = []
    names = names or {}
    for sym, close in closes.items():
        close = close.dropna()
        close.index = pd.to_datetime(close.index)
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        listed = in_list is None or sym in in_list
        d, d_prev, d_hist = rsi_pair(close)
        if d is None:
            if listed:
                print(f"  ! {sym}: not enough price history", file=sys.stderr)
            continue
        w, w_prev, w_hist = rsi_pair(resample_closes(close, "W"))
        m, m_prev, m_hist = rsi_pair(resample_closes(close, "M"))
        if history is not None:
            h = {"d": d_hist, "w": w_hist[-52:], "m": m_hist[-36:]}
            if not listed:  # sparklines only: whole numbers are enough
                h = {k: [int(round(v)) for v in vals] for k, vals in h.items()}
            history[sym] = h
        sig = lambda v: classify(v) if v is not None else None
        rows.append({
            "symbol": sym,
            "name": names.get(sym, ""),
            "in_list": bool(listed),
            "date": pd.Timestamp(close.index[-1]).date().isoformat(),
            "close": round(float(close.iloc[-1]), 2),
            "rsi": d, "prev_rsi": d_prev, "signal": sig(d),
            "rsi_w": w, "prev_rsi_w": w_prev, "signal_w": sig(w),
            "rsi_m": m, "prev_rsi_m": m_prev, "signal_m": sig(m),
            "alignment": alignment([sig(d), sig(w), sig(m)]),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("rsi", ascending=False).reset_index(drop=True)


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    p = argparse.ArgumentParser(description="RSI screener for NSE stocks")
    p.add_argument("tickers", nargs="*", help="NSE symbols, e.g. RELIANCE TCS")
    p.add_argument("--source", choices=["auto", "tapetide", "angel", "yahoo"], default="auto")
    p.add_argument("--csv", help="save results to this CSV file")
    p.add_argument("--debug", action="store_true", help="print the first raw API answer")
    p.add_argument("--no-open", action="store_true", help="write dashboard.html but don't open it")
    p.add_argument("--universe", choices=["nse", "keep", "list"], default="nse",
                   help="nse = also load every NSE stock for the search (default, a few minutes); "
                        "keep = refresh the watchlist only and keep the other NSE stocks from the last full load; "
                        "list = watchlist only")
    args = p.parse_args()

    symbols = [s.upper() for s in (args.tickers or WATCHLIST)]
    source = args.source
    if source == "auto":
        # Tapetide's free plan has no REST API access, so it is only used when asked for (--source tapetide).
        source = "angel" if angel_configured() else "yahoo"

    names_src = {"tapetide": "Tapetide API", "angel": "Angel One SmartAPI", "yahoo": "Yahoo Finance"}
    used = {}
    if source == "tapetide":
        from tapetide_source import daily_closes
        closes, failed = daily_closes(symbols, debug=args.debug)
    elif source == "angel":
        from angel_source import daily_closes
        closes = daily_closes(symbols)
        failed = [s for s in symbols if s not in closes]
    else:
        closes, failed = yahoo_closes(symbols), []
    used.update({s: names_src[source] for s in closes})

    if failed and source != "yahoo":
        print(f"  Falling back to Yahoo for {len(failed)} stock(s): {', '.join(failed)}")
        extra = yahoo_closes(failed)
        closes.update(extra)
        used.update({s: names_src["yahoo"] for s in extra})

    here = Path(__file__).resolve().parent
    watch = set(closes)
    names: dict = {}
    kept_rows: list = []
    kept_hist: dict = {}
    if args.universe in ("keep", "list"):
        try:
            from universe import _read_saved, BUNDLED, CACHE
            names = dict(_read_saved(CACHE if CACHE.exists() else BUNDLED))
        except Exception:
            names = {}
    if args.universe == "keep":
        from dashboard import payload_from_html
        page = here / "dashboard.html"
        payload = payload_from_html(page.read_text(encoding="utf-8")) if page.exists() else None
        if payload:
            kept_rows = [r for r in payload["rows"] if r.get("in_list") is False and r["symbol"] not in watch]
            kept_hist = {r["symbol"]: payload.get("history", {}).get(r["symbol"]) for r in kept_rows}
        print(f"  Kept {len(kept_rows)} other NSE stocks from the last full load"
              + ("" if kept_rows else " (none yet: use 'Refresh all NSE' once)"))
    if args.universe == "nse":
        from universe import nse_symbols
        nse = nse_symbols()
        names = dict(nse)
        rest = [s for s, _ in nse if s not in closes]
        print(f"  Loading {len(rest)} more NSE stocks from Yahoo for the search...", flush=True)
        extra = yahoo_closes(rest, quiet=True)
        closes.update(extra)
        used.update({s: names_src["yahoo"] for s in extra})
        print(f"  {len(extra)} of {len(rest)} loaded (the rest have no Yahoo data)")

    history: dict = {}
    df = screen(closes, history, names, in_list=watch)
    if df.empty:
        print("No data returned.")
        return
    df["source"] = df["symbol"].map(used)
    if kept_rows:
        df = pd.concat([df, pd.DataFrame(kept_rows)], ignore_index=True)
        df["in_list"] = df["in_list"].astype(bool)
        history.update({k: v for k, v in kept_hist.items() if v})
    listed = df[df["in_list"]]

    fallback = (listed["source"] != names_src[source]).any()
    print(f"\nSource: {names_src[source]}" + (" (+ Yahoo fallback)" if fallback else "") + "\n")
    cols = ["symbol", "close", "rsi", "signal", "rsi_w", "signal_w", "rsi_m", "signal_m"]
    if fallback:
        cols.append("source")
    print(listed[cols].rename(columns={"rsi": "daily", "signal": "d_sig", "rsi_w": "weekly", "signal_w": "w_sig",
                                   "rsi_m": "monthly", "signal_m": "m_sig"}).to_string(index=False))
    print()
    for s in ("Bullish", "Sideways", "Bearish"):
        members = ", ".join(listed.loc[listed.signal == s, "symbol"]) or "-"
        print(f"{s:9} ({(listed.signal == s).sum():2}): {members}")
    if len(df) > len(listed):
        counts = df["signal"].value_counts()
        print(f"\nAll NSE ({len(df)}): " + ", ".join(f"{k} {counts.get(k, 0)}" for k in ("Bullish", "Sideways", "Bearish")))

    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"\nSaved to {args.csv}")

    df.to_csv(here / "latest.csv", index=False)  # Claude can read this to discuss results

    from dashboard import build_html
    out = here / "dashboard.html"
    out.write_text(build_html(df, history, names_src[source]), encoding="utf-8")
    print(f"\nDashboard: {out}")
    if not args.no_open:
        import webbrowser
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
