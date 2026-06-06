from fastapi import APIRouter, Depends

from studio_api import auth as auth_mod
from studio_api.format_service import format_python
from studio_api.models import User
from studio_api.schemas import FormatBody

router = APIRouter(prefix="/api/v1", tags=["format"])


@router.post("/format")
async def format_code(
    body: FormatBody,
    current_user: User = Depends(auth_mod.get_current_user),
):
    r = format_python(body.source_code)
    return r
