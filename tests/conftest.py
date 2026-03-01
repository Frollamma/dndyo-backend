from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from dndyo.app.core.db import get_session
from dndyo.app.main import app


@pytest.fixture
def test_engine(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(test_engine, monkeypatch) -> Generator[TestClient, None, None]:
    def override_get_session():
        with Session(test_engine) as session:
            yield session

    monkeypatch.setattr("dndyo.app.routers.game.chat.engine", test_engine)
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
