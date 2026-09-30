"""
Pydantic DTOs for strict payload validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


class LockRequest(BaseModel):
    node_id: str = Field(..., min_length=1, description="Target node identifier")
    agent_id: str = Field(..., min_length=1, description="Requesting agent identifier")


class UnlockRequest(BaseModel):
    node_id: str = Field(..., min_length=1, description="Target node identifier")
    agent_id: str = Field(..., min_length=1, description="Requesting agent identifier")


class UpgradeRequest(BaseModel):
    parent_id: str = Field(..., min_length=1, description="Parent node to upgrade into")
    agent_id: str = Field(..., min_length=1, description="Requesting agent identifier")


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
