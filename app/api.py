"""
Main API router for Sonar project
"""
from ninja import NinjaAPI

from app.recordings.api.router import router as recordings_router

# Create main API instance
api = NinjaAPI(
    title="Sonar API",
    version="1.0.0",
    description="Speech recognition and diarization system",
    csrf=False
)

# Register app routers
api.add_router("/", recordings_router)
