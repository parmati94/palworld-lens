"""Custom base names: one shared JSON file under APP_STATE_PATH, edited from the UI."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.common.auth import require_auth
from backend.common.base_names import MAX_NAME_LENGTH, clean_name
from backend.common.logging_config import get_logger
from backend.parser import parser

logger = get_logger(__name__)
router = APIRouter(prefix="/api/base-names", tags=["base-names"])


class RenameBody(BaseModel):
    name: Optional[str] = None      # blank / null clears the custom name


@router.get("", dependencies=[Depends(require_auth)])
async def get_base_names():
    """{names: {base_id: name}, writable: bool}"""
    return parser.base_names_payload()


@router.put("/{base_id}", dependencies=[Depends(require_auth)])
async def rename_base(base_id: str, body: RenameBody):
    if not parser.loaded:
        raise HTTPException(status_code=400, detail="No save file loaded")
    known = {b.base_id for g in parser.get_guilds() for b in g.base_locations}
    if base_id not in known:
        raise HTTPException(status_code=404, detail="Unknown base")
    if body.name and len(clean_name(body.name)) > MAX_NAME_LENGTH:
        raise HTTPException(status_code=422, detail=f"Name must be at most {MAX_NAME_LENGTH} characters")
    try:
        stored = parser.rename_base(base_id, body.name)
    except PermissionError as e:
        logger.warning(f"rename refused: {e}")
        raise HTTPException(status_code=409, detail="Base names are not writable on this server (no APP_STATE_PATH volume)")
    except OSError as e:
        logger.error(f"rename failed: {e}")
        raise HTTPException(status_code=500, detail="Could not save the name")
    logger.info(f"base {base_id} renamed to {stored!r}")
    return {"base_id": base_id, "name": stored, **parser.base_names_payload()}
