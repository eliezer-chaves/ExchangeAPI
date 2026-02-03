from fastapi import FastAPI, HTTPException
import yfinance as yf
import pandas as pd
from typing import Dict

app = FastAPI()

# --- LISTA DE TICKERS COMUNS NO YFINANCE ---
# Moedas (Forex): Formato "BASEQUOTE=X" (ex: USDBRL=X)
# Criptos: Formato "SYMBOL-USD" (ex: BTC-USD)
TICKERS_MAP = {
    # Moedas Tradicionais
    "BRL": "BRL=X",    # Real Brasileiro
    "USD": "USD",      # Dólar (Base comum)
    "EUR": "EURUSD=X", # Euro
    "GBP": "GBPUSD=X", # Libra Esterlina
    "JPY": "JPY=X",    # Iene Japonês
    "ARS": "ARS=X",    # Peso Argentino
    
    # Criptomoedas
    "BTC": "BTC-USD",  # Bitcoin
    "ETH": "ETH-USD",  # Ethereum
    "SOL": "SOL-USD",  # Solana
    "USDT": "USDT-USD",# Tether
    "ADA": "ADA-USD",  # Cardano
}

def fetch_price(ticker: str) -> float:
    if ticker == "USD": return 1.0
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except:
        return None

@app.get("/latest/{base}")
async def get_rates(base: str):
    base = base.upper()
    
    # Pegamos o preço da moeda base em relação ao Dólar (âncora)
    # Se base é BRL, precisamos saber quanto 1 BRL vale em USD para converter o resto
    if base == "USD":
        base_in_usd = 1.0
    else:
        # Tenta buscar o par direto (Ex: BRLUSD=X)
        price = fetch_price(f"{base}USD=X")
        # Se não achar, tenta o inverso (1 / USDBRL=X)
        if not price:
            inv_price = fetch_price(f"USD{base}=X")
            if not inv_price:
                raise HTTPException(status_code=404, detail="Moeda base não suportada")
            base_in_usd = 1 / inv_price
        else:
            base_in_usd = price

    conversion_rates = {}
    
    # Calcula taxas para todas as outras moedas da nossa lista
    for code, ticker in TICKERS_MAP.items():
        if code == base:
            conversion_rates[code] = 1.0
            continue
            
        target_price_usd = fetch_price(ticker)
        
        if target_price_usd:
            # Lógica: Se 1 BTC = 50k USD e 1 BRL = 0.20 USD
            # Então 1 BRL = 0.20 / 50000 BTC
            # Mas o Angular espera: Quanto da moeda destino eu compro com 1 unidade da base.
            # Taxa = Valor_Base_em_USD / Valor_Destino_em_USD
            rate = base_in_usd / target_price_usd
            conversion_rates[code] = round(rate, 8)

    return {
        "result": "success",
        "base_code": base,
        "conversion_rates": conversion_rates
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)