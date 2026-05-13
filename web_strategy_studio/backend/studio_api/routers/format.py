from fastapi import APIRouter

from studio_api.format_service import format_python
from studio_api.schemas import FormatBody

router = APIRouter(prefix="/api/v1", tags=["format"])


@router.post("/format")
async def format_code(body: FormatBody):
    r = format_python(body.source_code)
    return r
