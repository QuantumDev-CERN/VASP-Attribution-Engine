from fastapi import FastAPI
from backend.db.models import init_db
from backend.adapters.eth_adapter import EthAdapter
from backend.api.sahyog_stub import router as sahyog_router
from backend.reports.report_generator import compile_investigation_report
from datetime import datetime, timezone
from backend.api.schemas import NormalizedTransaction, ChainEnum, TxTypeRaw

app = FastAPI(title="VASP Attribution Engine")

app.include_router(sahyog_router)

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/report/demo")
def get_demo_report():
    mock_path = [
        NormalizedTransaction(
            tx_hash="0xdeadbeef", chain=ChainEnum.ethereum, 
            from_address="0xSuspect", to_address="0xBinanceHot",
            value=5.0, token="native", timestamp=datetime.now(timezone.utc), 
            block_number=12345, tx_type_raw=TxTypeRaw.transfer
        )
    ]
    return compile_investigation_report(
        case_id="FIR-2026-001",
        suspect_address="0xSuspect",
        chain="ethereum",
        path=mock_path,
        confidence_score=90,
        confidence_band="High",
        reason_string="1 hop (direct) | passed through confirmed sweep",
        linked_cases=["FIR-2023-001"],
        freeze_recommendation=None
    )