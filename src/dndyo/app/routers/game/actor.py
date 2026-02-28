from fastapi import APIRouter, Depends
from sqlmodel import Session
from dndyo.app.models.actor import Actor, ActorCreate, ActorRead
from dndyo.app.core.db import get_session
from dndyo.app.routers.game.deps import require_game_id

router = APIRouter()


@router.post("/actor", response_model=ActorRead)
def create_actor(
    actor: ActorCreate,
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    db_actor = Actor.model_validate(actor)
    db_actor.game_id = game_id
    session.add(db_actor)
    session.commit()
    session.refresh(db_actor)
    return db_actor
