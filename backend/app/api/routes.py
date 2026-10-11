"""HTTP API routes."""

from fastapi import APIRouter, HTTPException

from app import __version__

router = APIRouter(prefix="/api")


@router.get("/version", tags=["meta"])
async def version() -> dict[str, str]:
    return {"name": "SecureDoc AI", "version": __version__}


@router.post("/process-document", tags=["documents"])
async def process_document() -> dict[str, str]:
    # Implemented in a later step (schemas + service orchestration).
    raise HTTPException(status_code=501, detail="Not implemented yet")
