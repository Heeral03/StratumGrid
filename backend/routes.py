"""
REST API routes for FleetScale resource arbiter.
"""

from fastapi import APIRouter
from .models import LockRequest, UnlockRequest, UpgradeRequest, ApiResponse
from engine.tree_manager import TreeManager

router = APIRouter(prefix="/api/v1")

# Shared tree manager instance (single process, thread-safe)
tree_manager = TreeManager()


@router.post("/resource/lock", response_model=ApiResponse)
def lock_resource(req: LockRequest):
    result = tree_manager.lock(req.node_id, req.agent_id)
    return ApiResponse(**result)


@router.post("/resource/unlock", response_model=ApiResponse)
def unlock_resource(req: UnlockRequest):
    result = tree_manager.unlock(req.node_id, req.agent_id)
    return ApiResponse(**result)


@router.post("/resource/upgrade", response_model=ApiResponse)
def upgrade_resource(req: UpgradeRequest):
    result = tree_manager.upgrade(req.parent_id, req.agent_id)
    return ApiResponse(**result)


@router.get("/resource/status", response_model=ApiResponse)
def get_status():
    tree = tree_manager.get_tree_state()
    nodes = tree_manager.get_all_node_ids()
    return ApiResponse(success=True, message="Current tree state", data={"tree": tree, "nodes": nodes})


@router.get("/audit", response_model=ApiResponse)
def get_audit_log():
    log = tree_manager.audit.get_log()
    return ApiResponse(success=True, message=f"{len(log)} audit entries", data={"log": log})
