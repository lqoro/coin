# Phantom (personal LARP clone)

A single-page web app that looks like the Phantom wallet iPhone app. You type in how
much SOL (or other tokens) you "have"; it multiplies that by the **live market price**
and shows the portfolio value. Purely cosmetic — no wallet, no keys, no chain.

## Use it on your iPhone

1. Host the folder anywhere static (GitHub Pages, Netlify, Vercel, `python3 -m http.server`).
   Needs HTTPS for the install prompt and clipboard to work.
2. Open the URL in Safari → Share → **Add to Home Screen**.
3. Launch from the home screen: full screen, no browser chrome, own icon.

## Editing your balance

- Tap the big dollar amount (or **Swap** / **Buy**) to open **Edit holdings**.
- Type any amount per token; it saves instantly to `localStorage`, so it survives
  refreshes, app restarts and reboots.
- Add tokens from the row of chips (USDC, BTC, ETH, BONK, JUP, WIF), or `×` to remove one.
- Gear icon → account name, wallet address (or generate a random one), hide-balances
  toggle, and full reset.

## Prices

Refreshed every 30s, on tab focus, and on reconnect. Source order with automatic
fallback: **CoinGecko** → **Binance** → **Coinbase**. The last good prices are cached,
so a rate-limited or offline launch still shows a value (labelled "Cached · Nm old"
under the balance instead of "Live"). The 24h change line is derived from the same
24h data.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | Entire app — markup, styles, logic |
| `manifest.webmanifest` | Home-screen install metadata |
| `sw.js` | App-shell cache for offline launch (never caches price APIs) |
| `icon-180.png`, `icon-512.png` | Home-screen icons |

All state is device-local. Nothing is transmitted anywhere except the public price APIs.
