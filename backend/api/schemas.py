from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ChainEnum(str, Enum):
    ethereum = "ethereum"
    tron = "tron"
    bitcoin = "bitcoin"
    bnb = "bnb"
    polygon = "polygon"
    solana = "solana"


class TxTypeRaw(str, Enum):
    transfer = "transfer"
    contract_call = "contract_call"
    swap_event = "swap_event"
    bridge_lock = "bridge_lock"
    unknown = "unknown"


class NormalizedTransaction(BaseModel):
    tx_hash: str
    chain: ChainEnum
    from_address: str
    to_address: str
    value: float
    token: Optional[str] = None
    token_contract: Optional[str] = None
    timestamp: datetime
    block_number: int
    tx_type_raw: TxTypeRaw = TxTypeRaw.unknown
    gas_used: Optional[float] = None