from fastapi import APIRouter, Depends

from studio_api import auth as auth_mod
from studio_api.completion_service import suggest
from studio_api.models import User
from studio_api.schemas import CompletionBody, CompletionItem, CompletionResponse

router = APIRouter(prefix="/api/v1", tags=["completion"])


@router.post("/completion", response_model=CompletionResponse)
async def completion(
    body: CompletionBody,
    current_user: User = Depends(auth_mod.get_current_user),
):
    raw = suggest(body.source_code, body.cursor_line, body.cursor_col)
    items = [CompletionItem.model_validate(r) for r in raw]
    return CompletionResponse(suggestions=items)
