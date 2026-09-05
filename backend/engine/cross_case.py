from sqlalchemy.orm import Session
from backend.db.models import Address, Case

def check_cross_case_linkage(db: Session, current_case_id: int, target_address: str) -> list[str]:
    """
    Checks the database to see if this address has appeared in prior SAHYOG cases.
    Returns a list of linked SAHYOG case IDs.
    """
    # Ensure case-insensitive matching for EVM addresses
    target_address_lower = target_address.lower()
    
    prior_appearances = (
        db.query(Address)
        .join(Case)
        .filter(Address.address.ilike(target_address_lower))
        .filter(Address.case_id != current_case_id)
        .all()
    )
    
    linked_case_ids = []
    for record in prior_appearances:
        if record.case and record.case.sahyog_case_id:
            linked_case_ids.append(record.case.sahyog_case_id)
            
    return list(set(linked_case_ids))

if __name__ == "__main__":
    from backend.db.models import engine, Base, SessionLocal
    
    # Quick smoke test for the exit criteria
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 1. Scaffold an old case
    old_case = Case(sahyog_case_id="FIR-2023-001")
    db.add(old_case)
    db.commit()
    
    db.add(Address(case_id=old_case.id, address="0xSuspectDemo", chain="ethereum", role="suspect"))
    db.commit()
    
    # 2. Simulate a new case searching for the same address
    new_case = Case(sahyog_case_id="FIR-2026-999")
    db.add(new_case)
    db.commit()
    
    links = check_cross_case_linkage(db, new_case.id, "0xSuspectDemo")
    print(f"Cross-case links found: {links}")