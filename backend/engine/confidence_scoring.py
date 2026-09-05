from typing import List, Dict, Tuple
from backend.api.schemas import NormalizedTransaction

# Draft Starting Weights from phases.md §8
BASE_SCORE_1_HOP = 90
PENALTY_PER_HOP = -10
BONUS_SWEEP = 15
PENALTY_MIXER = -60
PENALTY_BRIDGE_EXPLICIT = -5
PENALTY_BRIDGE_CORRELATION = -25

def evaluate_path_confidence(
    path: List[NormalizedTransaction], 
    address_labels: Dict[str, str]
) -> Tuple[int, str, str]:
    """
    Evaluates a chronological path (list of transactions) from suspect to terminal node.
    Returns: (Numeric Score, Confidence Band, Reason String)
    """
    if not path:
        return 0, "Unresolved", "Empty path provided."

    score = BASE_SCORE_1_HOP
    reasons = []
    
    # 1. Hop Discounting
    hop_count = len(path)
    if hop_count > 1:
        hop_penalty = (hop_count - 1) * PENALTY_PER_HOP
        score += hop_penalty
        reasons.append(f"{hop_count} hops ({hop_penalty})")
    else:
        reasons.append("1 hop (direct)")

    # 2. Iterate through path to check for edge-specific and address-specific modifiers
    hit_mixer = False
    
    for tx in path:
        # Check from_address and to_address against our generated/static labels
        from_label = address_labels.get(tx.from_address.lower() if tx.chain.value == "ethereum" else tx.from_address, "")
        to_label = address_labels.get(tx.to_address.lower() if tx.chain.value == "ethereum" else tx.to_address, "")
        
        combined_labels = f"{from_label} {to_label}".lower()

        # Sweep Detection Bonus
        if "sweep-forwarder" in combined_labels or "sweep-contributor" in combined_labels:
            score += BONUS_SWEEP
            reasons.append(f"passed through confirmed sweep (+{BONUS_SWEEP})")

        # Mixer Detection Penalty
        if "mixer" in combined_labels:
            hit_mixer = True
            score += PENALTY_MIXER
            reasons.append(f"passed through known mixer contract ({PENALTY_MIXER})")
            
        # Bridge Detection Penalties (Using basic tags for now)
        if tx.tx_type_raw.value == "bridge_lock":
            # Assuming we can differentiate explicit vs correlated bridges later
            # Defaulting to explicit destination penalty for the stub
            score += PENALTY_BRIDGE_EXPLICIT
            reasons.append(f"passed through bridge with explicit destination ({PENALTY_BRIDGE_EXPLICIT})")

    # 3. Floor/Ceiling bounds
    score = max(0, min(100, score))

    # 4. Determine Confidence Band
    if hit_mixer:
        band = "Flagged-Mixer"
        score = min(score, 39) # Cap at low regardless of other signals per phases.md
    elif score >= 70:
        band = "High"
    elif score >= 40:
        band = "Medium"
    else:
        band = "Low"

    # Terminal node check (Did it actually hit an exchange?)
    terminal_tx = path[-1]
    terminal_label = address_labels.get(
        terminal_tx.to_address.lower() if terminal_tx.chain.value == "ethereum" else terminal_tx.to_address, 
        ""
    )
    
    if "exchange" not in terminal_label.lower() and terminal_label != "":
        # It's an OTC hawala terminus or unresolved
        if "otc" in terminal_label.lower() or "hawala" in terminal_label.lower():
            band = "OTC-Terminus"
            reasons.append("Terminal address matches OTC/hawala registry pattern")
        else:
            band = "Unresolved"
            reasons.append("Terminal address unlabeled, no further activity")

    reason_string = " | ".join(set(reasons))  # set() prevents duplicate reason stacking
    return score, band, reason_string

if __name__ == "__main__":
    from datetime import datetime, timezone
    from backend.api.schemas import ChainEnum, TxTypeRaw
    
    # Mocking the sweep from Phase 3
    mock_path = [
        NormalizedTransaction(
            tx_hash="0x1", chain=ChainEnum.ethereum, from_address="0xVictim1", to_address="0xForwarder",
            value=1.0, token="native", timestamp=datetime.now(timezone.utc), block_number=1, tx_type_raw=TxTypeRaw.transfer
        ),
        NormalizedTransaction(
            tx_hash="0x2", chain=ChainEnum.ethereum, from_address="0xForwarder", to_address="0xBinanceHot",
            value=1.0, token="native", timestamp=datetime.now(timezone.utc), block_number=2, tx_type_raw=TxTypeRaw.transfer
        )
    ]
    
    mock_labels = {
        "0xforwarder": "sweep-forwarder",
        "0xbinancehot": "Binance: Hot Wallet 6 (exchange)"
    }
    
    score, band, reason = evaluate_path_confidence(mock_path, mock_labels)
    print(f"Score: {score}\nBand: {band}\nReason: {reason}")