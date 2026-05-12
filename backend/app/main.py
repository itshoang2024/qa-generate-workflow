from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import router as api_v1_router
from app.config import get_settings
from app.domain.responses import error_envelope

settings = get_settings()

app = FastAPI(
    title="QA Generate Workflow API",
    description=(
        "Prototype API for an AI-assisted QA workflow: GDD parsing, feature inventory, "
        "task planning, test-case generation, validation gates, and Notion sync."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "QA Generate Workflow API",
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                code=str(exc.detail["code"]),
                message=str(exc.detail.get("message", "Request failed.")),
                details=exc.detail.get("details"),
            ),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(
            code=f"http_{exc.status_code}",
            message=str(exc.detail),
        ),
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_envelope(
            code="internal_error",
            message="Unexpected server error.",
            details=str(exc),
        ),
    )
