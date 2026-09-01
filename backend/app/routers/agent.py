from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..routers.auth import CurrentUser, get_current_user
from ..services import ai_agent

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/status")
def status(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    return ai_agent.agent_status(db)


@router.get("/investigations")
def investigations(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    return {"items": ai_agent.investigations(db, merchant_id=current_user.merchant_id)}


@router.post("/ask")
def ask(
    body: dict,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    question = (body or {}).get("question") or ""
    frm = (body or {}).get("from") or from_date
    to = (body or {}).get("to") or to_date
    return ai_agent.run_agent(db, question, frm, to, merchant_id=current_user.merchant_id)