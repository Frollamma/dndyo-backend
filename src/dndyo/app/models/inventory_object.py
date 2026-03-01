from pydantic import BaseModel


class InventoryObject(BaseModel):
    name: str
    description: str
    quantity: int
