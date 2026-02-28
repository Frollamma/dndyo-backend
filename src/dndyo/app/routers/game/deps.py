from fastapi import Depends, HTTPException
from sqlmodel import Session, select

from dndyo.app.core.db import get_session
from dndyo.app.models.game import Game


def require_game_id(
    game_id: int,
    session: Session = Depends(get_session),
) -> int:
    game = session.exec(select(Game).where(Game.id == game_id)).first()
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found.")
    return game_id
