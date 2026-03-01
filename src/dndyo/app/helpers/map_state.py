from sqlmodel import Session, col, select

from dndyo.app.models.image import Image
from dndyo.app.models.map import Map

DEFAULT_MAP_IMAGE_URI = "https://example.com/default-map.png"
DEFAULT_MAP_NAME = "Starting Area"
DEFAULT_MAP_DESCRIPTION = 0


def ensure_game_has_map(session: Session, game_id: int) -> int:
    existing = session.exec(
        select(Map).where(col(Map.game_id) == game_id).order_by(col(Map.id))
    ).first()
    if existing is not None and existing.id is not None:
        return existing.id

    image = Image(uri=DEFAULT_MAP_IMAGE_URI)
    session.add(image)
    session.flush()
    if image.id is None:
        raise RuntimeError("Image ID was not generated for default map.")

    db_map = Map(
        game_id=game_id,
        name=DEFAULT_MAP_NAME,
        description=DEFAULT_MAP_DESCRIPTION,
        image_id=image.id,
        connected_maps_ids=[],
    )
    session.add(db_map)
    session.flush()
    if db_map.id is None:
        raise RuntimeError("Map ID was not generated.")
    return db_map.id
