"""The Paldeck: every species, with the server's ownership counts and each player's capture bonus progress.

See backend/common/paldeck.py for the shapes; this router only joins the parsed save to them.
"""
from fastapi import APIRouter, Depends, HTTPException

from backend.common import online
from backend.common.auth import require_auth
from backend.common.exp_tables import BONUS_CAP
from backend.common.paldeck import deck_aliases, deck_ids, filter_options, player_progress, species_detail, species_rows
from backend.parser import parser

router = APIRouter(prefix="/api/paldeck", tags=["paldeck"], dependencies=[Depends(require_auth)])


@router.get("")
async def get_paldeck():
    """Every deck species in Paldeck order, plus each player's place in the capture bonus chain.

    `players[].bonus` is {species id: catches that paid, <= 5} and `.caught` the raw tally, so
    the UI can draw the pips and the "missing" list without another request. `exp_rate` is the
    server's ExpRate when the REST API answered (bonus figures are already scaled by it);
    null means the figures are at the default rate.
    """
    data = parser.data
    rate = await online.fetch_exp_rate()
    rows = species_rows(data, parser.get_pals())
    return {
        "species": rows,
        "filters": filter_options(data, rows),
        "players": player_progress(parser.get_players(), data.species, set(deck_ids(data.pals)), data.exp, rate,
                                   aliases=deck_aliases(data.pals)),
        "bonus_cap": BONUS_CAP,
        "exp_rate": rate,
        "has_exp_table": bool(data.exp.get("capture_bonus")),
    }


@router.get("/{species_id}")
async def get_species(species_id: str):
    """One species in full: description, spawn groups, breeding, the pals of it on this server."""
    data = parser.data
    sid = data.species.resolve(species_id) or species_id
    detail = species_detail(data, sid, parser.get_pals(), parser.get_players())
    if detail is None:
        raise HTTPException(status_code=404, detail="Not a Paldeck species")
    return detail
