from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/sahyog", tags=["SAHYOG Integration Stub"])

class SahyogIntakeRequest(BaseModel):
    fir_number: str
    suspect_address: str
    chain: str
    complainant_agency: str

class SahyogIntakeResponse(BaseModel):
    status: str
    job_id: str
    message: str
    disclaimer: str

@router.post("/intake", response_model=SahyogIntakeResponse)
def submit_to_sahyog(payload: SahyogIntakeRequest):
    """
    Mock intake endpoint for SAHYOG case routing.
    Clearly labeled as an integration stub, not a live connection.
    """
    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
    
    return {
        "status": "success",
        "job_id": job_id,
        "message": f"Case {payload.fir_number} intake registered for address {payload.suspect_address}.",
        "disclaimer": "INTEGRATION STUB: This is a simulated SAHYOG return receipt. Not a live production connection."
    }