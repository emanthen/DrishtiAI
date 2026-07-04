"""Shared Pydantic base for all inbound request bodies."""
from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """All Create/Patch/Update schemas inherit this.
    extra='forbid' rejects unknown fields — prevents mass-assignment.
    """
    model_config = ConfigDict(extra="forbid")
