from pydantic import BaseModel, Field
from typing import Optional


class LockRequest(BaseModel):
    node_id: str = Field(..., description="ID of the target spatial node (e.g. aisle-A1, bin-A1R1B1)")
    agent_id: str = Field(..., description="ID of the requesting bot or auditor (e.g. bot-alpha)")
    ttl_seconds: int = Field(30, description="Lease duration in seconds (default: 30s)", ge=5, le=300)


class UnlockRequest(BaseModel):
    node_id: str = Field(..., description="ID of the spatial node to unlock")
    agent_id: str = Field(..., description="ID of the releasing agent")


class UpgradeRequest(BaseModel):
    parent_id: str = Field(..., description="ID of the parent node to consolidate into")
    agent_id: str = Field(..., description="ID of the requesting agent")


class HeartbeatRequest(BaseModel):
    node_id: str = Field(..., description="ID of the locked node to renew lease for")
    agent_id: str = Field(..., description="ID of the owning agent")
    ttl_seconds: int = Field(30, description="Lease extension duration in seconds", ge=5, le=300)
