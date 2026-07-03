from fastapi import APIRouter, status
from pydantic import BaseModel

from ..deps import CurrentUser, RedisClient

router = APIRouter()


class TokenBody(BaseModel):
    token: str


@router.post("/register", status_code=status.HTTP_204_NO_CONTENT)
async def register(
    body: TokenBody,
    current_user: CurrentUser,
    redis: RedisClient,
):
    key = f"push_tokens:{current_user.id}"
    await redis.sadd(key, body.token)


@router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT)
async def unregister(
    body: TokenBody,
    current_user: CurrentUser,
    redis: RedisClient,
):
    key = f"push_tokens:{current_user.id}"
    await redis.srem(key, body.token)
