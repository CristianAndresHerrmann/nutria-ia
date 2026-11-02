from fastapi import Request
from fastapi.responses import JSONResponse

from app.schemas.plan_proposal import GenerationErrorResponse


class GenerationError(Exception):
    """Error controlado de la generación, con código estable. El backend lo traduce a
    un error con reintento (RNF-02)."""

    def __init__(self, status_code: int, body: GenerationErrorResponse):
        super().__init__(body.error.message)
        self.status_code = status_code
        self.body = body


async def generation_error_handler(request: Request, exc: GenerationError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body.model_dump(mode="json"))
