from typing import Optional

from sqlmodel import Field, SQLModel


class ImageBase(SQLModel):
    uri: str


class Image(ImageBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class ImageCreate(ImageBase):
    pass


class ImageRead(ImageBase):
    id: int
