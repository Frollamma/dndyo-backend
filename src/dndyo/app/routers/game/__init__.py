from fastapi import APIRouter
from . import actor, chat, dice, game, state

router = APIRouter()
router.include_router(game.router, tags=["game"])
router.include_router(chat.router, prefix="/{game_id}/chat", tags=["chat"])
router.include_router(actor.router, prefix="/{game_id}/actor", tags=["actor"])
router.include_router(state.router, prefix="/{game_id}/state", tags=["state"])
router.include_router(dice.router, prefix="/{game_id}/dice", tags=["dice"])
