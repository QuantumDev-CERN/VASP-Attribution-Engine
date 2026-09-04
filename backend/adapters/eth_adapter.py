from __future__ import annotations
import os
import datetime
import requests
from dotenv import load_dotenv
from backend.adapters.base_adapter import BaseChainAdapter
from backend.api.schemas import NormalizedTransaction

load_dotenv()
API_KEY = os.getenv("ETHERSCAN_API_KEY")
BASE_URL = "https://api.etherscan.io/v2/api"


class EthAdapter(BaseChainAdapter):
    def fetch_transactions(self, address: str) -> list[NormalizedTransaction]:
        params = {
            "chainid":"1",
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "asc",
            "apikey": API_KEY,
        }
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "0":
            error_message = data.get("result", "Unknown error")
            print(f"Error fetching transactions for address {address}: {error_message}")
            return []
        raw_txs = resp.json().get("result", [])
        return [self._normalize(tx) for tx in raw_txs]

    def _normalize(self, raw_tx: dict) -> NormalizedTransaction:
        return NormalizedTransaction(
            tx_hash=raw_tx["hash"],
            chain="ethereum",
            from_address=raw_tx["from"],
            to_address=raw_tx["to"],
            value=float(raw_tx["value"]) / 1e18,
            token="native",
            token_contract=None,
            timestamp=datetime.datetime.utcfromtimestamp(int(raw_tx["timeStamp"])),
            block_number=int(raw_tx["blockNumber"]),
            tx_type_raw="transfer",
            gas_used=float(raw_tx["gasUsed"]) if raw_tx.get("gasUsed") else None,
        )


if __name__ == "__main__":
    # quick smoke test — swap for demo_case.json address once Teammate 1 delivers it
    test_address = "0x59aAB1bd0d26290274398c07b55955c15425e16B"
    adapter = EthAdapter()
    txs = adapter.fetch_transactions(test_address)
    if txs:
        print(txs[0].model_dump_json(indent=2))
    else:
        print("No transactions found — check API key or address")