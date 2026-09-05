import json
from typing import List, Dict, Optional
from backend.api.schemas import NormalizedTransaction, ChainEnum

def load_registry(filepath: str) -> dict:
    with open(filepath, 'r') as f:
        return json.load(f)

def get_vasp_name(chain: ChainEnum, address: str, registry: dict) -> Optional[str]:
    chain_str = chain.value
    chain_registry = registry.get(chain_str, {})
    
    # Ethereum addresses are hex (case-insensitive); Tron Base58 is case-sensitive
    lookup_addr = address.lower() if chain_str == "ethereum" else address
    vasp_data = chain_registry.get(lookup_addr)
    
    return vasp_data.get("name") if vasp_data else None

def detect_sweeps(transactions: List[NormalizedTransaction], vasp_labels: dict) -> Dict[str, str]:
    """
    Analyzes normalized transactions to detect many-in/few-out sweeps into known VASPs.
    Returns a dictionary of new labels to apply: { "address": "Label String" }
    """
    new_labels = {}
    
    # 1. Identify txs depositing directly into a known VASP
    vasp_deposits = []
    for tx in transactions:
        if tx.to_address:
            vasp_name = get_vasp_name(tx.chain, tx.to_address, vasp_labels)
            if vasp_name:
                vasp_deposits.append((tx, vasp_name))
    
    # 2. Look up the chain: who fed the address that deposited to the VASP?
    for deposit_tx, target_vasp_name in vasp_deposits:
        forwarder_address = deposit_tx.from_address
        chain = deposit_tx.chain
        
        # 3. Find all txs feeding INTO this forwarder
        feeding_txs = [
            tx for tx in transactions 
            if tx.to_address == forwarder_address and tx.chain == chain
        ]
        
        # Heuristic: If multiple distinct addresses fund the forwarder before it deposits, it's a sweep.
        unique_contributors = {tx.from_address for tx in feeding_txs if tx.from_address}
        
        if len(unique_contributors) > 1:
            # Format addresses consistently for the output dictionary
            fmt_forwarder = forwarder_address.lower() if chain.value == "ethereum" else forwarder_address
            new_labels[fmt_forwarder] = "sweep-forwarder"
            
            for contributor in unique_contributors:
                fmt_contrib = contributor.lower() if chain.value == "ethereum" else contributor
                
                # Assign contributor label if it's not already a known exchange itself
                if not get_vasp_name(chain, fmt_contrib, vasp_labels):  
                    new_labels[fmt_contrib] = f"sweep-contributor (to {target_vasp_name})"
                    
    return new_labels


if __name__ == "__main__":
    import os
    from datetime import datetime, timezone
    from backend.api.schemas import TxTypeRaw

    # 1. Load the nested registry from the filesystem
    registry_path = os.path.join(os.path.dirname(__file__), "..", "registry", "vasp_labels.json")
    try:
        vasp_labels = load_registry(registry_path)
    except FileNotFoundError:
        print(f"Error: Could not find {registry_path}. Make sure you saved vasp_labels.json.")
        exit(1)

    # 2. Create a synthetic sweep pattern using your exact NormalizedTransaction schema
    mock_txs = [
        NormalizedTransaction(
            tx_hash="0x1", chain=ChainEnum.ethereum, from_address="0xVictim1", to_address="0xForwarder",
            value=1.0, token="native", timestamp=datetime.now(timezone.utc), block_number=1, tx_type_raw=TxTypeRaw.transfer
        ),
        NormalizedTransaction(
            tx_hash="0x2", chain=ChainEnum.ethereum, from_address="0xVictim2", to_address="0xForwarder",
            value=2.0, token="native", timestamp=datetime.now(timezone.utc), block_number=2, tx_type_raw=TxTypeRaw.transfer
        ),
        # The forwarder sweeps the funds into Binance Hot Wallet 6
        NormalizedTransaction(
            tx_hash="0x3", chain=ChainEnum.ethereum, from_address="0xForwarder", to_address="0x8894e0a0c962cb723c1976a4421c95949be2d4e3",
            value=3.0, token="native", timestamp=datetime.now(timezone.utc), block_number=3, tx_type_raw=TxTypeRaw.transfer
        )
    ]

    # 3. Run the detector
    print("Running synthetic sweep test...")
    results = detect_sweeps(mock_txs, vasp_labels)
    
    print("\n--- Sweep Detection Results ---")
    if results:
        for addr, label in results.items():
            print(f"{addr}: {label}")
    else:
        print("FAILED: No sweeps detected.")