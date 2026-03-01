from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session, col, delete, func, select

from dndyo.app.core.ai.ai import stream_ai_response
from dndyo.app.core.db import engine, get_session
from dndyo.app.models.chat import (
    ChatMessage,
    ChatMessageCreate,
    ChatMessagesDeleteRead,
    ChatMessageRead,
    MessageRole,
    MistralMessage,
)
from dndyo.app.routers.game.deps import require_game_id

router = APIRouter()


def _to_read(message: ChatMessage) -> ChatMessageRead:
    if message.id is None:
        raise ValueError("Chat message ID was not generated.")
    return ChatMessageRead(
        id=message.id,
        message=MistralMessage(
            role=message.role,
            content=message.content,
        ),
    )


@router.delete("/messages", response_model=ChatMessagesDeleteRead)
def delete_messages(
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    where_clause = col(ChatMessage.game_id) == game_id
    total_messages = session.exec(
        select(func.count())
        .select_from(ChatMessage)
        .where(where_clause)
    ).one()
    session.exec(delete(ChatMessage).where(where_clause))
    session.commit()
    return ChatMessagesDeleteRead(deleted=total_messages)


@router.get("/messages", response_model=list[ChatMessageRead])
def get_messages(
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    db_messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.game_id == game_id)
        .order_by(col(ChatMessage.id))
    ).all()
    return [_to_read(message) for message in db_messages]


@router.post("/message", response_model=ChatMessageRead)
def add_message(
    payload: ChatMessageCreate,
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    db_message = ChatMessage(
        role=payload.message.role,
        content=payload.message.content,
        game_id=game_id,
    )
    session.add(db_message)
    session.commit()
    session.refresh(db_message)
    return _to_read(db_message)


@router.post("/run-ai")
def add_ai_message(
    game_id: int = Depends(require_game_id),
    session: Session = Depends(get_session),
):
    history_rows = session.exec(
        select(ChatMessage)
        .where(ChatMessage.game_id == game_id)
        .order_by(col(ChatMessage.id))
    ).all()
    history = [{"role": row.role.value, "content": row.content} for row in history_rows]

    def _stream():
        full_response: list[str] = []
        try:
            for chunk in stream_ai_response(history, game_id=game_id):
                full_response.append(chunk)
                yield chunk
        except Exception as exc:
            # Keep the HTTP stream well-formed even if upstream AI streaming fails.
            yield f"\n[ai-stream-error] {exc}"

        assistant_text = "".join(full_response).strip()
        if assistant_text:
            with Session(engine) as write_session:
                db_message = ChatMessage(
                    role=MessageRole.assistant,
                    content=assistant_text,
                    game_id=game_id,
                )
                write_session.add(db_message)
                write_session.commit()

    return StreamingResponse(_stream(), media_type="text/plain")
