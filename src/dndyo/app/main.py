from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dndyo.app.routers import game
from dndyo.app.core.db import init_db

init_db()

app = FastAPI(title="My FastAPI App")

# Enable CORS to allow cross-origin requests from browsers (e.g., Chrome)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins; restrict in production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods including OPTIONS
    allow_headers=["*"],  # Allow all headers
)

app.include_router(game.router, prefix="/api/game")


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
