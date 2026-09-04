from fastapi import FastAPI
from backend.db.models import init_db
from backend.adapters.eth_adapter import EthAdapter

app = FastAPI(title="VASP Attribution Engine")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug/eth-test")
def eth_test(address: str = "0x59aAB1bd0d26290274398c07b55955c15425e16B"):
    adapter = EthAdapter()
    txs = adapter.fetch_transactions(address)
    return txs[0] if txs else {"error": "no transactions found"}