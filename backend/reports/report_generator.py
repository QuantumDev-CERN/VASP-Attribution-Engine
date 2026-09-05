import json
from datetime import datetime, timezone
from backend.reports.cert_hash import generate_evidentiary_cert

def compile_investigation_report(
    case_id: str,
    suspect_address: str,
    chain: str,
    path: list,
    confidence_score: int,
    confidence_band: str,
    reason_string: str,
    linked_cases: list,
    freeze_recommendation: str | None
) -> dict:
    raw_report = {
        "metadata": {
            "engine": "VASP Attribution Engine",
            "jurisdiction": "FIU-IND / LEA Compliance",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id
        },
        "target_profile": {
            "suspect_address": suspect_address,
            "chain": chain
        },
        "attribution_result": {
            "confidence_score": confidence_score,
            "confidence_band": confidence_band,
            "scoring_rationale": reason_string,
            "parallel_actions": {
                "stablecoin_issuer_freeze": freeze_recommendation
            }
        },
        "intelligence_links": {
            "syndicate_cross_case_matches": linked_cases
        },
        "trace_path_hops": [
            {
                "hop_index": i + 1,
                "tx_hash": tx.tx_hash,
                "from": tx.from_address,
                "to": tx.to_address,
                "value": tx.value,
                "token": tx.token,
                "timestamp": tx.timestamp.isoformat()
            }
            for i, tx in enumerate(path)
        ]
    }
    
    return generate_evidentiary_cert(raw_report)

if __name__ == "__main__":
    from backend.api.schemas import NormalizedTransaction, ChainEnum, TxTypeRaw
    
    mock_path = [
        NormalizedTransaction(
            tx_hash="0xdeadbeef", chain=ChainEnum.ethereum, 
            from_address="0xSuspect", to_address="0xBinanceHot",
            value=5.0, token="native", timestamp=datetime.now(timezone.utc), 
            block_number=12345, tx_type_raw=TxTypeRaw.transfer
        )
    ]
    
    report = compile_investigation_report(
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
    
    print(json.dumps(report, indent=2))