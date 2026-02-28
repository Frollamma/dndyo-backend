from sqlalchemy import inspect
from sqlmodel import create_engine, SQLModel
from sqlmodel import Session

# Import table models so SQLModel metadata is populated before create_all.
from dndyo.app.models.actor import Actor
from dndyo.app.models.chat import ChatMessage
from dndyo.app.models.game import Game
from dndyo.app.models.game_state import GameState
from dndyo.app.models.image import Image
from dndyo.app.models.live_actor import LiveActor
from dndyo.app.models.map import Map

DATABASE_URL = "sqlite:///database.db"

engine = create_engine(DATABASE_URL, echo=True)


def _schema_compatible() -> bool:
    required_columns = {
        "game": {"id", "name", "owner_user", "game_state_id", "chapters", "current_chapters"},
        "actor": {"id", "game_id"},
        "chatmessage": {"id", "game_id"},
        "gamestate": {"id"},
        "liveactor": {"id", "game_id"},
        "map": {"id", "game_id"},
        "image": {"id", "uri"},
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table_name, expected in required_columns.items():
        if table_name not in existing_tables:
            return False
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if not expected.issubset(columns):
            return False

    return True


def init_db():
    if not _schema_compatible():
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
