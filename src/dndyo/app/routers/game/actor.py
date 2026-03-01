from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select
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
    # Convert to dict and keep abilities as dicts (not ActorAbility objects)
    payload = actor.model_dump(mode="json")
    payload["game_id"] = game_id
    # Create Actor directly without re-validating (which converts abilities back to objects)
    db_actor = Actor(**payload)
    session.add(db_actor)
    session.commit()
    session.refresh(db_actor)
    return db_actor


@router.get("/actors", response_model=list[ActorRead])
def list_actors(
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    return session.exec(
        select(Actor).where(col(Actor.game_id) == game_id).order_by(col(Actor.id))
    ).all()
