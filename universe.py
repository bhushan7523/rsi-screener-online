"""The list of every stock listed on NSE (symbol + company name), for the dashboard's search.

Source: NSE's own equity list (EQUITY_L.csv). It is cached for a day in .cache/. If NSE can't be
reached (it sometimes blocks servers), the copy saved next to this file (nse_symbols.csv) is used.
"""

from __future__ import annotations

import csv
import io
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
NSE_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
CACHE = HERE / ".cache" / "nse_symbols.csv"
BUNDLED = HERE / "nse_symbols.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120 Safari/537.36"}


def _parse_nse(text: str) -> list[tuple[str, str]]:
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        row = {k.strip().upper(): (v or "").strip() for k, v in row.items() if k}
        sym, name = row.get("SYMBOL"), row.get("NAME OF COMPANY")
        if sym:
            out.append((sym.upper(), name or sym))
    return out


def _read_saved(path: Path) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8") as f:
        return [(r["symbol"], r["name"]) for r in csv.DictReader(f) if r.get("symbol")]


def _save(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "name"])
        w.writerows(rows)


def nse_symbols(update_bundled: bool = False) -> list[tuple[str, str]]:
    """[(symbol, company name)] for every NSE-listed stock, sorted by symbol."""
    if CACHE.exists() and time.time() - CACHE.stat().st_mtime < 86400:
        return _read_saved(CACHE)
    try:
        r = requests.get(NSE_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        rows = sorted(set(_parse_nse(r.text)))
        if len(rows) < 1000:
            raise ValueError(f"only {len(rows)} stocks in NSE's list")
        _save(CACHE, rows)
        if update_bundled:
            _save(BUNDLED, rows)
        return rows
    except Exception as e:
        print(f"  ! NSE stock list not reachable ({e}); using the saved copy")
        return _read_saved(BUNDLED)


if __name__ == "__main__":
    # python universe.py  -> refreshes nse_symbols.csv from NSE
    rows = nse_symbols(update_bundled=True)
    print(len(rows), "NSE stocks")
