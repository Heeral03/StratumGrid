from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any
from backend.models import LockRequest, UnlockRequest, UpgradeRequest, HeartbeatRequest
from engine.tree_manager import TreeManager
from engine.audit import AuditLogger
from backend.ws_manager import ws_manager

router = APIRouter()
audit_logger = AuditLogger()
tree_manager = TreeManager(audit_logger=audit_logger)


async def broadcast_tree_change(event_type: str, detail: Dict[str, Any]):
    """Helper to broadcast real-time state changes to all WebSocket subscribers."""
    tree_snapshot = tree_manager.get_tree_state()
    audit_snapshot = audit_logger.get_logs()
    await ws_manager.broadcast({
        "type": event_type,
        "detail": detail,
        "tree": tree_snapshot,
        "audit": audit_snapshot
    })


@router.post("/api/v1/resource/lock")
async def lock_resource(payload: LockRequest):
    result = tree_manager.lock(payload.node_id, payload.agent_id, payload.ttl_seconds)
    if not result["success"]:
        await broadcast_tree_change("LOCK_FAILED", result)
        raise HTTPException(status_code=400, detail=result["message"])
    
    await broadcast_tree_change("LOCK_SUCCESS", result)
    return {"success": True, "message": result["message"], "expires_at": result.get("expires_at"), "ttl_seconds": payload.ttl_seconds}


@router.post("/api/v1/resource/unlock")
async def unlock_resource(payload: UnlockRequest):
    result = tree_manager.unlock(payload.node_id, payload.agent_id)
    if not result["success"]:
        await broadcast_tree_change("UNLOCK_FAILED", result)
        raise HTTPException(status_code=400, detail=result["message"])

    await broadcast_tree_change("UNLOCK_SUCCESS", result)
    return {"success": True, "message": result["message"]}


@router.post("/api/v1/resource/heartbeat")
async def heartbeat_resource(payload: HeartbeatRequest):
    result = tree_manager.heartbeat(payload.node_id, payload.agent_id, payload.ttl_seconds)
    if not result["success"]:
        await broadcast_tree_change("HEARTBEAT_FAILED", result)
        raise HTTPException(status_code=400, detail=result["message"])

    await broadcast_tree_change("HEARTBEAT_SUCCESS", result)
    return {
        "success": True,
        "message": result["message"],
        "expires_at": result.get("expires_at"),
        "ttl_remaining": result.get("ttl_remaining")
    }


@router.post("/api/v1/resource/upgrade")
async def upgrade_resource(payload: UpgradeRequest):
    result = tree_manager.upgrade(payload.parent_id, payload.agent_id)
    if not result["success"]:
        await broadcast_tree_change("UPGRADE_FAILED", result)
        raise HTTPException(status_code=400, detail=result["message"])

    await broadcast_tree_change("UPGRADE_SUCCESS", result)
    return {"success": True, "message": result["message"]}


@router.get("/api/v1/resource/status")
def get_resource_status():
    return {
        "success": True,
        "data": {
            "tree": tree_manager.get_tree_state(),
            "nodes": tree_manager.get_all_nodes_flat()
        }
    }


@router.get("/api/v1/audit")
def get_audit_log():
    return {
        "success": True,
        "data": {
            "log": audit_logger.get_logs()
        }
    }


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await ws_manager.connect(websocket)
    # Send initial state snapshot upon connection
    await websocket.send_json({
        "type": "INITIAL_STATE",
        "tree": tree_manager.get_tree_state(),
        "audit": audit_logger.get_logs()
    })
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
