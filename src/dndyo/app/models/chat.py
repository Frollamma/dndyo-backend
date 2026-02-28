from enum import Enum

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class MistralMessage(BaseModel):
    role: MessageRole
    content: str


class ChatMessageBase(SQLModel):
    role: MessageRole
    content: str


class ChatMessage(ChatMessageBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)


class ChatMessageCreate(BaseModel):
    message: MistralMessage


class ChatMessageRead(BaseModel):
    id: int
    message: MistralMessage


class ChatMessagesDeleteRead(BaseModel):
    deleted: int
