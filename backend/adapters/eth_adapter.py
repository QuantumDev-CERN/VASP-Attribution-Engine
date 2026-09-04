from __future__ import annotations
import os
import time
import datetime
import requests
from dotenv import load_dotenv
from backend.adapters.base_adapter import BaseChainAdapter
from backend.api.schemas import NormalizedTransaction, TxTypeRaw
from backend.adapters.dex_signatures import match_swap_topic, decode_swap_log, DexVersion

load_dotenv()
API_KEY = os.getenv("ETHERSCAN_API_KEY")
BASE_URL = "https://api.etherscan.io/v2/api"

# Etherscan free-tier is ~5 req/sec; receipt calls are 1-per-tx, so throttle
# to stay under that during a full trace of an address with many txs.
RECEIPT_CALL_DELAY_SECONDS = 0.21


class EthAdapter(BaseChainAdapter):
    def fetch_transactions(self, address: str, limit: int = 100) -> list[NormalizedTransaction]:
        params = {
            "chainid": "1",
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": limit,
            "sort": "desc",
            "apikey": API_KEY,
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"HTTP error fetching transactions for address {address}: {exc}")
            return []

        data = resp.json()

        if data.get("status") == "0":
            error_message = data.get("result", "Unknown error")
            print(f"Error fetching transactions for address {address}: {error_message}")
            return []
        raw_txs = data.get("result", [])
        return [self._normalize(tx) for tx in raw_txs]

    def _fetch_receipt_logs(self, tx_hash: str) -> list[dict]:
        """
        Fetch a transaction's receipt via Etherscan's proxy module and return
        its `logs` list (each with address/topics/data). Returns [] on any
        failure -- a missing receipt should degrade the tx to 'transfer'/
        'contract_call' classification, not crash the whole trace.
        """
        params = {
            "chainid": "1",
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
            "apikey": API_KEY,
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"HTTP error fetching receipt for {tx_hash}: {exc}")
            return []

        data = resp.json()
        result = data.get("result")
        if not result or not isinstance(result, dict):
            return []
        return result.get("logs", []) or []

    def _classify_and_decode(self, raw_tx: dict) -> tuple[TxTypeRaw, dict | None]:
        """
        Determine tx_type_raw for a transaction and, if it's a swap, return
        the decoded swap fields alongside the classification.

        Classification order:
          1. Any log's topic0 matches a known Swap signature -> swap_event
          2. No input data (plain value transfer) -> transfer
          3. Has input data / touches a contract but no Swap log -> contract_call
        """
        input_data = raw_tx.get("input", "0x")
        is_plain_transfer_shape = input_data in ("0x", "0x0", "", None)

        logs = self._fetch_receipt_logs(raw_tx["hash"])
        time.sleep(RECEIPT_CALL_DELAY_SECONDS)

        for log in logs:
            version = match_swap_topic(log.get("topics", []))
            if version is not None:
                try:
                    decoded = decode_swap_log(log.get("data", "0x"), version)
                except ValueError as exc:
                    print(f"Swap log decode failed for {raw_tx['hash']}: {exc}")
                    continue
                decoded["dex_version"] = version.value
                decoded["pool_or_pair_address"] = log.get("address")
                return TxTypeRaw.swap_event, decoded

        if is_plain_transfer_shape:
            return TxTypeRaw.transfer, None
        return TxTypeRaw.contract_call, None

    def _normalize(self, raw_tx: dict) -> NormalizedTransaction:
        tx_type, swap_data = self._classify_and_decode(raw_tx)

        if tx_type == TxTypeRaw.swap_event and swap_data is not None:
            # NOTE (Phase 1 scope): we surface the swap's pool/pair contract
            # address and the raw integer amount from the log. We deliberately
            # do NOT guess ERC-20 decimals here (18 for one token, 6 for
            # USDT/USDC, etc. all differ) -- resolving true decimal-adjusted
            # value requires a per-token-contract decimals() lookup, which is
            # a Phase 3+ registry/enrichment concern, not adapter-layer.
            # `value` therefore holds the raw on-chain integer for the swap's
            # output leg until that enrichment step exists.
            if swap_data.get("dex_version") == DexVersion.v2.value:
                out_amount = max(swap_data["amount0_out"], swap_data["amount1_out"])
            else:  # v3: amount0/amount1 signed, negative = leaving the pool (to the trader)
                out_amount = abs(min(swap_data["amount0"], swap_data["amount1"]))

            return NormalizedTransaction(
                tx_hash=raw_tx["hash"],
                chain="ethereum",
                from_address=raw_tx["from"],
                to_address=raw_tx["to"],
                value=float(out_amount),
                token=f"unresolved-erc20:{swap_data.get('dex_version')}",
                token_contract=swap_data.get("pool_or_pair_address"),
                timestamp=datetime.datetime.utcfromtimestamp(int(raw_tx["timeStamp"])),
                block_number=int(raw_tx["blockNumber"]),
                tx_type_raw=TxTypeRaw.swap_event,
                gas_used=float(raw_tx["gasUsed"]) if raw_tx.get("gasUsed") else None,
            )

        return NormalizedTransaction(
            tx_hash=raw_tx["hash"],
            chain="ethereum",
            from_address=raw_tx["from"],
            to_address=raw_tx["to"],
            value=float(raw_tx["value"]) / 1e18,
            token="native",
            token_contract=None,
            timestamp=datetime.datetime.fromtimestamp(int(raw_tx["timeStamp"]), datetime.timezone.utc),
            block_number=int(raw_tx["blockNumber"]),
            tx_type_raw=tx_type,
            gas_used=float(raw_tx["gasUsed"]) if raw_tx.get("gasUsed") else None,
        )


if __name__ == "__main__":
    # quick smoke test -- swap for demo_case.json address once Teammate 1 delivers it
    test_address = "0x43684D03D81d3a4C70da68feBDd61029d426F042"  # Binance-tagged, transfer-heavy
    adapter = EthAdapter()
    txs = adapter.fetch_transactions(test_address)
    if txs:
        print(f"{len(txs)} transactions fetched")
        tag_counts = {}
        for tx in txs:
            tag_counts[tx.tx_type_raw] = tag_counts.get(tx.tx_type_raw, 0) + 1
        print("Tag counts:", tag_counts)
        print(txs[0].model_dump_json(indent=2))
    else:
        print("No transactions found -- check API key or address")