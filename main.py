import os
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import yfinance as yf
from supabase import create_client, Client
from mangum import Mangum

app = FastAPI()


# Configurações do Supabase (Substitua pelos seus dados ou use variáveis de ambiente)
SUPABASE_URL = "https://vzkuutyodrrzitsehzhv.supabase.co"
SUPABASE_KEY = "sb_publishable_uVJijNCB-weCW-BYdzSDZQ_1_D4s7Hm"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÃO DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TICKERS_MAP = {
    "BRL": "BRL=X", "USD": "USD", "EUR": "EURUSD=X",
    "GBP": "GBPUSD=X", "JPY": "JPY=X", "ARS": "ARS=X",
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
    "USDT": "USDT-USD", "ADA": "ADA-USD",
}


def fetch_price(ticker: str) -> float:
    if ticker == "USD":
        return 1.0
    try:
        data = yf.Ticker(ticker).history(period="1d")
        return float(data["Close"].iloc[-1]) if not data.empty else None
    except:
        return None


cache_data = {}
CACHE_EXPIRE_SECONDS = 300

# --- ROTA DE SAÚDE (PING NO SUPABASE) ---


@app.get("/health")
async def health_check():
    try:
        # O comando 'rpc' ou uma query simples mantém o banco ativo
        # .limit(1) em uma tabela qualquer ou um comando de sistema:
        supabase.table("profiles").select("*").limit(1).execute()
        

        return {"status": "ok", "db": "connected", "timestamp": time.time()}
    except Exception as e:
        # Se o banco estiver desligado, ele tentará religar ou avisará o erro
        return {"status": "error", "message": str(e)}


@app.get("/latest/{base}")
async def get_rates(base: str):
    base = base.upper()
    if base == "USD":
        base_in_usd = 1.0
    else:
        price = fetch_price(f"{base}USD=X")
        if not price:
            inv_price = fetch_price(f"USD{base}=X")
            if not inv_price:
                raise HTTPException(
                    status_code=404, detail="Moeda base não suportada")
            base_in_usd = 1 / inv_price
        else:
            base_in_usd = price

    conversion_rates = {}
    for code, ticker in TICKERS_MAP.items():
        if code == base:
            conversion_rates[code] = 1.0
            continue
        target_price_usd = fetch_price(ticker)
        if target_price_usd:
            rate = base_in_usd / target_price_usd
            conversion_rates[code] = round(rate, 8)

    return {
        "result": "success",
        "base_code": base,
        "conversion_rates": conversion_rates
    }

handler = Mangum(app)

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)
