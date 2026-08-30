from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_analysis import analyze

router = APIRouter(prefix="/ai-agent", tags=["ai-agent"])


@router.post("/analyze")
def analyze_request(
    body: dict,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    question = str((body or {}).get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")
    if len(question) > 1000:
        raise HTTPException(status_code=422, detail="question must be 1000 characters or fewer")
    try:
        return analyze(db, question, (body or {}).get("from") or from_date, (body or {}).get("to") or to_date)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {exc}") from exc
