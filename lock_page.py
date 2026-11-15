"""Wraps the dashboard in a password-protected page for publishing online.

The dashboard is encrypted (AES-256-GCM, key from the password via PBKDF2-SHA256),
so the published file holds no readable data. The browser decrypts it after the
password is entered. The password comes from the PAGE_PASSWORD environment variable
(a GitHub Actions secret), never from this file.

Usage: PAGE_PASSWORD=... python lock_page.py dashboard.html site/index.html
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 250_000

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>RSI Screener</title>
<style>
:root{--bg:#f7f7f5;--panel:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e4e3de;--bad:#c2410c}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--panel:#1f1f1d;--fg:#ededea;--muted:#a3a39d;--line:#34342f;--bad:#fb923c}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
form{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:28px;width:min(340px,88vw);display:flex;flex-direction:column;gap:12px}
h1{font:400 26px/1.2 Georgia,serif;margin:0}
p{margin:0;color:var(--muted);font-size:13px}
input,button{font:inherit;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--fg)}
button{background:var(--fg);color:var(--bg);border-color:var(--fg);cursor:pointer;font-weight:600}
#err{color:var(--bad);min-height:1.2em}
</style>
</head>
<body>
<form id="f">
  <h1>RSI Screener</h1>
  <p>Enter the password to view the dashboard.</p>
  <input id="pw" type="password" autocomplete="current-password" placeholder="Password" autofocus>
  <button type="submit">Open</button>
  <p id="err"></p>
</form>
<script>
(() => {
const SALT="__SALT__", IV="__IV__", DATA="__DATA__", ITER=__ITER__;
const b64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
async function unlock(pw) {
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(pw), "PBKDF2", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey({name:"PBKDF2", salt:b64(SALT), iterations:ITER, hash:"SHA-256"}, base, {name:"AES-GCM", length:256}, false, ["decrypt"]);
  const plain = await crypto.subtle.decrypt({name:"AES-GCM", iv:b64(IV)}, key, b64(DATA));
  return new TextDecoder().decode(plain);
}
async function open(pw, remember) {
  const html = await unlock(pw);
  if (remember) { try { sessionStorage.setItem("rsi-pw", pw); } catch (e) {} }
  document.open(); document.write(html); document.close();
}
document.getElementById("f").addEventListener("submit", async e => {
  e.preventDefault();
  const err = document.getElementById("err"); err.textContent = "Checking…";
  try { await open(document.getElementById("pw").value, true); }
  catch (x) { err.textContent = "Wrong password."; }
});
(async () => { let saved = null; try { saved = sessionStorage.getItem("rsi-pw"); } catch (e) {}
  if (saved) { try { await open(saved, false); } catch (e) {} } })();
})();
</script>
</body>
</html>
"""


def lock(html: str, password: str) -> str:
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS).derive(password.encode())
    data = AESGCM(key).encrypt(iv, html.encode("utf-8"), None)
    enc = lambda b: base64.b64encode(b).decode()
    return (PAGE.replace("__SALT__", enc(salt)).replace("__IV__", enc(iv))
                .replace("__DATA__", enc(data)).replace("__ITER__", str(ITERATIONS)))


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    password = os.environ.get("PAGE_PASSWORD", "")
    if not password:
        raise SystemExit("PAGE_PASSWORD is not set. Add it as a repository secret on GitHub.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(lock(src.read_text(encoding="utf-8"), password), encoding="utf-8")
    print(f"Locked page written to {dst}")


if __name__ == "__main__":
    main()
