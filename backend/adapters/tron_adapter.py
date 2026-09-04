from __future__ import annotations
import os
import datetime
import requests
from dotenv import load_dotenv
from backend.adapters.base_adapter import BaseChainAdapter
from backend.api.schemas import NormalizedTransaction, TxTypeRaw

load_dotenv()
API_KEY = os.getenv("TRONGRID_API_KEY")
BASE_URL = "https://api.trongrid.io"


class TronAdapter(BaseChainAdapter):
    """
    Tron adapter leveraging TronGrid API.
    Key advantage over Eth Phase 1: TronGrid's /v1/accounts/{addr}/transactions 
    endpoint returns token transfer events with token metadata directly, 
    no need for messy event log decoding.
    """

    def fetch_transactions(self, address: str) -> list[NormalizedTransaction]:
        """Fetch all transactions for a Tron address (native + token transfers)."""
        all_txs = []
        
        # TronGrid returns paginated results; fetch all
        offset = 0
        limit = 50
        max_iterations = 100  # safety limit
        iteration = 0

        while iteration < max_iterations:
            # Endpoint: /v1/accounts/{address}/transactions
            # Returns: native transfers + token transfers in one list
            url = f"{BASE_URL}/v1/accounts/{address}/transactions"
            params = {
                "limit": limit,
                "offset": offset,
                "only_confirmed": "true",
            }
            headers = {"TRON-PRO-API-KEY": API_KEY} if API_KEY else {}

            try:
                resp = requests.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"Error fetching Tron txs for {address}: {e}")
                break

            data = resp.json()
            transactions = data.get("data", [])

            if not transactions:
                break

            all_txs.extend(transactions)
            offset += limit
            iteration += 1

            # Stop if we got fewer than limit (indicates end of paginated results)
            if len(transactions) < limit:
                break

        # Normalize all transactions
        normalized = [self._normalize(tx) for tx in all_txs]
        return normalized

    def _normalize(self, raw_tx: dict) -> NormalizedTransaction:
        """
        Normalize a TronGrid transaction to canonical schema.
        
        TronGrid advantages over Etherscan:
        - Token transfers come pre-parsed in 'token_transfer_overview' field
        - No event log decoding needed
        - 'value' field includes amount in native SUN units
        """
        tx_hash = raw_tx.get("txID", "unknown")
        timestamp_ms = raw_tx.get("block_timestamp", 0)
        timestamp = datetime.datetime.utcfromtimestamp(timestamp_ms / 1000)
        block_number = raw_tx.get("blockNumber", 0)

        # Determine tx type and extract amount/token
        tx_type = TxTypeRaw.unknown
        from_addr = None
        to_addr = None
        value = 0.0
        token = "native"
        token_contract = None

        # Check for token transfers (cleaner in Tron than Ethereum)
        token_transfer_overview = raw_tx.get("token_transfer_overview", [])
        if token_transfer_overview:
            # TronGrid already decoded the token transfer for us
            transfer = token_transfer_overview[0]
            tx_type = TxTypeRaw.swap_event if "swap" in str(transfer).lower() else TxTypeRaw.transfer
            from_addr = transfer.get("from_address", "")
            to_addr = transfer.get("to_address", "")
            value = float(transfer.get("amount_str", "0")) / 1e6  # TRC20s are typically 6 decimals
            token_contract = transfer.get("contract_address", "")
            token = transfer.get("symbol", f"TRC20:{token_contract[:6]}")
        else:
            # Native TRX transfer
            tx_type = TxTypeRaw.transfer
            # For native transfers, extract from/to from raw_tx structure
            # TronGrid nests this in raw_data.contract[0].parameter.value
            contract = raw_tx.get("raw_data", {}).get("contract", [{}])[0]
            param_value = contract.get("parameter", {}).get("value", {})
            from_addr = param_value.get("owner_address", "")
            to_addr = param_value.get("to_address", "")
            value = float(param_value.get("amount", 0)) / 1e6  # TRX in SUN (1 TRX = 1e6 SUN)
            token = "TRX"
            token_contract = None

        # Gas equivalent for Tron (net energy spent)
        net_fee = raw_tx.get("net_fee", 0)
        gas_used = float(net_fee) if net_fee else None

        return NormalizedTransaction(
            tx_hash=tx_hash,
            chain="tron",
            from_address=from_addr,
            to_address=to_addr,
            value=value,
            token=token,
            token_contract=token_contract,
            timestamp=timestamp,
            block_number=block_number,
            tx_type_raw=tx_type,
            gas_used=gas_used,
        )


if __name__ == "__main__":
    # Smoke test: Try a known Tron USDT holder
    # (Teammate 1 will provide demo address once Phase 1 demo works)
    test_address = "TN3W4H6rK634By4gVCcwEJF0o67XChWNtb"  # Example USDT-heavy address
    adapter = TronAdapter()
    txs = adapter.fetch_transactions(test_address)
    print(f"Fetched {len(txs)} transactions")
    if txs:
        print(txs[0].model_dump_json(indent=2))
    else:
        print("No transactions found — check API key or address")