from __future__ import annotations
import os
import time
import datetime
from datetime import timezone
import requests
from typing import Dict
from dotenv import load_dotenv
from backend.adapters.base_adapter import BaseChainAdapter
from backend.api.schemas import NormalizedTransaction, TxTypeRaw
from backend.adapters.tron_dex_signatures import match_swap_topic, decode_swap_log, DexVersion

load_dotenv()
API_KEY = os.getenv("TRONGRID_API_KEY")
BASE_URL = "https://api.trongrid.io"

# Rate limiting: 0.05s = 20 req/sec (safe for free tier ~5 req/sec when batched)
RECEIPT_FETCH_DELAY = 0.05


class TronAdapter(BaseChainAdapter):
    """
    Tron adapter leveraging TronGrid API — comprehensive event detection.
    """

    def fetch_transactions(self, address: str) -> list[NormalizedTransaction]:
        """Fetch ALL transaction types for a Tron address."""
        
        tx_map: Dict[str, dict] = {}
        
        # Endpoint A: TRC-20 token transfers
        print(f"[TronAdapter] Fetching TRC-20 transfers for {address}...")
        trc20_txs = self._fetch_trc20_transfers(address)
        for tx in trc20_txs:
            tx_hash = tx.get("transaction_id", tx.get("txID", "unknown"))
            tx_map[tx_hash] = {**tx_map.get(tx_hash, {}), **tx, "_source": "trc20"}
        print(f"  → Got {len(trc20_txs)} TRC-20 transfers")

        # Endpoint B: Native TRX transfers + contract calls
        print(f"[TronAdapter] Fetching native TRX + contract txs for {address}...")
        native_txs = self._fetch_native_and_contract_txs(address)
        for tx in native_txs:
            tx_hash = tx.get("txID", "unknown")
            tx_map[tx_hash] = {**tx_map.get(tx_hash, {}), **tx, "_source": "native"}
        print(f"  → Got {len(native_txs)} native/contract transactions")

        # Endpoint C: Fetch receipts with logs for swap detection
        print(f"[TronAdapter] Fetching transaction info for swap detection...")
        receipts_fetched = 0
        receipts_with_logs = 0
        swaps_found_in_logs = 0
        
        native_txs_items = [(h, d) for h, d in tx_map.items() if d.get("_source") == "native"]
        native_txs_count = len(native_txs_items)

        for i, (tx_hash, tx_data) in enumerate(native_txs_items):
            receipt = self._fetch_receipt(tx_hash)
            if receipt:
                tx_map[tx_hash]["receipt"] = receipt
                receipts_fetched += 1

                # DEBUG: Check if this receipt has logs
                logs = receipt.get("log", [])
                if logs:
                    receipts_with_logs += 1
                    # Check if any logs are swap events
                    for log in logs:
                        raw_topics = log.get("topics", [])
                        # FIX: Add 0x prefix to topics for standard EVM matching
                        topics = [t if t.startswith("0x") else f"0x{t}" for t in raw_topics]
                        
                        version = match_swap_topic(topics)
                        if version:
                            swaps_found_in_logs += 1
                            break

            time.sleep(RECEIPT_FETCH_DELAY)

            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{native_txs_count}] Fetched info, {receipts_with_logs} have logs, {swaps_found_in_logs} have swaps")

        print(f"  → Fetched {receipts_fetched} transaction infos total")
        print(f"  → {receipts_with_logs} had event logs")
        print(f"  → {swaps_found_in_logs} contained swap events")

        all_txs = list(tx_map.values())
        normalized = [self._normalize(tx) for tx in all_txs]
        return normalized

    def _fetch_trc20_transfers(self, address: str, limit: int = 100) -> list[dict]:
        all_txs = []
        fingerprint = None
        max_iterations = 50
        iteration = 0

        while iteration < max_iterations:
            url = f"{BASE_URL}/v1/accounts/{address}/transactions/trc20"
            params = {"limit": limit, "only_confirmed": "true"}
            if fingerprint:
                params["fingerprint"] = fingerprint

            headers = {"TRON-PRO-API-KEY": API_KEY} if API_KEY else {}

            try:
                resp = requests.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [TRC-20] Error: {e}")
                break

            data = resp.json()
            transactions = data.get("data", [])
            if not transactions:
                break

            all_txs.extend(transactions)
            iteration += 1

            meta = data.get("meta", {})
            fingerprint = meta.get("fingerprint")
            if not fingerprint:
                break

        return all_txs

    def _fetch_native_and_contract_txs(self, address: str, limit: int = 100) -> list[dict]:
        all_txs = []
        fingerprint = None
        max_iterations = 50
        iteration = 0

        while iteration < max_iterations:
            url = f"{BASE_URL}/v1/accounts/{address}/transactions"
            params = {"limit": limit, "only_confirmed": "true"}
            if fingerprint:
                params["fingerprint"] = fingerprint

            headers = {"TRON-PRO-API-KEY": API_KEY} if API_KEY else {}

            try:
                resp = requests.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [Native/Contract] Error: {e}")
                break

            data = resp.json()
            transactions = data.get("data", [])
            if not transactions:
                break

            all_txs.extend(transactions)
            iteration += 1

            meta = data.get("meta", {})
            fingerprint = meta.get("fingerprint")
            if not fingerprint:
                break

        return all_txs

    def _fetch_receipt(self, tx_hash: str) -> dict | None:
        url = f"{BASE_URL}/wallet/gettransactioninfobyid"
        headers = {"TRON-PRO-API-KEY": API_KEY} if API_KEY else {}

        try:
            resp = requests.post(url, json={"value": tx_hash}, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            return None

        data = resp.json()
        return data if data else None

    def _extract_logs(self, raw_tx: dict) -> list[dict]:
        receipt = raw_tx.get("receipt", {})
        if not isinstance(receipt, dict):
            return []
        logs = receipt.get("log", [])
        return logs if isinstance(logs, list) else []

    def _classify_and_decode(self, raw_tx: dict) -> tuple[TxTypeRaw, dict | None]:
        logs = self._extract_logs(raw_tx)

        for log in logs:
            raw_topics = log.get("topics", [])
            # FIX: Add 0x prefix to topics
            topics = [t if t.startswith("0x") else f"0x{t}" for t in raw_topics]
            
            version = match_swap_topic(topics)
            if version is not None:
                try:
                    raw_data = log.get("data", "")
                    # FIX: Add 0x prefix to data
                    data = raw_data if raw_data.startswith("0x") else f"0x{raw_data}"
                    
                    decoded = decode_swap_log(data, version)
                except ValueError as exc:
                    print(f"  [Swap decode] Failed for {raw_tx.get('txID', 'unknown')}: {exc}")
                    continue
                decoded["dex_version"] = version.value
                decoded["pool_or_pair_address"] = log.get("address")
                return TxTypeRaw.swap_event, decoded

        token_transfer_overview = raw_tx.get("token_transfer_overview", [])
        if token_transfer_overview:
            return TxTypeRaw.transfer, None

        contract = raw_tx.get("raw_data", {}).get("contract", [{}])[0]
        if contract:
            return TxTypeRaw.transfer, None

        return TxTypeRaw.contract_call, None

    def _normalize(self, raw_tx: dict) -> NormalizedTransaction:
        source = raw_tx.get("_source", "unknown")

        if source == "trc20":
            tx_hash = raw_tx.get("transaction_id", raw_tx.get("txID", "unknown"))
            timestamp_ms = raw_tx.get("block_timestamp", 0)
            # FIX: Use timezone-aware UTC datetime
            timestamp = datetime.datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)
            
            from_addr = raw_tx.get("from", "")
            to_addr = raw_tx.get("to", "")
            raw_value = raw_tx.get("value", "0")
            
            token_info = raw_tx.get("token_info", {})
            token_contract = token_info.get("address", "")
            
            try:
                value_float = float(raw_value)
            except ValueError:
                value_float = 0.0

            return NormalizedTransaction(
                tx_hash=tx_hash,
                chain="tron",
                from_address=from_addr,
                to_address=to_addr,
                value=value_float,
                token=f"unresolved-erc20:tron",
                token_contract=token_contract,
                timestamp=timestamp,
                block_number=0,
                tx_type_raw=TxTypeRaw.transfer,
                gas_used=None,
            )

        tx_hash = raw_tx.get("txID", "unknown")
        timestamp_ms = raw_tx.get("block_timestamp", 0)
        # FIX: Use timezone-aware UTC datetime
        timestamp = datetime.datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)
        block_number = raw_tx.get("blockNumber", 0)
        net_fee = raw_tx.get("net_fee", 0)
        gas_used = float(net_fee) if net_fee else None

        tx_type, swap_data = self._classify_and_decode(raw_tx)

        if tx_type == TxTypeRaw.swap_event and swap_data is not None:
            if swap_data.get("dex_version") == DexVersion.v2.value:
                out_amount = max(swap_data["amount0_out"], swap_data["amount1_out"])
            else:  # v3
                out_amount = abs(min(swap_data["amount0"], swap_data["amount1"]))

            return NormalizedTransaction(
                tx_hash=tx_hash,
                chain="tron",
                from_address=raw_tx.get("from", ""),
                to_address=raw_tx.get("to", ""),
                value=float(out_amount),
                token=f"unresolved-erc20:{swap_data.get('dex_version')}",
                token_contract=swap_data.get("pool_or_pair_address"),
                timestamp=timestamp,
                block_number=block_number,
                tx_type_raw=TxTypeRaw.swap_event,
                gas_used=gas_used,
            )

        contract = raw_tx.get("raw_data", {}).get("contract", [{}])[0]
        param_value = contract.get("parameter", {}).get("value", {})
        if param_value.get("amount") is not None:
            return NormalizedTransaction(
                tx_hash=tx_hash,
                chain="tron",
                from_address=param_value.get("owner_address", ""),
                to_address=param_value.get("to_address", ""),
                value=float(param_value.get("amount", 0)) / 1e6,
                token="TRX",
                token_contract=None,
                timestamp=timestamp,
                block_number=block_number,
                tx_type_raw=TxTypeRaw.transfer,
                gas_used=gas_used,
            )

        return NormalizedTransaction(
            tx_hash=tx_hash,
            chain="tron",
            from_address="",
            to_address="",
            value=0.0,
            token="unknown",
            token_contract=None,
            timestamp=timestamp,
            block_number=block_number,
            tx_type_raw=TxTypeRaw.contract_call,
            gas_used=gas_used,
        )


if __name__ == "__main__":
    test_address = "TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax"
    adapter = TronAdapter()
    txs = adapter.fetch_transactions(test_address)
    print(f"\nFetched {len(txs)} transactions")
    if txs:
        tag_counts = {}
        for tx in txs:
            tag = tx.tx_type_raw.value if hasattr(tx.tx_type_raw, 'value') else str(tx.tx_type_raw)
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        print("Tag counts:", tag_counts)
    else:
        print("No transactions found")