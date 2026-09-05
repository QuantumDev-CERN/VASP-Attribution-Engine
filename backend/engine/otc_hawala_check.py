import json
import os
from typing import List
from backend.api.schemas import NormalizedTransaction

def load_otc_registry(filepath: str) -> dict:
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}

def save_otc_registry(filepath: str, data: dict):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def detect_otc_hawala(transactions: List[NormalizedTransaction], terminal_address: str, registry_path: str) -> bool:
    """
    Heuristic: Many small disparate deposits into the terminal address, with no further outgoing movement.
    Persists confirmed terminus wallets to the static registry.
    """
    terminal_lower = terminal_address.lower()
    
    deposits = [tx for tx in transactions if tx.to_address.lower() == terminal_lower]
    outgoing = [tx for tx in transactions if tx.from_address.lower() == terminal_lower]
    
    # If the address is moving money out, it's not a dead-end terminus
    if len(outgoing) > 0:
        return False 
        
    unique_senders = set(tx.from_address.lower() for tx in deposits if tx.from_address)
    
    # Heuristic Threshold: At least 3 different unlinked senders
    if len(unique_senders) >= 3:
        registry = load_otc_registry(registry_path)
        registry[terminal_lower] = {
            "type": "otc-hawala-terminus",
            "depositors": len(unique_senders),
            "flagged_at": deposits[-1].timestamp.isoformat()
        }
        save_otc_registry(registry_path, registry)
        return True
        
    return False