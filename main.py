import os, time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import yfinance as yf
from supabase import create_client, Client
from mangum import Mangum

app = FastAPI()

# Configurações do Supabase (Substitua pelos seus dados ou use variáveis de ambiente)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://vzkuutyodrrzitsehzhv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_uVJijNCB-weCW-BYdzSDZQ_1_D4s7Hm")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÃO DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache para armazenar informações das moedas e evitar múltiplas chamadas ao Supabase
currency_info_cache = {}
CACHE_EXPIRE_SECONDS = 300

async def get_currency_details(currency_code: str):
    current_time = time.time()
    if currency_code in currency_info_cache and \
       (current_time - currency_info_cache[currency_code]["timestamp"] < CACHE_EXPIRE_SECONDS):
        return currency_info_cache[currency_code]["data"]

    try:
        response = supabase.table("currencies").select("code, is_crypto").eq("code", currency_code).single().execute()
        data = response.data
        if data:
            currency_info_cache[currency_code] = {"data": data, "timestamp": current_time}
            return data
    except Exception as e:
        print(f"Erro ao buscar detalhes da moeda {currency_code} no Supabase: {e}")
    return None

async def get_all_currencies_details():
    current_time = time.time()
    if "all_currencies" in currency_info_cache and \
       (current_time - currency_info_cache["all_currencies"]["timestamp"] < CACHE_EXPIRE_SECONDS):
        return currency_info_cache["all_currencies"]["data"]

    try:
        response = supabase.table("currencies").select("code, is_crypto").execute()
        data = response.data
        if data:
            currency_info_cache["all_currencies"] = {"data": data, "timestamp": current_time}
            return data
    except Exception as e:
        print(f"Erro ao buscar todas as moedas no Supabase: {e}")
    return []

def get_yf_ticker(currency_code: str, is_crypto: bool):
    if currency_code == "USD":
        return "USD"
    if is_crypto:
        return f"{currency_code}-USD"
    return f"{currency_code}=X"

def fetch_price(ticker: str) -> float:
    if ticker == "USD":
        return 1.0
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception as e:
        print(f"Erro ao buscar preço para o ticker {ticker}: {e}")
    return None

cache_data = {}

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

    base_currency_details = await get_currency_details(base)
    if not base_currency_details:
        raise HTTPException(status_code=404, detail=f"Moeda base '{base}' não encontrada ou não suportada.")

    base_is_crypto = base_currency_details["is_crypto"]

    base_in_usd = 1.0
    if base != "USD":
        base_ticker = get_yf_ticker(base, base_is_crypto)
        price = fetch_price(base_ticker)
        if price:
            base_in_usd = price
        else:
            # Tenta a conversão inversa se a direta falhar (apenas para fiat)
            if not base_is_crypto:
                inv_ticker = get_yf_ticker("USD", False) # USD é fiat
                inv_price = fetch_price(get_yf_ticker(base, False))
                if inv_price:
                    base_in_usd = 1 / inv_price
                else:
                    raise HTTPException(status_code=404, detail=f"Não foi possível obter a cotação para a moeda base '{base}'.")
            else:
                raise HTTPException(status_code=404, detail=f"Não foi possível obter a cotação para a criptomoeda base '{base}'.")

    conversion_rates = {}
    all_currencies = await get_all_currencies_details()

    for currency_detail in all_currencies:
        code = currency_detail["code"]
        is_crypto = currency_detail["is_crypto"]

        if code == base:
            conversion_rates[code] = 1.0
            continue

        target_ticker = get_yf_ticker(code, is_crypto)
        target_price_usd = fetch_price(target_ticker)

        if target_price_usd is not None:
            rate = target_price_usd / base_in_usd
            conversion_rates[code] = round(rate, 8)
        else:
            print(f"Aviso: Não foi possível obter a cotação para {code} ({target_ticker}).")

    return {
        "result": "success",
        "base_code": base,
        "conversion_rates": conversion_rates
    }

handler = Mangum(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
