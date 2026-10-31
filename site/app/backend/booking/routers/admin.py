from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from booking import clock
from booking.db import get_session
from booking.seed import reset

router = APIRouter(prefix="/api/admin")


@router.post("/reset")
def reset_endpoint(session: Session = Depends(get_session)):
    reset(session, clock.now())
    return {"status": "ok"}
