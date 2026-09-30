import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.routes import router, tree_manager, broadcast_tree_change


async def expired_lock_cleanup_worker():
    """
    Background worker loop that runs every 1 second, checks for expired TTL leases,
    releases stale locks, and broadcasts LEASE_EXPIRED updates over WebSockets.
    """
    while True:
        try:
            await asyncio.sleep(1.0)
            expired_events = tree_manager.check_and_expire_locks()
            if expired_events:
                for event in expired_events:
                    await broadcast_tree_change("LEASE_EXPIRED", event)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background cleanup task
    cleanup_task = asyncio.create_task(expired_lock_cleanup_worker())
    yield
    # Cleanup task on shutdown
    cleanup_task.cancel()


app = FastAPI(
    title="StratumGrid — Dynamic Warehouse Sub-Grid Spatial Arbiter",
    description="High-performance $M$-ary tree spatial arbiter with thread-safe locking, TTL heartbeats, and WebSocket streaming.",
    version="2.0.0",
    lifespan=lifespan
)

# Register API routes
app.include_router(router)

# Serve frontend static assets
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def read_root():
    """Serves the single-page dashboard application."""
    from fastapi.responses import FileResponse
    return FileResponse("frontend/index.html")
