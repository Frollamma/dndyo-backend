from fastapi import FastAPI
from dndyo.app.routers import game
from dndyo.app.core.db import init_db

init_db()

app = FastAPI(title="My FastAPI App")

app.include_router(game.router, prefix="/api/game")


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
