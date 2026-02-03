from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Importação necessária
import yfinance as yf
from mangum import Mangum
import uvicorn

app = FastAPI()

# --- CONFIGURAÇÃO DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite qualquer site (inclusive seu localhost e o deploy do Angular)
    allow_credentials=True,
    allow_methods=["*"], # Permite GET, POST, etc.
    allow_headers=["*"], # Permite qualquer cabeçalho
)

TICKERS_MAP = {
    "BRL": "BRL=X", "USD": "USD", "EUR": "EURUSD=X", 
    "GBP": "GBPUSD=X", "JPY": "JPY=X", "ARS": "ARS=X",
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
    "USDT": "USDT-USD", "ADA": "ADA-USD",
}

def fetch_price(ticker: str) -> float:
    if ticker == "USD": return 1.0
    try:
        data = yf.Ticker(ticker).history(period="1d")
        return float(data["Close"].iloc[-1]) if not data.empty else None
    except:
        return None

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
                raise HTTPException(status_code=404, detail="Moeda base não suportada")
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
