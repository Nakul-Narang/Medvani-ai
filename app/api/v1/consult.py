from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.agents.state import MedicalAgentState
from app.core.security import api_key_is_valid
from app.schemas.consult import ConsultRequest, ConsultResponse, Source

router = APIRouter(tags=["consult"])


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    if not api_key_is_valid(x_api_key, request.app.state.settings.api_keys):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.post("/consult", response_model=ConsultResponse, dependencies=[Depends(require_api_key)])
def consult(payload: ConsultRequest, request: Request) -> ConsultResponse:
    settings = request.app.state.settings
    if len(payload.query) > settings.max_query_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Query too long (max {settings.max_query_chars} characters). Please shorten it.",
        )

    state: MedicalAgentState = {
        "request_id": request.state.request_id,
        "raw_user_query": payload.query,
        "user_language": payload.language,
        "chat_history": [turn.model_dump() for turn in payload.history],
    }
    result = request.app.state.pipeline.invoke(state)

    return ConsultResponse(
        request_id=request.state.request_id,
        detected_language=result["detected_language"],
        response_language=result["response_language"],
        answer=result["final_translated_response"],
        emergency=result["emergency"],
        emergency_reasons=result.get("emergency_rules", []),
        sources=[
            Source(id=h["id"], title=h["title"], source=h["source"], score=h["score"])
            for h in result.get("retrieved", [])
        ],
        warnings=result.get("warnings", []),
        history=result["chat_history"],
    )
