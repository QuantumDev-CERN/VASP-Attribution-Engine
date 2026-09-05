from typing import List
from backend.api.schemas import NormalizedTransaction

# Mainnet contract addresses for Tether and Circle
KNOWN_STABLECOIN_CONTRACTS = {
    "ethereum": [
        "0xdac17f958d2ee523a2206206994597c13d831ec7", # USDT
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC
    ],
    "tron": [
        "tr7nhqjekqxgtci8q8zy4pl8otszgjlj6t" # USDT TRC20
    ]
}

def evaluate_stablecoin_freeze(path: List[NormalizedTransaction]) -> str | None:
    """
    Checks if the terminal address is holding stablecoins.
    If so, surfaces the parallel freeze recommendation.
    """
    if not path:
        return None
        
    terminal_tx = path[-1]
    is_stablecoin = False
    
    if terminal_tx.token and terminal_tx.token.upper() in ["USDT", "USDC"]:
        is_stablecoin = True
        
    if terminal_tx.token_contract:
        chain_contracts = KNOWN_STABLECOIN_CONTRACTS.get(terminal_tx.chain.value, [])
        if terminal_tx.token_contract.lower() in chain_contracts:
            is_stablecoin = True
            
    if is_stablecoin:
        return (
            "PARALLEL FREEZE RECOMMENDATION: The terminal address holds USDT/USDC. "
            "Execute a parallel issuer-level freeze by requesting Tether/Circle to invoke "
            "the `addBlackList` contract function. This runs alongside VASP disclosure, not as a replacement."
        )
        
    return None

if __name__ == "__main__":
    from datetime import datetime, timezone
    from backend.api.schemas import ChainEnum, TxTypeRaw
    
    mock_path = [
        NormalizedTransaction(
            tx_hash="0xabc", chain=ChainEnum.ethereum, from_address="0x1", to_address="0x2",
            value=100.0, token="USDT", token_contract="0xdac17f958d2ee523a2206206994597c13d831ec7",
            timestamp=datetime.now(timezone.utc), block_number=1, tx_type_raw=TxTypeRaw.transfer
        )
    ]
    print(evaluate_stablecoin_freeze(mock_path))