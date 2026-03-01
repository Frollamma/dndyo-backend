"""Image endpoints for retrieving generated images."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from dndyo.app.core.db import get_session
from dndyo.app.models.image import Image, ImageRead

router = APIRouter()


@router.get(
    "/",
    response_model=list[ImageRead],
    summary="List Images",
    description="List all images.",
)
def list_images(
    session: Session = Depends(get_session),
):
    """List all images in the database."""
    return session.exec(select(Image)).all()


@router.get(
    "/{image_id}",
    response_model=ImageRead,
    summary="Get Image Metadata",
    description="Retrieve image metadata by ID.",
)
def get_image(
    image_id: int,
    session: Session = Depends(get_session),
):
    """Get image metadata by ID."""
    image = session.exec(select(Image).where(Image.id == image_id)).first()
    if image is None:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found.")
    return image


@router.get(
    "/{image_id}/file",
    summary="Get Image File",
    description="Get the actual image file by ID (displays inline in browser).",
)
def get_image_file(
    image_id: int,
    session: Session = Depends(get_session),
):
    """Get image file by ID - displays inline in browser instead of downloading."""
    image = session.exec(select(Image).where(Image.id == image_id)).first()
    if image is None:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found.")

    # Resolve file path
    file_path = Path(image.uri)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Image file not found: {image.uri}")

    # Content-Disposition: inline tells browser to display the image instead of downloading
    return FileResponse(
        path=file_path,
        media_type="image/png",
        headers={"Content-Disposition": "inline; filename=image.png"},
    )

