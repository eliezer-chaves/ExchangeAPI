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

    # 1. Busca detalhes da moeda base
    base_currency_details = await get_currency_details(base)
    if not base_currency_details:
        raise HTTPException(status_code=404, detail=f"Moeda base '{base}' não encontrada.")

    # 2. Obtém todas as moedas para retornar no mapa
    all_currencies = await get_all_currencies_details()
    conversion_rates = {}

    for currency_detail in all_currencies:
        code = currency_detail["code"]
        is_crypto = currency_detail["is_crypto"]

        if code == base:
            conversion_rates[code] = 1.0
            continue

        # 3. LÓGICA DE SENIOR: 
        # Retornamos o valor de cada moeda EM DÓLAR (Âncora).
        # O ExchangeService no Angular fará a regra de três (Cross Rate).
        ticker = get_yf_ticker(code, is_crypto)
        price_in_usd = fetch_price(ticker)

        if price_in_usd is not None:
            # Armazenamos o valor da moeda em relação ao USD
            # Ex: BRL -> 0.18 | BTC -> 65000.0 | EUR -> 1.08
            conversion_rates[code] = round(price_in_usd, 8)

    return {
        "result": "success",
        "base_code": base,
        "conversion_rates": conversion_rates
    }
handler = Mangum(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
