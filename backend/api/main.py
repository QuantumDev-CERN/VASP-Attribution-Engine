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
def eth_test(address: str = "0xd8dA6BF26964af9D7eEd9e03E53415D37aA96045"):
    adapter = EthAdapter()
    txs = adapter.fetch_transactions(address)
    return txs[0] if txs else {"error": "no transactions found"}