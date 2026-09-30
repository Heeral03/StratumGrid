"""
FleetScale — FastAPI Application Entry Point

Mounts the REST API router and serves the frontend dashboard
as static files.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .routes import router

app = FastAPI(
    title="FleetScale — Warehouse Spatial Arbiter",
    version="1.0.0",
    description="Hierarchical resource locking engine for automated warehouse sub-grid management.",
)

# CORS — allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
