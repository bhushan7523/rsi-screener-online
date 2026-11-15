# RSI Screener (online)

Daily RSI(14) screen of large NSE stocks, published as a password-protected page on GitHub Pages.

- **Bullish:** RSI above 60 · **Sideways:** RSI 40 to 60 · **Bearish:** RSI below 40
- Data: Yahoo Finance daily closes (via `yfinance`).
- Runs automatically every weekday at 4:47 PM IST, after the NSE close. To refresh by hand: **Actions → Publish RSI dashboard → Run workflow**.
- The page is encrypted with the `PAGE_PASSWORD` repository secret (Settings → Secrets and variables → Actions). No data is stored in this repository.

Not trading advice.
