import json, os, sys, time, urllib.parse, urllib.request

def num(name, default):
    v = os.environ.get(name, "").strip()
    try:
        return float(v) if v else default
    except ValueError:
        return default

TH_1H = num("ALERT_1H_PCT", 3.0)
TH_24H = num("ALERT_24H_PCT", 8.0)
COOLDOWN_MIN = num("COOLDOWN_MIN", 120)
TOP_N = 10
STATE_FILE = "state.json"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
KEY = os.environ.get("COINGECKO_KEY", "").strip()
MANUAL = os.environ.get("MANUAL") == "true"

# Stablecoins plus wrapped/staked copies of other coins
EXCLUDE = {
    "tether", "usd-coin", "usds", "ethena-usde", "dai", "first-digital-usd",
    "usd1-wlfi", "paypal-usd", "usdd", "true-usd", "global-dollar", "usdtb",
    "wrapped-bitcoin", "weth", "staked-ether", "wrapped-steth", "wrapped-eeth",
    "coinbase-wrapped-btc", "wrapped-beacon-eth", "binance-staked-eth",
}

def is_excluded(c):
    if c["id"] in EXCLUDE:
        return True
    p = c.get("current_price") or 0
    chg = abs(c.get("price_change_percentage_24h_in_currency") or 0)
    return 0.97 <= p <= 1.03 and chg < 1.5  # looks like a $1 stablecoin

def price(p):
    return f"{p:,.2f}" if p >= 1 else f"{p:.4f}"

def send(text):
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    urllib.request.urlopen(
        "https://api.telegram.org/bot" + TOKEN + "/sendMessage", data=data, timeout=30)

def fetch():
    url = "https://api.coingecko.com/api/v3/coins/markets?" + urllib.parse.urlencode({
        "vs_currency": "usd", "order": "market_cap_desc", "per_page": 40,
        "page": 1, "price_change_percentage": "1h,24h"})
    headers = {"User-Agent": "crypto-alert-agent"}
    if KEY:
        headers["x-cg-demo-api-key"] = KEY
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)

def main():
    try:
        coins = fetch()
    except Exception as e:
        print("Fetch failed:", e)
        if MANUAL:
            send("Could not fetch prices: " + str(e))
        sys.exit(0)

    picked = [c for c in coins if not is_excluded(c)][:TOP_N]

    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except Exception:
        state = {}

    now = time.time()
    alerts = []
    for c in picked:
        for key, th in (("1h", TH_1H), ("24h", TH_24H)):
            chg = c.get(f"price_change_percentage_{key}_in_currency")
            if chg is None or abs(chg) < th:
                continue
            k = f"{c['id']}:{key}"
            if now - state.get(k, 0) < COOLDOWN_MIN * 60:
                continue
            state[k] = now
            icon = "🟢" if chg > 0 else "🔴"
            alerts.append(f"{icon} {c['symbol'].upper()} {chg:+.2f}% in {key} (${price(c['current_price'])})")

    if alerts:
        send("Crypto alert\n" + "\n".join(alerts))
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)

    if MANUAL:
        lines = ["✅ Crypto alert bot is running",
                 f"Alert when 1h ≥ {TH_1H}% or 24h ≥ {TH_24H}%", ""]
        for c in picked:
            c1 = c.get("price_change_percentage_1h_in_currency") or 0
            c24 = c.get("price_change_percentage_24h_in_currency") or 0
            lines.append(f"{c['symbol'].upper()} ${price(c['current_price'])} | 1h {c1:+.1f}% | 24h {c24:+.1f}%")
        send("\n".join(lines))

main()
