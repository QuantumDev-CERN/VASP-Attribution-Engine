"""
Known DEX Swap event signatures for Tron chains + decoders.

Tron DEXes (SunSwap, PancakeSwap-Tron, JustSwap) fork Uniswap V2/V3, so they
reuse the same Swap event signatures. topic0 values are keccak256 hashes of
the canonical event signatures — same as Ethereum.

Independently verified:
    from Crypto.Hash import keccak
    h = keccak.new(digest_bits=256)
    h.update(b"Swap(address,uint256,uint256,uint256,uint256,address)")
    print("0x" + h.hexdigest())
"""
from __future__ import annotations
from enum import Enum


class DexVersion(str, Enum):
    v2 = "v2"  # SunSwap V1/V2, PancakeSwap-Tron V2, JustSwap (V2 forks)
    v3 = "v3"  # Uniswap V3 forks on Tron (if they exist)


# Swap(address,uint256,uint256,uint256,uint256,address)
# Same as Uniswap V2 — Tron DEXes reuse this signature
UNISWAP_V2_SWAP_TOPIC0 = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

# Swap(address,address,int256,int256,uint160,uint128,int24)
# Same as Uniswap V3 — Tron V3 forks reuse this
UNISWAP_V3_SWAP_TOPIC0 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"

SWAP_TOPIC0: dict[str, DexVersion] = {
    UNISWAP_V2_SWAP_TOPIC0: DexVersion.v2,
    UNISWAP_V3_SWAP_TOPIC0: DexVersion.v3,
}


def match_swap_topic(topics: list[str]) -> DexVersion | None:
    """Return the DexVersion if this log's topic0 is a known Swap signature, else None."""
    if not topics:
        return None
    topic0 = topics[0].lower()
    for known, version in SWAP_TOPIC0.items():
        if known.lower() == topic0:
            return version
    return None


def _hex_to_int(word: str) -> int:
    """Parse a 32-byte hex word as an unsigned integer."""
    return int(word, 16)


def _hex_to_signed_int(word: str, bits: int = 256) -> int:
    """Parse a 32-byte hex word as a two's-complement signed integer."""
    val = int(word, 16)
    if val >= 2 ** (bits - 1):
        val -= 2 ** bits
    return val


def _split_words(data: str) -> list[str]:
    """Split a 0x-prefixed hex `data` blob into 32-byte (64 hex-char) words."""
    body = data[2:] if data.startswith("0x") else data
    return [body[i:i + 64] for i in range(0, len(body), 64)]


def decode_swap_log(data: str, version: DexVersion) -> dict:
    """
    Decode a Swap event log's `data` field for Tron DEXes.
    
    Same decoding logic as Ethereum (Tron event logs use same ABI encoding).
    Raises ValueError if data doesn't match expected word count for the version.
    """
    words = _split_words(data)

    if version == DexVersion.v2:
        # amount0In, amount1In, amount0Out, amount1Out  (4 x uint256)
        if len(words) != 4:
            raise ValueError(f"expected 4 words for V2 Swap data, got {len(words)}")
        amount0_in, amount1_in, amount0_out, amount1_out = (_hex_to_int(w) for w in words)
        return {
            "amount0_in": amount0_in,
            "amount1_in": amount1_in,
            "amount0_out": amount0_out,
            "amount1_out": amount1_out,
        }

    if version == DexVersion.v3:
        # amount0 (int256), amount1 (int256), sqrtPriceX96 (uint160),
        # liquidity (uint128), tick (int24)
        if len(words) != 5:
            raise ValueError(f"expected 5 words for V3 Swap data, got {len(words)}")
        amount0 = _hex_to_signed_int(words[0])
        amount1 = _hex_to_signed_int(words[1])
        sqrt_price_x96 = _hex_to_int(words[2])
        liquidity = _hex_to_int(words[3])
        tick = _hex_to_signed_int(words[4])
        return {
            "amount0": amount0,
            "amount1": amount1,
            "sqrt_price_x96": sqrt_price_x96,
            "liquidity": liquidity,
            "tick": tick,
        }

    raise ValueError(f"unknown DexVersion: {version}")
