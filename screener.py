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


def yahoo_closes(symbols: list[str]) -> dict[str, pd.Series]:
    import yfinance as yf

    tickers = [f"{s.upper()}.NS" for s in symbols]
    import usage
    usage.record("yahoo", 1)
    data = yf.download(tickers, period="9mo", interval="1d", auto_adjust=True,
                       group_by="ticker", progress=False, threads=True)
    out = {}
    for s, t in zip(symbols, tickers):
        try:
            close = (data[t]["Close"] if len(tickers) > 1 else data["Close"]).dropna()
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            out[s.upper()] = close
        except Exception as e:
            print(f"  ! {t}: {e}", file=sys.stderr)
    return out


def angel_configured() -> bool:
    from angel_source import load_env
    load_env()
    return all(os.environ.get(k) for k in
               ("ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PIN", "ANGEL_TOTP_SECRET"))


def screen(closes: dict[str, pd.Series], history: dict | None = None) -> pd.DataFrame:
    rows = []
    for sym, close in closes.items():
        close = close.dropna()
        if len(close) <= RSI_PERIOD + 1:
            print(f"  ! {sym}: not enough price history", file=sys.stderr)
            continue
        rsi = wilder_rsi(close).dropna()
        if history is not None:
            history[sym] = [round(float(v), 2) for v in rsi.iloc[-60:]]
        rows.append({
            "symbol": sym,
            "date": pd.Timestamp(rsi.index[-1]).date().isoformat(),
            "close": round(float(close.iloc[-1]), 2),
            "rsi": round(float(rsi.iloc[-1]), 2),
            "prev_rsi": round(float(rsi.iloc[-2]), 2),
            "signal": classify(float(rsi.iloc[-1])),
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
    args = p.parse_args()

    symbols = [s.upper() for s in (args.tickers or WATCHLIST)]
    source = args.source
    if source == "auto":
        from tapetide_source import token as tapetide_token
        # Tapetide's free plan has no REST API access, so it is only used when asked for (--source tapetide).
        source = "angel" if angel_configured() else "yahoo"

    names = {"tapetide": "Tapetide API", "angel": "Angel One SmartAPI", "yahoo": "Yahoo Finance"}
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
    used.update({s: names[source] for s in closes})

    if failed and source != "yahoo":
        print(f"  Falling back to Yahoo for {len(failed)} stock(s): {', '.join(failed)}")
        extra = yahoo_closes(failed)
        closes.update(extra)
        used.update({s: names["yahoo"] for s in extra})

    history: dict = {}
    df = screen(closes, history)
    if df.empty:
        print("No data returned.")
        return
    df["source"] = df["symbol"].map(used)

    print(f"\nSource: {names[source]}" + (" (+ Yahoo fallback)" if (df["source"] != names[source]).any() else "") + "\n")
    show = df if (df["source"] != names[source]).any() else df.drop(columns="source")
    print(show.to_string(index=False))
    print()
    for s in ("Bullish", "Sideways", "Bearish"):
        members = ", ".join(df.loc[df.signal == s, "symbol"]) or "-"
        print(f"{s:9} ({(df.signal == s).sum():2}): {members}")

    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"\nSaved to {args.csv}")

    here = Path(__file__).resolve().parent
    df.to_csv(here / "latest.csv", index=False)  # Claude can read this to discuss results

    from dashboard import build_html
    out = here / "dashboard.html"
    out.write_text(build_html(df, history, names[source]), encoding="utf-8")
    print(f"\nDashboard: {out}")
    if not args.no_open:
        import webbrowser
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
