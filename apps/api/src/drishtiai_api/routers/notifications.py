from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from ..deps import CurrentUser, RedisClient
from ..schemas import RequestModel

router = APIRouter()


class TokenBody(RequestModel):
    token: str = Field(min_length=1, max_length=512)


@router.post("/register", status_code=status.HTTP_204_NO_CONTENT)
async def register(
    body: TokenBody,
    current_user: CurrentUser,
    redis: RedisClient,
):
    for site_id in (current_user.site_ids or []):
        await redis.sadd(f"push_site_tokens:{site_id}:{current_user.id}", body.token)


@router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT)
async def unregister(
    body: TokenBody,
    current_user: CurrentUser,
    redis: RedisClient,
):
    for site_id in (current_user.site_ids or []):
        await redis.srem(f"push_site_tokens:{site_id}:{current_user.id}", body.token)
