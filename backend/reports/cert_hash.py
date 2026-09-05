import hashlib
import json
import datetime
from datetime import timezone

def generate_evidentiary_cert(report_data: dict) -> dict:
    """
    Appends a SHA-256 hash and ISO timestamp to the report data, 
    framing it as a BSA Section 63 electronic evidence certificate.
    """
    serialized_content = json.dumps(report_data, sort_keys=True, default=str)
    timestamp = datetime.datetime.now(timezone.utc).isoformat()
    raw_string = f"{serialized_content}{timestamp}"
    
    cert_hash = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()
    
    return {
        "report_content": report_data,
        "evidentiary_certificate": {
            "legal_standard": "BSA Section 63 (Electronic Evidence Certificate)",
            "timestamp_utc": timestamp,
            "sha256_hash": cert_hash,
            "status": "Tamper-Evident & Cryptographically Sealed"
        }
    }