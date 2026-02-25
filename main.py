import os
import time
import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from mangum import Mangum

# -------------------------------
# App
# -------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Supabase
# -------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://vzkuutyodrrzitsehzhv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_uVJijNCB-weCW-BYdzSDZQ_1_D4s7Hm")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# Cache simples
# -------------------------------
CACHE_TTL = 300
currency_cache = {}

# -------------------------------
# Helpers
# -------------------------------
def get_yf_ticker(code: str, is_crypto: bool) -> str:
    if code == "USD":
        return "USD"
    if is_crypto:
        return f"{code}-USD"
    return f"{code}=X"


def fetch_usd_price(ticker: str) -> float | None:
    if ticker == "USD":
        return 1.0

    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception as e:
        print(f"[yfinance] erro {ticker}: {e}")

    return None


def get_all_currencies():
    now = time.time()
    if "all" in currency_cache and now - currency_cache["all"]["ts"] < CACHE_TTL:
        return currency_cache["all"]["data"]

    res = supabase.table("currencies").select("code, is_crypto").execute()
    if not res.data:
        raise HTTPException(500, "Currencies not found")

    currency_cache["all"] = {"data": res.data, "ts": now}
    return res.data


# -------------------------------
# Endpoint
# -------------------------------
@app.get("/latest/{base}")
async def latest(base: str):
    currencies = get_all_currencies()

    base_currency = next((c for c in currencies if c["code"] == base), None)
    if not base_currency:
        raise HTTPException(400, "Invalid base currency")

    # --- base → USD ---
    base_ticker = get_yf_ticker(base, base_currency["is_crypto"])
    base_usd_price = fetch_usd_price(base_ticker)

    if not base_usd_price:
        raise HTTPException(400, "Base currency unavailable")

    rates = {}
    unit_reference = {}

    for currency in currencies:
        ticker = get_yf_ticker(currency["code"], currency["is_crypto"])
        usd_price = fetch_usd_price(ticker)

        if not usd_price:
            continue

        # USD → BASE
        value_in_base = usd_price / base_usd_price

        rates[currency["code"]] = round(value_in_base, 10)
        unit_reference[currency["code"]] = (
            f"1 {currency['code']} = {value_in_base:.6f} {base}"
        )

    return {
        "result": "success",
        "base": base,
        "rates": rates,
        "unit_reference": unit_reference,
        "timestamp": time.time(),
    }


handler = Mangum(app)
